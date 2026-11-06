#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
sort_scan_batch.py — Triage/Splitter für gemischte, gescannte Dokumentstapel

@tier        infrastructure
@purpose.de  Nimmt große, OCR'te Sammel-PDFs (z.B. aus einem Dokumentenscanner
             mit mehreren unterschiedlichen Dokumenttypen hintereinander) und
             zerlegt sie in einzelne, nach Kategorie sortierte PDF-Dateien.
             Erkennt dabei auch Fast-Duplikate (mehrfach gescannte Seiten).
@purpose.en  Takes large, OCR'd batch PDFs (e.g. from a document scanner with
             several different document types scanned back-to-back) and
             splits them into individual, category-sorted PDF files. Also
             detects near-duplicate pages (the same sheet scanned twice).
@method.de   Rein regelbasiert, KEIN LLM (lokal oder Cloud) beteiligt — läuft
             komplett ohne dass Dokumentinhalte irgendeine KI durchlaufen.
             Extrahiert Seitentext via pdftotext (poppler-utils, muss bereits
             vorhanden sein), klassifiziert jede Seite per Schlüsselwort-/
             Regex-Heuristik (Laborbefund/Laboranforderung/Arztbrief/Genetik/
             Abrechnung/Überweisungsträger/Trennblatt-oder-OCR-Müll/Unklar), erkennt
             Fast-Duplikate per Jaccard-Ähnlichkeit auf Wort-Shingles
             (Schwelle konfigurierbar, lose per Default wegen OCR-Rauschen),
             gruppiert zusammenhängende Seiten derselben Kategorie innerhalb
             einer Quelldatei zu einem logischen Dokument und schneidet jedes
             mit pikepdf in eine eigene Ausgabedatei. Erwartet bereits
             OCR'te PDFs (siehe @limits) — führt selbst kein OCR aus.
@method.en   Purely rule-based, NO LLM (local or cloud) involved — runs
             entirely without document content passing through any AI.
             Extracts page text via pdftotext (poppler-utils, must already
             be installed), classifies each page via keyword/regex heuristics
             (laborbefund/laboranforderung/arztbrief/genetik/abrechnung/
             ueberweisungstraeger/trennblatt-or-ocr-junk/unclear), detects
             near-duplicates via Jaccard similarity on word shingles
             (threshold configurable, loose by default due to OCR noise),
             groups consecutive same-category pages within one source file
             into a logical document, and splits each into its own output
             file with pikepdf. Expects already-OCR'd PDFs (see @limits) —
             does not perform OCR itself.
@relevance.de  Ermöglicht die lokale Vorsortierung gemischter Scan-Stapel ohne KI-Beteiligung, essentiell für den Datenschutz beim Einsortieren großer Dokumentenmengen
@relevance.en  Enables local pre-sorting of mixed scan batches without any AI involvement, essential for privacy when triaging large document volumes
@reads       keine Tabellen (reine Datei-Operation)
@writes      keine Tabellen — nur Dateien: <out-dir>/<kategorie>/*.pdf
             + sortierung_bericht.txt (Status/Pfade, keine Inhalts-Snippets)
@limits.de   Erwartet bereits OCR'te PDFs (durchsuchbarer Text) — vorher
             `ocrmypdf` laufen lassen (siehe requirements.txt/onboard.py für
             Installationshinweis). Gruppierung läuft nur INNERHALB einer
             Eingabedatei — ein logisches Dokument, das genau an einer
             Dateigrenze zwischen zwei Eingabe-PDFs geteilt ist, wird nicht
             automatisch zusammengeführt (wird im Bericht als Randfall an
             Seite 1/letzter Seite markiert). Klassifizierung ist
             heuristisch, kein Ersatz für eine inhaltliche Prüfung —
             Ergebnis immer selbst durchsehen, bevor weiterverarbeitet wird.
             Keine Datei wird gelöscht, auch "uninteressante" Kategorien
             (Überweisungsträger, Trennblätter) landen nur in einem eigenen
             Unterordner, nicht im Papierkorb.
@limits.en   Expects already-OCR'd PDFs (searchable text) — run `ocrmypdf`
             first (see requirements.txt/onboard.py for install hint).
             Grouping only happens WITHIN one input file — a logical
             document split exactly across two input PDFs' boundary is not
             auto-merged (flagged in the report as an edge case at page
             1/last page instead). Classification is heuristic, not a
             substitute for actual review — always check the result before
             further processing. No file is ever deleted; even "irrelevant"
             categories (bank transfer forms, separator sheets) only move
             to their own subfolder, never to the trash.
@usage
    python3 sort_scan_batch.py --file scan1_ocr.pdf scan2_ocr.pdf
    python3 sort_scan_batch.py --file scan_ocr.pdf --out-dir /pfad/sortiert
    python3 sort_scan_batch.py --file scan_ocr.pdf --similarity-threshold 0.6
    python3 sort_scan_batch.py --lang en --file scan_ocr.pdf
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from modules.i18n import t, add_lang_arg, apply_lang_from_args  # noqa: E402
from health_config import Config  # noqa: E402

CATEGORIES_NEXT_STEP = {
    "laborbefund": "python3 scripts/importers/import_lab_results.py --file <datei>.pdf",
    "laboranforderung": t(
        "keine Werte enthalten, i.d.R. kein Import nötig",
        "no values inside, usually no import needed",
    ),
    "arztbrief": t(
        "noch kein Importer — vorerst nur archivieren (medicine/arztbriefe/)",
        "no importer yet — archive for now (medicine/arztbriefe/)",
    ),
    "genetik": t(
        "siehe scripts/importers/import_genetics_*.py (Format ggf. abweichend)",
        "see scripts/importers/import_genetics_*.py (format may differ)",
    ),
    "ueberweisungstraeger": t("kein Gesundheitsbezug — i.d.R. ignorieren", "not health data — usually ignore"),
    "abrechnung": t(
        "Kostenträger-/Leistungsabrechnung — enthält oft ICD-Codes; Importer-Plan siehe "
        "intern/plan_import_diagnosis_history_2026-10.md (läuft auf der UNGESPLITTETEN "
        "Originaldatei, nicht auf dieser Kategorie-Ausgabe, da ICD-Codes je Dokument auch "
        "in angrenzende arztbrief-Seiten streuen können)",
        "payer/benefits billing statement — often contains ICD codes; importer plan in "
        "intern/plan_import_diagnosis_history_2026-10.md (runs against the UNSPLIT "
        "original file, not this category's output, since ICD codes in one document can "
        "spill into neighboring arztbrief-classified pages)",
    ),
    "trennblatt_oder_ocr_muell": t("kein Inhalt — ignorieren", "no content — ignore"),
    "sonstiges_dokument": t("Verwaltung/Einwilligung — Einzelfallprüfung", "admin/consent form — review individually"),
    "unklar": t("von Hand prüfen", "review by hand"),
}

# NUR generische Rechtsform-/Fachbegriffe hier -- KEIN konkreter Laborfirmen-
# name, egal ob bundesweite Kette oder regionale Praxis (beides ist ein
# personenbezogener Identifikator: welches Labor jemand nutzt, verrät etwas
# über Wohnort/Arztnetzwerk) und kein Labor-Name, der selbst schon auf eine
# Fachrichtung/Diagnose hinweist. Alle konkreten Laborfirmennamen gehören nur
# in die lokale, nicht committete Config
# (health_config.json -> scan_sorting.extra_lab_company_markers), niemals in
# den Quellcode -- siehe CLAUDE.md "Privacy rules".
LAB_COMPANY_MARKERS_BASE = [
    "laborgemeinschaft", "medizinisches versorgungszentrum", "labormedizin",
]
LAB_RESULT_MARKERS = ["endbefund", "referenzbereich", "normalwert", "laborwert", "befunddatum"]
ANFORDERUNG_RE = re.compile(r"\bfa-a[s5]\b|\blg-10a-normal\b|\bmikro-a5\b|\banforderung\b", re.IGNORECASE)
# "Auftragsschlüssel" ist spezifisch genug für ein Laborauftrags-/Überweisungs-
# formular, um auch dann Vorrang vor der Laborbefund-Einordnung zu haben, wenn
# dieselbe Seite -- weil es das Formular eines bestimmten Labors ist -- auch
# dessen Firmenname/Befund-Vorlagenfelder enthält.
ANFORDERUNG_STRONG_RE = re.compile(r"\bauftragsschl(?:ü|ue|u)ssel\b", re.IGNORECASE)
# "epikrise" ist medizin-spezifisch genug, um sofort zu entscheiden.
# "sehr geehrte"/"mit freundlichen" sind dagegen generische deutsche
# Brief-Anrede/-Grußformeln -- jeder Brief (auch ein Laborbefund-Anschreiben
# eines Labors, ein Krankenkassenschreiben etc.) kann sie enthalten, sind
# also KEIN verlässliches Arztbrief-Signal und werden nur als Fallback
# geprüft, NACHDEM Labor-/Genetik-/Abrechnungs-Marker ausgeschlossen sind.
# "anamnese" ist noch schwächer (taucht auch in tabellarischen
# Leistungsübersichten mit vielen ICD-Codes auf), siehe
# ICD_DENSITY_ABRECHNUNG_THRESHOLD unten -- daher als letzter Fallback.
ARZTBRIEF_STRONG_MARKERS = ["epikrise"]
ARZTBRIEF_GENERIC_LETTER_MARKERS = ["sehr geehrte", "mit freundlichen"]
ARZTBRIEF_WEAK_MARKERS = ["anamnese"]
ICD_RE = re.compile(r"\b[A-Z][0-9]{2}\.[0-9]{1,2}\b")
ICD_DENSITY_ABRECHNUNG_THRESHOLD = 5  # ab so vielen ICD-Codes auf einer Seite: eher Abrechnung als Arztbrief
GENETIK_RE = re.compile(r"\brs\d{3,}\b|\bgenetisch\b|\bvariante\b|\ballel\b|\bmutation\b", re.IGNORECASE)
UEBERWEISUNG_RE = re.compile(
    r"\bverwendungszweck\b|\bbetrag in eur\b|\bkontoinhaber\b|\büberweisungstr(?:ä|ae)ger\b|\bzahlschein\b",
    re.IGNORECASE,
)
ABRECHNUNG_MARKERS = [
    "kostenübernahme", "leistungsdatum", "rechnungsdatum", "zahlung akz", "rechnungsbetrag",
    "leistungserbringer", "kostenträger", "genehmigt", "erstattung", "leistungsart",
    # Arznei-/Verbandmittel-Teilabschnitt (TP3) derselben Leistungsübersicht:
    # andere Feldlabel als der Diagnose-Teil (kein ICD, keine "genehmigt"/
    # "zahlung akz"-Vokabel), sonst faelschlich "unklar" statt abrechnung.
    # "verordnung" bewusst NICHT hier -- zu generisches Wort (kommt auch in
    # normalen Arztbriefen vor, z.B. "Verordnung von Physiotherapie").
    "apotheke", "pzn",
]
SONSTIGES_RE = re.compile(r"\beinwilligung\b|\bforschungsvorhaben\b|\beinverstaendnis", re.IGNORECASE)
# Format-basiertes statt begriffsbasiertes Laborbefund-Signal: manche Labore
# drucken gar kein "Endbefund"/"Referenzbereich"-Label, nur eine dichte
# Parameter/Wert/Einheit-Tabelle. Einzelne Parameternamen (Leukozyten, TSH, …)
# händisch aufzuzählen ist ein Fass ohne Boden -- die seltenen, eindeutigen
# Einheiten-Schreibweisen mit Schrägstrich (mg/dl, mmol/l, …) sind dagegen
# sprachlich fast nie zufällig und kommen auf einem echten Laborbefund in
# hoher Dichte vor (Testseite: 39x "mg/dl", 64x "g/dl").
LAB_UNIT_RE = re.compile(
    r"\bm?g/dl\b|\bn?mmol/l\b|\bµ?mol/l\b|\bn?pg/ml\b|\bng/ml\b|\bpmol/l\b|\bu/ml\b|\bu/l\b|\b/µl\b",
    re.IGNORECASE,
)
LAB_UNIT_DENSITY_THRESHOLD = 5  # ab so vielen Einheiten-Treffern auf einer Seite: eindeutig ein Laborbefund

OCR_GARBAGE_TOKEN_LEN = 40  # längster "Wort"-Lauf ohne Leerzeichen, ab dem wir OCR-Muell/Barcode annehmen
MIN_CONTENT_LEN = 60        # Seiten kuerzer als das: Trennblatt oder leer


def longest_token_len(s: str) -> int:
    return max((len(tok) for tok in s.split()), default=0)


def classify_page(norm_text: str, extra_lab_company_markers: list[str] | None = None) -> str:
    """Rule-based category for one page's normalized (whitespace-collapsed) text.

    extra_lab_company_markers: nutzerspezifische regionale Laborfirmen-Namen
    aus der lokalen Config (siehe LAB_COMPANY_MARKERS_BASE-Kommentar oben) --
    optional, damit die Funktion auch ohne Config (z. B. in Tests) nutzbar bleibt.
    """
    length = len(norm_text)
    tl = norm_text.lower()
    lab_company_markers = LAB_COMPANY_MARKERS_BASE + list(extra_lab_company_markers or [])

    if longest_token_len(norm_text) > OCR_GARBAGE_TOKEN_LEN or length < MIN_CONTENT_LEN:
        return "trennblatt_oder_ocr_muell"
    if any(k in tl for k in ARZTBRIEF_STRONG_MARKERS):
        return "arztbrief"
    if GENETIK_RE.search(tl):
        return "genetik"
    if SONSTIGES_RE.search(tl):
        return "sonstiges_dokument"

    # "Auftragsschlüssel" ist spezifisch genug, um sofort zu entscheiden,
    # unabhängig von allem anderen auf der Seite.
    if ANFORDERUNG_STRONG_RE.search(tl):
        return "laboranforderung"

    # Hohe ICD-Dichte VOR allen Labor-/Brief-Marken prüfen: eine einzelne
    # Labor-/Arztbrief-Seite listet praktisch nie Dutzende verschiedene ICD-
    # Codes, eine mehrjährige Krankenkassen-Leistungsübersicht dagegen schon --
    # und genau solche Seiten erwähnen beiläufig (als Name eines abgerechneten
    # Leistungserbringers, nicht weil die Seite selbst ein Laborbefund ist)
    # auch generische Labor-Fachbegriffe/-Rechtsformen, was sie sonst
    # fälschlich zu laborbefund gemacht hat.
    icd_count = len(ICD_RE.findall(norm_text))
    if any(k in tl for k in ABRECHNUNG_MARKERS) or icd_count >= ICD_DENSITY_ABRECHNUNG_THRESHOLD:
        return "abrechnung"

    is_lab_company = any(k in tl for k in lab_company_markers)
    is_lab_result = any(k in tl for k in LAB_RESULT_MARKERS)
    is_lab_unit_dense = len(LAB_UNIT_RE.findall(tl)) >= LAB_UNIT_DENSITY_THRESHOLD
    is_anforderung = bool(ANFORDERUNG_RE.search(tl))

    if is_anforderung and not (is_lab_result or is_lab_unit_dense):
        return "laboranforderung"
    if is_lab_company or is_lab_result or is_lab_unit_dense:
        return "laborbefund"
    if UEBERWEISUNG_RE.search(tl):
        return "ueberweisungstraeger"

    if any(k in tl for k in ARZTBRIEF_GENERIC_LETTER_MARKERS):
        return "arztbrief"
    if any(k in tl for k in ARZTBRIEF_WEAK_MARKERS):
        return "arztbrief"
    return "unklar"


CODE_OR_DATE_RE = re.compile(r"\b[a-z][0-9]{2}\.[0-9]{1,2}\b|\b\d{1,2}\.\d{1,2}\.\d{2,4}\b")


def tokenset(norm_text: str) -> set:
    """Wort-Shingles fuer die Jaccard-Dedup-Pruefung.

    ICD-Codes ("A00.0") und Daten ("01.02.2000") enthalten einen Punkt und
    wuerden von der reinen Wort-Regex an diesem Punkt zerschnitten (z.B.
    "a00"+"0"), wonach die einzelnen Teile meist unter der Mindestlaenge von
    4 Zeichen liegen und ganz wegfallen -- genau die Werte, die zwei fachlich
    UNTERSCHIEDLICHE Seiten einer sich wiederholenden Tabellenstruktur (z.B.
    eine mehrjaehrige Krankenkassen-Leistungsuebersicht) voneinander
    unterscheiden wuerden. Ohne sie dominieren die gemeinsamen Tabellen-
    Spaltenkoepfe die Jaccard-Berechnung, und inhaltlich verschiedene Seiten
    erscheinen faelschlich als Duplikate. Codes/Daten werden deshalb VOR der
    Wort-Tokenisierung als eigene, intakte Tokens erfasst.
    """
    tl = norm_text.lower()
    words = {tok for tok in re.findall(r"[a-zA-ZÄÖÜäöüß0-9]+", tl) if len(tok) >= 4}
    codes_and_dates = set(CODE_OR_DATE_RE.findall(tl))
    return words | codes_and_dates


def extract_pages(pdf_path: Path) -> list[str]:
    """Return one normalized text string per page via pdftotext (poppler-utils)."""
    result = subprocess.run(
        ["pdftotext", str(pdf_path), "-"],
        capture_output=True, text=True, check=True,
    )
    raw_pages = result.stdout.split("\f")
    if raw_pages and raw_pages[-1].strip() == "":
        raw_pages = raw_pages[:-1]
    return [re.sub(r"\s+", " ", p).strip() for p in raw_pages]


def looks_unocred(pages: list[str]) -> bool:
    """Heuristic: if almost every page is empty/near-empty, OCR probably wasn't run."""
    if not pages:
        return True
    empty = sum(1 for p in pages if len(p) < MIN_CONTENT_LEN)
    return empty / len(pages) > 0.9


class UnionFind:
    def __init__(self, n: int):
        self.parent = list(range(n))

    def find(self, x: int) -> int:
        while self.parent[x] != x:
            x = self.parent[x]
        return x

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[ra] = rb


def fuzzy_dedup(pages: list[dict], threshold: float) -> dict:
    """Group pages by near-duplicate content (same category + similar length
    + Jaccard token overlap >= threshold). Returns {root_index: [indices]}.

    Seiten mit ICD-Codes/Daten (siehe tokenset()) brauchen ZUSAETZLICH eine
    ausreichende Code/Datum-Ueberlappung, nicht nur Gesamt-Jaccard -- sonst
    werden inhaltlich verschiedene Zeilen einer sich wiederholenden
    Tabellenvorlage (z.B. eine mehrjaehrige Krankenkassen-Leistungsuebersicht
    mit vielen Zeilen pro Seite, aber je Seite anderen Diagnosen/Daten)
    faelschlich als Duplikate zusammengefasst, weil die gemeinsamen
    Spaltenkoepfe/Fachbegriffe allein schon nahe an die Schwelle kommen.
    """
    n = len(pages)
    uf = UnionFind(n)
    for i in range(n):
        if not pages[i]["tokens"]:
            continue
        for j in range(i + 1, n):
            if pages[i]["category"] != pages[j]["category"]:
                continue
            if not pages[j]["tokens"]:
                continue
            li, lj = pages[i]["length"], pages[j]["length"]
            if li == 0 or lj == 0 or abs(li - lj) / max(li, lj) > 0.30:
                continue
            inter = pages[i]["tokens"] & pages[j]["tokens"]
            union_set = pages[i]["tokens"] | pages[j]["tokens"]
            jaccard = len(inter) / len(union_set) if union_set else 0.0
            if jaccard < threshold:
                continue
            cd_i, cd_j = pages[i].get("code_date_tokens", set()), pages[j].get("code_date_tokens", set())
            if cd_i or cd_j:
                cd_union = cd_i | cd_j
                cd_jaccard = len(cd_i & cd_j) / len(cd_union) if cd_union else 0.0
                if cd_jaccard < threshold:
                    continue
            uf.union(i, j)
    groups: dict[int, list[int]] = {}
    for idx in range(n):
        groups.setdefault(uf.find(idx), []).append(idx)
    return groups


NEAR_EMPTY_GAP_LEN = 400  # "unklar"-Seiten unter dieser Laenge gelten als zu inhaltsarm fuer eine eigene Einstufung


def fill_near_empty_gaps(file_pages: list[dict], keep_mask: list[bool]) -> None:
    """Mutiert category in place: eine als 'unklar' eingestufte, sehr kurze
    Seite (z.B. eine fast leere Zwischen-/Unterschriftsseite innerhalb eines
    mehrseitigen Berichts, OHNE eigene Werte/Marker) wird derselben Kategorie
    zugeordnet wie die UNMITTELBAR angrenzenden Seiten, wenn beide Nachbarn
    (nach Dedup, in echter Seitenfolge) dieselbe, eindeutige Kategorie haben.
    Verhindert, dass ein inhaltsarmer Zwischenfall ein zusammenhaengendes
    Dokument unnoetig in zwei Teile zerreisst."""
    kept_indices = [i for i, k in enumerate(keep_mask) if k]
    for pos, i in enumerate(kept_indices):
        pg = file_pages[i]
        if pg["category"] != "unklar" or pg["length"] >= NEAR_EMPTY_GAP_LEN:
            continue
        if pos == 0 or pos == len(kept_indices) - 1:
            continue
        prev_pg = file_pages[kept_indices[pos - 1]]
        next_pg = file_pages[kept_indices[pos + 1]]
        if (prev_pg["category"] == next_pg["category"]
                and prev_pg["category"] not in ("unklar", "trennblatt_oder_ocr_muell")
                and prev_pg["page"] == pg["page"] - 1
                and next_pg["page"] == pg["page"] + 1):
            pg["category"] = prev_pg["category"]


def merge_adjacent_weak_lab_unit_pages(file_pages: list[dict], keep_mask: list[bool]) -> None:
    """Mutiert category in place: ein Laborbefund, der sich über mehrere
    Seiten verteilt (z.B. ein Allergie-Panel mit wenigen Analyten pro Seite),
    muss auf KEINER einzelnen Seite für sich die Einheiten-Dichte-Schwelle
    erreichen -- nur in Summe über zusammenhängende, jeweils schwach
    positive 'unklar'-Seiten. Verhindert, dass ein auf zwei schwache Seiten
    aufgeteilter Bericht komplett unter die Schwelle faellt, ohne die
    Schwelle selbst global abzusenken (das würde anderswo echte Arztbrief-
    Seiten mit nur beiläufiger Einheiten-Erwähnung faelschlich zu
    laborbefund machen, siehe ARZTBRIEF_WEAK_MARKERS-Kommentar oben)."""
    kept_indices = [i for i, k in enumerate(keep_mask) if k]
    pos = 0
    while pos < len(kept_indices):
        i = kept_indices[pos]
        pg = file_pages[i]
        if pg["category"] != "unklar" or pg["lab_unit_hits"] < 1:
            pos += 1
            continue
        run = [i]
        look = pos + 1
        while look < len(kept_indices):
            j = kept_indices[look]
            nxt = file_pages[j]
            if (nxt["category"] == "unklar" and nxt["lab_unit_hits"] >= 1
                    and nxt["page"] == file_pages[run[-1]]["page"] + 1):
                run.append(j)
                look += 1
            else:
                break
        if len(run) >= 2 and sum(file_pages[k]["lab_unit_hits"] for k in run) >= LAB_UNIT_DENSITY_THRESHOLD:
            for k in run:
                file_pages[k]["category"] = "laborbefund"
        pos = look if look > pos + 1 else pos + 1


def group_consecutive(pages: list[dict], keep_mask: list[bool]) -> list[dict]:
    """Within one source file, group consecutive kept pages of the same
    category into logical documents (contiguous runs). Pages not kept
    (duplicates, or category = trennblatt_oder_ocr_muell) break a run."""
    docs = []
    current = None
    for idx, pg in enumerate(pages):
        if not keep_mask[idx] or pg["category"] == "trennblatt_oder_ocr_muell":
            if current:
                docs.append(current)
                current = None
            continue
        if current and current["category"] == pg["category"] and pg["page"] == current["pages"][-1] + 1:
            current["pages"].append(pg["page"])
        else:
            if current:
                docs.append(current)
            current = {"category": pg["category"], "pages": [pg["page"]], "file": pg["file"]}
    if current:
        docs.append(current)
    return docs


def split_pdf(source_pdf: Path, page_numbers: list[int], out_path: Path) -> None:
    import pikepdf
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with pikepdf.open(source_pdf) as src:
        dst = pikepdf.Pdf.new()
        for p in page_numbers:
            dst.pages.append(src.pages[p - 1])  # 1-indexed in our bookkeeping
        dst.save(out_path)


def main() -> None:
    parser = argparse.ArgumentParser(description=t(
        "Sortiert einen gescannten, OCR'ten Dokumentstapel nach Typ und entfernt Fast-Duplikate",
        "Sorts a scanned, OCR'd document batch by type and removes near-duplicates",
    ))
    parser.add_argument("--file", nargs="+", required=True, type=Path, help=t(
        "Eine oder mehrere OCR'te PDF-Dateien", "One or more OCR'd PDF files"))
    parser.add_argument("--out-dir", type=Path, default=None, help=t(
        "Ausgabeverzeichnis (Default: <Ordner der ersten Datei>/sortiert/)",
        "Output directory (default: <first file's folder>/sortiert/)"))
    parser.add_argument("--similarity-threshold", type=float, default=0.45, help=t(
        "Jaccard-Schwelle für Fast-Duplikat-Erkennung, 0-1 (Default 0.45, bewusst locker wegen OCR-Rauschen)",
        "Jaccard threshold for near-duplicate detection, 0-1 (default 0.45, deliberately loose due to OCR noise)"))
    add_lang_arg(parser)
    args = parser.parse_args()
    apply_lang_from_args(args)

    out_dir = args.out_dir or (args.file[0].parent / "sortiert")
    out_dir.mkdir(parents=True, exist_ok=True)

    extra_lab_markers = Config().extra_lab_company_markers
    all_pages: list[dict] = []
    for fpath in args.file:
        page_texts = extract_pages(fpath)
        if looks_unocred(page_texts):
            print(t(
                f"FEHLER: {fpath.name} sieht nicht OCR't aus (fast nur leere Seiten). "
                f"Bitte zuerst 'ocrmypdf --skip-text {fpath.name} {fpath.stem}_ocr.pdf' laufen lassen.",
                f"ERROR: {fpath.name} doesn't look OCR'd (almost all pages empty). "
                f"Run 'ocrmypdf --skip-text {fpath.name} {fpath.stem}_ocr.pdf' first.",
            ))
            sys.exit(1)
        for i, norm in enumerate(page_texts, 1):
            all_pages.append({
                "idx": len(all_pages), "file": fpath, "page": i, "norm": norm,
                "length": len(norm), "category": classify_page(norm, extra_lab_markers), "tokens": tokenset(norm),
                "code_date_tokens": set(CODE_OR_DATE_RE.findall(norm.lower())),
                "lab_unit_hits": len(LAB_UNIT_RE.findall(norm.lower())),
            })

    groups = fuzzy_dedup(all_pages, args.similarity_threshold)
    keep_mask = [True] * len(all_pages)
    dup_report_lines = []
    for root, members in groups.items():
        if len(members) <= 1:
            continue
        canonical = members[0]
        for m in members[1:]:
            keep_mask[m] = False
        dup_report_lines.append(
            f"DUPLIKAT-GRUPPE: behalten={all_pages[canonical]['file'].name}:S{all_pages[canonical]['page']}"
            f"  verworfen=" + ", ".join(
                f"{all_pages[m]['file'].name}:S{all_pages[m]['page']}" for m in members[1:]
            )
        )

    report_lines = [t("=== Duplikate ===", "=== Duplicates ===")]
    report_lines.extend(dup_report_lines or [t("(keine gefunden)", "(none found)")])
    report_lines.append("")
    report_lines.append(t("=== Dokumente ===", "=== Documents ==="))

    cat_counts = Counter()
    edge_case_notes = []

    for fpath in args.file:
        file_pages = [p for p in all_pages if p["file"] == fpath]
        file_mask = [keep_mask[p["idx"]] for p in file_pages]
        merge_adjacent_weak_lab_unit_pages(file_pages, file_mask)
        fill_near_empty_gaps(file_pages, file_mask)
        docs = group_consecutive(file_pages, file_mask)
        total_pages_in_file = len(file_pages)
        for doc in docs:
            cat = doc["category"]
            cat_counts[cat] += 1
            page_range = doc["pages"]
            is_edge = page_range[0] == 1 or page_range[-1] == total_pages_in_file
            if is_edge:
                edge_case_notes.append(
                    f"{fpath.stem} S{page_range[0]}-{page_range[-1]} ({cat}): "
                    + t("liegt am Dateirand — ggf. Fortsetzung in Nachbardatei pruefen",
                        "sits at file edge — may continue in a neighboring file")
                )
            if cat in ("trennblatt_oder_ocr_muell",):
                continue  # kein Output nötig, ist leer/Rauschen
            cat_dir = out_dir / cat
            out_name = f"{fpath.stem}_S{page_range[0]:03d}-{page_range[-1]:03d}.pdf"
            out_path = cat_dir / out_name
            split_pdf(fpath, page_range, out_path)
            report_lines.append(
                f"[{cat:25s}] {out_path.relative_to(out_dir)}  "
                f"(Quelle: {fpath.name} S{page_range[0]}-{page_range[-1]}, "
                f"naechster Schritt: {CATEGORIES_NEXT_STEP.get(cat, '?')})"
            )

    report_lines.append("")
    report_lines.append(t("=== Randfaelle (an Dateigrenze) ===", "=== Edge cases (at file boundary) ==="))
    report_lines.extend(edge_case_notes or [t("(keine)", "(none)")])

    report_path = out_dir / "sortierung_bericht.txt"
    report_path.write_text("\n".join(report_lines), encoding="utf-8")

    print(t("Fertig.", "Done."))
    print(t(f"Ergebnis liegt in: {out_dir}", f"Result is in: {out_dir}"))
    print(t(f"Bericht: {report_path}", f"Report: {report_path}"))


if __name__ == "__main__":
    main()
