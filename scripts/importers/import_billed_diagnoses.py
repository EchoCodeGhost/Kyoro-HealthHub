#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Abgerechnete Diagnosen- und Medikamentenhistorie (ICD-10 + Apotheken-Verordnungen, OCR-Scan) → medicine.db

@tier        infrastructure
@purpose.de  Extrahiert ICD-10-codierte Diagnoseeinträge UND Apotheken-
             Verordnungsblöcke aus einer OCR'ten Krankenkassen-/Leistungs-
             träger-Übersicht (gescannt + ocrmypdf) und importiert sie
             zweistufig (Extraktion → menschliche Review → Commit) in die
             bestehenden Tabellen diagnoses bzw. medications.
@purpose.en  Extracts ICD-10-coded entries AND pharmacy
             prescription blocks from an OCR'd health-insurer benefits
             overview (scanned + ocrmypdf) and imports them in two stages
             (extraction → human review → commit) into the existing
             diagnoses resp. medications tables.
@method.de   Stufe 1 (--extract): liest .txt oder .pdf (via pdftotext), findet
             ICD-10-Codes per Regex sowie Apotheke/PZN/Verordnung-Anker,
             ordnet Datum/Code/Diagnosetext bzw. PZN/Präparatname per
             Zeilenfenster- und Typ-Heuristik zu (Label-Reihenfolge im OCR-
             Text ist nicht verlässlich fest). Diagnosen werden oft als
             Beginn/Ende-Zeitraum abgerechnet, Medikamente haben separate
             Verordnungs-/Abgabedaten -- find_date_candidates() sucht daher
             nach ZWEI Label-Typen parallel (beginn/ende bzw. verordnung/
             abgabe) und choose_date() wählt pro Label-Typ unabhängig.
             Uneindeutige Fälle gehen NUR
             mit --llm-fallback an ein AUSSCHLIESSLICH LOKALES LLM (openvino/
             ovms/ollama/lmstudio/llamacpp/exo/mlx — Cloud-Provider werden
             hart abgelehnt). Ohne --llm-fallback (Standard) werden
             uneindeutige Fälle NICHT ans LLM gegeben, sondern direkt mit
             niedriger certainty als Kandidat markiert — bewusste Abweichung
             vom ursprünglichen Plan, weil die auf dieser Maschine verfügbaren
             lokalen LLMs bei diesem Dokumentumfang (hunderte Treffer) zu
             langsam für einen Vollauf sind; kein Treffer wird dadurch
             verworfen, nur die automatische Klärung ausgelassen. Bei
             Diagnosen fragt der LLM-Fallback-Prompt zusätzlich nach dem
             korrekten ICD-10-Code (OCR verwechselt gelegentlich Ziffern/
             Buchstaben, z.B. "O" statt "0") -- ein abweichender, aber
             regex-valider Code überschreibt den per Anker gefundenen Code.
             Bei beiden Typen fragt der Prompt zusätzlich nach einer knappen
             Fundstelle (Label/Nachbarzeile), damit ein Mensch die Stelle im
             Originaldokument wiederfindet. certainty=0.6-Einträge tragen
             deshalb in notes: Seitenzahl, diese Fundstelle (falls vom LLM
             geliefert) sowie den kompletten rohen OCR-Fensterausschnitt, der
             dem LLM vorlag -- nicht nur ein "LLM war beteiligt"-Vermerk,
             sondern die Grundlage, auf der das LLM seine Werte erkannt hat,
             damit die Review-Entscheidung ohne Rückgriff auf das
             Originaldokument möglich ist. Stufe 2
             (--commit) liest die (ggf. von Hand korrigierte) Kandidaten-JSON
             und schreibt jeden Eintrag in die per "table" angegebene
             Zieltabelle. Der rohe Scanner-Dateiname (kann Geräte-/Batch-/
             Zeitstempel-Kennungen enthalten) wird vor dem Schreiben in die
             Kandidaten-JSON über identity_resolver.resolve_sourcefile()
             pseudonymisiert, nie im Klartext gespeichert.
@method.en   Stage 1 (--extract): reads .txt or .pdf (via pdftotext), finds
             ICD-10 codes via regex as well as Apotheke/PZN/Verordnung
             anchors, assigns date/code/descriptive text resp. PZN/drug name
             via a line-window and type-based heuristic (label order in the
             OCR text is not reliably fixed). Diagnoses are often billed as
             a start/end period, medications have separate prescription/
             dispensing dates -- find_date_candidates() looks for TWO label
             types in parallel (beginn/ende resp. verordnung/abgabe) and
             choose_date() picks independently per label type. Ambiguous
             cases only go to an
             EXCLUSIVELY LOCAL LLM (openvino/ovms/ollama/lmstudio/llamacpp/
             exo/mlx — cloud providers are hard-rejected) if --llm-fallback
             is passed. Without --llm-fallback (default), ambiguous cases
             are NOT sent to an LLM — they're marked as a low-certainty
             candidate directly. Deliberate deviation from the original
             plan: the local LLMs available on this machine are too slow
             for a full run at this document's scale (hundreds of matches);
             no match is discarded, only the automatic disambiguation step
             is skipped. For diagnoses, the LLM-fallback prompt additionally
             asks for the correct ICD-10 code (OCR occasionally confuses
             digits/letters, e.g. "O" for "0") -- a different but regex-valid
             code overrides the one found by the anchor. For both types, the
             prompt also asks for a brief location hint (label/neighboring
             line) so a human can relocate the spot in the original
             document. certainty=0.6 entries therefore carry in notes: the
             page number, that location hint (if the LLM supplied one), and
             the full raw OCR window excerpt the LLM was given -- not just a
             "LLM was involved" remark, but the material the LLM based its
             values on, so the review decision is possible without going
             back to the original document. Stage 2 (--commit) reads the
             (possibly hand-corrected) candidate JSON and writes each entry
             to the table named by "table". The raw scanner filename (which
             may embed a device/batch/timestamp identifier) is pseudonymized
             via identity_resolver.resolve_sourcefile() before being written
             to the candidate JSON, never stored in cleartext.
@thresholds
    certainty = 0.9 (diagnoses) :: de=Datum+Text+kein Nachbar-Code eindeutig -- status=confirmed, ohne LLM :: en=date+text+no neighboring code unambiguous -- status=confirmed, without LLM
    certainty = 0.7 (medications) :: de=Datum+Präparatname+kein Nachbar-PZN eindeutig -- status=confirmed, ohne LLM :: en=date+drug name+no neighboring PZN unambiguous -- status=confirmed, without LLM
    certainty = 0.6 :: de=uneindeutig, aber --llm-fallback lieferte einen Wert -- status=needs_review, notes enthält Fundstelle+OCR-Original :: en=ambiguous, but --llm-fallback supplied a value -- status=needs_review, notes contains location+original OCR
    certainty = 0.3 :: de=uneindeutig und (ohne --llm-fallback ODER auch vom LLM) nicht klärbar -- status=needs_review :: en=ambiguous and unresolved (without --llm-fallback OR even by the LLM) -- status=needs_review
@reads       diagnoses, medications (für Duplikat-Vermeidung via UNIQUE-/
             PRIMARY-KEY-Constraint, nur Stufe 2)
@writes      imports/manual/billed_diagnoses_candidates.json (Stufe 1; "source_file"
             enthält bereits das Pseudonym, nicht den rohen Scanner-Dateinamen
             -- siehe identity_resolver.resolve_sourcefile());
             diagnoses: date TEXT (Beginn), date_to TEXT (Ende, meist NULL --
             siehe @limits), icd_code TEXT, description TEXT, status TEXT,
             certainty REAL, source TEXT, notes TEXT, provider_pseudonym TEXT
             (via scripts/modules/provider_scrubbing.py);
             medications: ts TEXT, date TEXT (Verordnung), date_abgabe TEXT
             (Abgabe, meist NULL -- siehe @limits), medication_id TEXT,
             drug_name TEXT, is_chronic INTEGER, source TEXT, notes TEXT,
             prescriber_pseudonym TEXT (Verordner-Nummer, ebenfalls über
             identity_resolver pseudonymisiert statt im Klartext behalten)
             (Stufe 2)
@limits.de   Leistungserbringer wird nur pseudonymisiert übernommen
             (provider_pseudonym), nicht im Klartext, und nur so präzise wie
             scrub_provider_text()'s Registry/Heuristiken — ein unbekannter
             Name ohne Titel/Adresse bleibt unerkannt (NULL). Keine
             Kosten-Spalte bei Diagnosen. date_to/date_abgabe werden nur
             gefüllt, wenn ein "Ende"-/"Abgabe"-Label eindeutig in der Nähe
             steht ODER das LLM-Fallback sie liefert -- die Label-Wörter
             selbst sind in diesem Dokumenttyp seltene Spaltenköpfe (ca. 1 pro
             30 Einträge), kein Pro-Eintrag-Marker, daher bleiben beide Felder
             beim deterministischen Pass fast immer NULL. Bei Medikamenten
             keine Dosierungsangabe im Quelldokument vorhanden (dose_value/
             dose_unit/route bleiben NULL). OCR-Fehler in Codes/PZN werden
             nur korrigiert, wenn --llm-fallback lief UND das LLM einen
             regex-validen abweichenden Wert zurückgab (icd_code bei
             Diagnosen, medication_id bei Medikamenten) -- ohne
             --llm-fallback oder bei einem vom LLM nicht erkannten Fehler
             bleibt der per Regex-Anker gefundene (ggf. fehlerhafte) Wert
             stehen. Dubletten-Schutz bei medications nur über (ts, person, source).
             Ohne --llm-fallback bleiben alle uneindeutigen Faelle auf
             certainty=0.3/needs_review stehen, auch wenn ein LLM sie
             theoretisch hätte klären können — das ist Absicht (siehe
             @method), keine Einschränkung, die händisches Prüfen ersetzen
             könnte.
@limits.en   The treating provider is only kept pseudonymized
             (provider_pseudonym), never in cleartext, and only as
             precisely as scrub_provider_text()'s registry/heuristics
             allow — an unknown name without a title/address stays
             unresolved (NULL). No cost column for diagnoses. date_to/
             date_abgabe are only filled when an "Ende"/"Abgabe" label sits
             unambiguously nearby OR the LLM fallback supplies them -- in
             this document type those label words are rare column headers
             (roughly 1 per 30 entries), not a per-entry marker, so both
             fields stay NULL for almost all deterministically-resolved
             entries. For medications, no dosage is present in the source
             document (dose_value/dose_unit/route stay NULL). OCR errors in
             codes/PZN are only corrected if --llm-fallback ran AND the LLM
             returned a regex-valid differing value (icd_code for
             diagnoses, medication_id for medications) -- without
             --llm-fallback, or when the LLM also misses the error, the
             (possibly wrong) regex-anchored value stands. Duplicate
             protection for medications relies only on
             (ts, person, source). Without --llm-fallback, all ambiguous
             cases stay at certainty=0.3/needs_review even though an LLM
             could in principle resolve some of them — this is deliberate
             (see @method), not a limitation a human review pass should
             skip.

@relevance.de  Ermöglicht den Import einer jahrzehntelangen, gescannten Diagnose- und Medikamentenhistorie, essentiell für eine lückenlose Krankengeschichte
@relevance.en  Enables import of a decades-long, scanned ICD-10-coded and medication history, essential for a complete medical history
@usage
    python3 import_billed_diagnoses.py --extract --file /pfad/zur/datei.txt
    python3 import_billed_diagnoses.py --extract --file /pfad/zur/datei.pdf
    python3 import_billed_diagnoses.py --extract --file /pfad/zur/datei.pdf --llm-fallback
    python3 import_billed_diagnoses.py --commit
    python3 import_billed_diagnoses.py --commit --file imports/manual/andere_kandidaten.json
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))
from health_config import Config as _Cfg  # noqa: E402
from modules.base import log_import, resolve_person  # noqa: E402
from modules.db import open_medicine_db  # noqa: E402
from modules.i18n import t, add_lang_arg, apply_lang_from_args  # noqa: E402
from modules.llm import call_llm_importer_only  # noqa: E402
from modules.provider_scrubbing import scrub_provider_text  # noqa: E402
from modules.identity_resolver import resolve_provider, resolve_sourcefile  # noqa: E402
from modules.patient_scrubbing import scrub_patient_identity  # noqa: E402
from modules.review_notes import build_ocr_note  # noqa: E402
from modules import icd10_catalog  # noqa: E402

_cfg = _Cfg()
DEFAULT_CANDIDATES_PATH = _cfg.data_root / "manual" / "billed_diagnoses_candidates.json"

ICD_RE = re.compile(r"\b[A-Z][0-9]{2}\.[0-9]{1,2}(?:[AGVZ][BLR]?)?\b")
# Manche Leistungsübersichten (z.B. die Krankenkassen-Auskunft, nicht die
# Arztbrief-Variante) hängen das KBV-Diagnosesicherheits-/Seitenkennzeichen
# ohne Trenner direkt an den Code (z.B. "A00.0G", "A00.0V", "A00.0GR") --
# ICD_RE muss das miterfassen, sonst matcht \b nach den Ziffern nicht und
# der Code wird gar nicht gefunden (gefundener Fall: 0 Treffer auf einer
# Datei, die dutzende Codes enthielt). Gruppe 1 ist der reine ICD-10-GM-Code
# (für den Katalog-Check/icd10_catalog.py), Gruppe 2 das optionale
# Kennzeichen -- siehe KBV_CERTAINTY_LABELS für die Bedeutung.
ICD_CODE_RE = re.compile(r"\b([A-Z][0-9]{2}\.[0-9]{1,2})([AGVZ][BLR]?)?\b")
KBV_CERTAINTY_LABELS = {"G": "gesichert", "V": "Verdacht auf", "A": "ausgeschlossen", "Z": "Zustand nach"}
KBV_LATERALITY_LABELS = {"B": "beidseitig", "L": "links", "R": "rechts"}
DATE_RE = re.compile(r"\b\d{2}\.\d{2}\.\d{4}\b")
PZN_RE = re.compile(r"\b\d{6,8}\b")


def _decode_kbv_marker(marker: str | None) -> str | None:
    """Klartext für ein KBV-Zusatzkennzeichen wie "G", "V", "GR", "ZL" --
    None, wenn kein Kennzeichen vorhanden war (ältere Dokumentvarianten ohne
    dieses Suffix)."""
    if not marker:
        return None
    certainty = KBV_CERTAINTY_LABELS.get(marker[0])
    laterality = KBV_LATERALITY_LABELS.get(marker[1]) if len(marker) > 1 else None
    if certainty and laterality:
        return f"{certainty} ({laterality})"
    return certainty or marker

# Tabellenköpfe/Label-Zeilen, die bei der Freitext-Suche als Rauschen
# überzuspringen sind -- erscheinen als eigene Zeile im OCR-Text.
KNOWN_LABELS = {
    "icd", "a icd", "diagnose", "kosten", "status", "leistungserbringer",
    "beginn", "ende", "tage", "genehmigt",
    "apotheke", "pzn", "verordnung", "verordner", "zuzahlung",
}

# Deutsches Institutionskennzeichen (IK, 9-stellig) -- identifiziert z.B. die
# abgebende Apotheke. Anders als die Verordner-Nummer (identifiziert einen
# Arzt, wird pseudonymisiert) ist das IK selbst nicht erhaltenswert -- wird
# komplett entfernt statt pseudonymisiert.
IK_RE = re.compile(r"\b\d{9}\b")

ICD_WINDOW_BACK = 400  # Dokument-Realität: ein Datum koepft oft einen Block vieler
                       # nachfolgender Codes -- 15 Zeilen waren bei der Testung an
                       # echten Daten zu knapp (viele fanden gar kein Datum,
                       # obwohl eines existierte, nur weiter weg)
ICD_WINDOW_FWD = 5
ICD_NEIGHBOR_MIN_DIST = 3
MED_WINDOW = 10

_ICD_FALLBACK_PROMPT_DE = (
    "Du bekommst einen Zeilenausschnitt aus einer OCR'ten Krankenkassen-"
    "Leistungsübersicht. Darin steht (laut Regex-Fund) der ICD-10-Code "
    "{icd_code}, aber Datum und/oder Diagnosetext sind nicht sicher "
    "zuordenbar. Diagnosen werden oft als Zeitraum (Beginn/Ende) "
    "abgerechnet. Finde das am ehesten zu diesem Code gehörende "
    "Beginn-Datum UND, falls vorhanden, das Ende-Datum (jeweils Format "
    "TT.MM.JJJJ), den Diagnosetext, sowie -- da OCR Ziffern/Buchstaben in "
    "Codes verwechseln kann (z.B. O statt 0) -- den korrekten ICD-10-Code, "
    "falls er von {icd_code} abweicht. Gib außerdem knapp an, WO im "
    "Ausschnitt du das gefunden hast (z.B. nahe welchem Label oder "
    "welcher Nachbarzeile), damit ein Mensch die Stelle im Originaldokument "
    "wiederfindet.\n\n"
    'Gib NUR ein JSON-Objekt zurück: {{"date": "TT.MM.JJJJ" oder null, '
    '"date_to": "TT.MM.JJJJ" oder null (nur falls ein Ende-Datum erkennbar '
    'ist), "description": "Text" oder null, "icd_code": "Code" oder null '
    '(nur falls abweichend von {icd_code}), "fundstelle": "kurzer Hinweis" '
    'oder null}}. Wenn du nichts Sicheres findest, gib null zurück.'
)
_ICD_FALLBACK_PROMPT_EN = (
    "You get a line excerpt from an OCR'd health-insurer benefits overview. "
    "It contains (per a regex match) the ICD-10 code {icd_code}, but the "
    "date and/or diagnosis text can't be confidently assigned. Diagnoses "
    "are often billed as a period (start/end). Find the start date most "
    "likely belonging to this code AND, if present, the end date (format "
    "DD.MM.YYYY each), the diagnosis text, and -- since OCR can confuse "
    "digits/letters in codes (e.g. O for 0) -- the correct ICD-10 code, if "
    "it differs from {icd_code}. Also briefly state WHERE in the excerpt "
    "you found this (e.g. near which label or neighboring line), so a "
    "human can relocate the spot in the original document.\n\n"
    'Return ONLY a JSON object: {{"date": "DD.MM.YYYY" or null, "date_to": '
    '"DD.MM.YYYY" or null (only if an end date is identifiable), '
    '"description": "text" or null, "icd_code": "code" or null (only if '
    'different from {icd_code}), "location": "short hint" or null}}. If '
    "you find nothing certain, return null."
)
_MED_FALLBACK_PROMPT_DE = (
    "Du bekommst einen Zeilenausschnitt aus einer OCR'ten Krankenkassen-"
    "Leistungsübersicht, Abschnitt Arznei-/Verbandmittel. Finde die PZN "
    "(Pharmazentralnummer, 6-8-stellige Zahl), das Verordnungsdatum UND, "
    "falls vorhanden, das Abgabedatum (jeweils Format TT.MM.JJJJ, beide "
    "stehen oft dicht beieinander) sowie den Präparatnamen. Gib außerdem "
    "knapp an, WO im Ausschnitt du das gefunden hast (z.B. nahe welchem "
    "Label oder welcher Nachbarzeile), damit ein Mensch die Stelle im "
    "Originaldokument wiederfindet.\n\n"
    'Gib NUR ein JSON-Objekt zurück: {{"date": "TT.MM.JJJJ" oder null '
    '(Verordnungsdatum), "date_abgabe": "TT.MM.JJJJ" oder null (nur falls '
    'erkennbar), "medication_id": "PZN" oder null, "drug_name": "Text" '
    'oder null, "fundstelle": "kurzer Hinweis" oder null}}.'
)
_MED_FALLBACK_PROMPT_EN = (
    "You get a line excerpt from an OCR'd health-insurer benefits overview, "
    "pharmacy/medication section. Find the PZN (German drug product code, "
    "6-8 digit number), the prescription date AND, if present, the "
    "dispensing date (format DD.MM.YYYY each, often close together), and "
    "the drug name. Also briefly state WHERE in the excerpt you found this "
    "(e.g. near which label or neighboring line), so a human can relocate "
    "the spot in the original document.\n\n"
    'Return ONLY a JSON object: {{"date": "DD.MM.YYYY" or null '
    '(prescription date), "date_abgabe": "DD.MM.YYYY" or null (only if '
    'identifiable), "medication_id": "PZN" or null, "drug_name": "text" or '
    'null, "location": "short hint" or null}}.'
)


def read_lines(path: Path) -> tuple[list[str], list[int]]:
    """Liefert (lines, page_of_line) -- pdftotext trennt Seiten mit einem
    Form-Feed-Zeichen ("\\f"); dieses NICHT verwerfen, sondern als Seiten-
    grenze auswerten, damit Kandidaten später per Seitenzahl statt per für
    Menschen unauffindbarer Zeilennummer im Fließtext referenziert werden
    können ("Zeile 9802" sagt niemandem etwas bei einem 27-seitigen PDF)."""
    if path.suffix.lower() == ".pdf":
        result = subprocess.run(["pdftotext", str(path), "-"], capture_output=True, text=True, check=True)
        text = result.stdout
    else:
        text = path.read_text(encoding="utf-8", errors="replace")
    lines: list[str] = []
    page_of_line: list[int] = []
    for page_num, page_text in enumerate(text.split("\f"), start=1):
        page_lines = page_text.splitlines()
        lines.extend(page_lines)
        page_of_line.extend([page_num] * len(page_lines))
    return lines, page_of_line


def is_noise_line(line: str) -> bool:
    s = line.strip().lower()
    return s == "" or s in KNOWN_LABELS


def find_date_candidates(
    lines: list[str], idx: int, max_back: int,
    primary_label: str = "beginn", secondary_label: str | None = None,
) -> list[tuple[str, int, bool, bool]]:
    """(date_str, line_idx, has_primary_label_nearby, has_secondary_label_nearby)
    für alle Datumstreffer bis zu max_back Zeilen vor idx. Diagnosen haben
    Beginn/Ende-Zeiträume, Medikamente Verordnung/Abgabe-Daten -- dasselbe
    Zwei-Datums-Muster, nur mit anderen Label-Wörtern; secondary_label=None
    deaktiviert die zweite Prüfung (immer False)."""
    out = []
    start = max(0, idx - max_back)
    for j in range(idx - 1, start - 1, -1):
        m = DATE_RE.search(lines[j])
        if m:
            has_primary = any(lines[k].strip().lower() == primary_label for k in range(max(0, j - 2), j))
            has_secondary = bool(secondary_label) and any(
                lines[k].strip().lower() == secondary_label for k in range(max(0, j - 2), j)
            )
            out.append((m.group(0), j, has_primary, has_secondary))
    return out


def choose_date(
    candidates: list[tuple[str, int, bool, bool]], flag_index: int = 2, fallback_to_nearest: bool = True,
) -> tuple[str | None, bool]:
    """Wählt das wahrscheinlichste Datum nach dem Label-Flag an flag_index
    (2 = primary/Beginn/Verordnung, 3 = secondary/Ende/Abgabe);
    (date_or_None, is_unambiguous). fallback_to_nearest=False (für
    secondary/date_to/date_abgabe): OHNE eindeutiges Label-Match bleibt das
    Ergebnis None, statt auf das nächstgelegene Datum zu raten -- sonst
    würde date_to/date_abgabe faelschlich IMMER denselben Wert wie das
    Primärdatum annehmen (identischer Fallback-Mechanismus, gleiche
    Kandidatenliste), was ein Ende-/Abgabedatum vorgaukelt, das gar nicht
    erkannt wurde."""
    if not candidates:
        return None, False
    labeled_dates = sorted({c[0] for c in candidates if c[flag_index]})
    if len(labeled_dates) == 1:
        return labeled_dates[0], True
    distinct = sorted({c[0] for c in candidates})
    if len(distinct) == 1:
        return distinct[0], True
    if not fallback_to_nearest:
        return None, False
    # mehrdeutig: nächstgelegenes Datum als bester Schätzwert, aber als unsicher
    # markiert -- find_date_candidates() haengt rueckwaerts von idx-1 abwaerts ab,
    # candidates[0] ist also bereits das naechstgelegene (kleinste Distanz zu idx)
    return candidates[0][0], False


def find_text_forward(lines: list[str], idx: int, max_fwd: int) -> tuple[str, bool]:
    """Erster Freitext-Block nach idx; (text, found)."""
    j = idx + 1
    scanned = 0
    while j < len(lines) and scanned < max_fwd:
        line = lines[j].strip()
        if is_noise_line(line) or DATE_RE.fullmatch(line) or ICD_RE.fullmatch(line):
            j += 1
            scanned += 1
            continue
        break
    if j >= len(lines) or scanned >= max_fwd:
        return "", False
    text_lines = []
    while j < len(lines):
        line = lines[j].strip()
        if line == "" or is_noise_line(line) or DATE_RE.search(line) or ICD_RE.search(line):
            break
        text_lines.append(line)
        j += 1
    text = " ".join(text_lines).strip()
    return text, bool(text)


def find_provider_text(lines: list[str], date_line_idx: int | None, code_idx: int) -> str:
    """Freitext zwischen dem gewählten Datum und dem ICD-Code -- meist der
    Leistungserbringer-Name."""
    if date_line_idx is None:
        return ""
    start, end = min(date_line_idx, code_idx) + 1, max(date_line_idx, code_idx)
    parts = []
    for k in range(start, end):
        line = lines[k].strip()
        if is_noise_line(line) or DATE_RE.search(line) or ICD_RE.search(line):
            continue
        parts.append(line)
    return " ".join(parts).strip()


def has_near_neighbor_code(idx: int, icd_positions: list[int], min_dist: int) -> bool:
    return any(other != idx and abs(other - idx) < min_dist for other in icd_positions)


def _looks_bundled(description: str) -> bool:
    """Erkennt, ob find_text_forward() vermutlich Text MEHRERER Diagnosen in
    einem description-Wert zusammengezogen hat, statt nur den zu diesem
    ICD-Code gehörenden -- unabhängig von has_near_neighbor_code(), das
    NICHT greift, wenn die Codes der anderen Diagnosen OCR-mangled sind
    (verwechselte Ziffern/Buchstaben, treffen ICD_RE nicht) oder weiter als
    ICD_NEIGHBOR_MIN_DIST entfernt stehen, waehrend ihr Diagnosetext trotzdem
    ins Vorwaerts-Fenster faellt. Deutsche ICD-Kurztexte tragen das
    Qualifier-Suffix "bezeichnet" (aus "nicht näher/naher bezeichnet")
    praktisch immer genau einmal -- zwei oder mehr Vorkommen in einem
    einzigen description-Wert sind daher ein starkes Signal fuer mehrere
    aneinandergeratene Diagnosen. Gefunden an einem echten Fall: F32.9 wurde
    certainty=0.9/confirmed trotz vierfach gebündelter Fremd-Diagnosen
    ("Tachykardie... Bronchitis... Fraktur... Depressive Episode..."), weil
    die drei anderen Codes OCR-bedingt nicht als icd_positions erkannt
    wurden."""
    return description.count("bezeichnet") > 1 or description.count(",") > 2


def llm_fallback_icd(window_text: str, icd_code: str, lang: str) -> dict | None:
    """Gibt None bei jedem Fehler zurück (Timeout, Verbindungsabbruch, o.ä.),
    NIE eine Exception nach oben durchreichen -- bei einem mehrstündigen Lauf
    über hunderte Fälle darf ein einzelner haengender/fehlschlagender LLM-
    Aufruf nicht den gesamten Lauf abbrechen (Kandidaten werden erst am Ende
    geschrieben, ein Absturz würde die gesamte bisherige Arbeit verwerfen).
    Aufrufer behandeln None bereits als "LLM konnte nicht klären"."""
    prompt_tpl = _ICD_FALLBACK_PROMPT_DE if lang == "de" else _ICD_FALLBACK_PROMPT_EN
    system = prompt_tpl.format(icd_code=icd_code)
    try:
        response = call_llm_importer_only(
            window_text, system=system, purpose="Diagnosehistorie-ICD-Zuordnung",
            max_tokens=300, require_grounding=False, label_output=False,
        )
    except Exception:
        return None
    if response is None:
        return None
    return extract_json_object(response)


def llm_fallback_med(window_text: str, lang: str) -> dict | None:
    """Siehe llm_fallback_icd() -- dieselbe Begründung für den try/except."""
    system = _MED_FALLBACK_PROMPT_DE if lang == "de" else _MED_FALLBACK_PROMPT_EN
    try:
        response = call_llm_importer_only(
            window_text, system=system, purpose="Diagnosehistorie-Medikamenten-Zuordnung",
            max_tokens=300, require_grounding=False, label_output=False,
        )
    except Exception:
        return None
    if response is None:
        return None
    return extract_json_object(response)


def extract_json_object(text: str) -> dict | None:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        return None
    try:
        data = json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def extract_diagnoses(
    lines: list[str], page_of_line: list[int], lang: str, use_llm: bool, source_name: str,
    done_keys: set[tuple[str, str, int]], emit,
) -> int:
    """emit(candidate) wird pro Eintrag aufgerufen (statt eine komplette Liste
    zurückzugeben) -- so kann cmd_extract() nach jedem Eintrag checkpointen.
    done_keys überspringt bereits (unter den aktuellen --llm-fallback-
    Einstellungen) verarbeitete Einträge bei einem Resume nach Abbruch --
    bei hunderten LLM-Aufrufen à ~10s darf ein Absturz nicht dazu führen,
    dass der komplette Lauf wiederholt werden muss. Rückgabewert: Anzahl
    übersprungener (bereits vorhandener) Einträge."""
    icd_matches = [
        (i, m.group(1), m.group(2))
        for i, line in enumerate(lines)
        for m in [ICD_CODE_RE.search(line)]
        if m
    ]
    icd_positions = [i for i, _, _ in icd_matches]
    n_skipped = 0

    for idx, icd_code, kbv_marker in icd_matches:
        if ("diagnoses", source_name, idx + 1) in done_keys:
            n_skipped += 1
            continue
        page = page_of_line[idx]
        date_candidates = find_date_candidates(lines, idx, ICD_WINDOW_BACK, "beginn", "ende")
        chosen_date, date_unambiguous = choose_date(date_candidates, flag_index=2)
        chosen_date_to, _ = choose_date(date_candidates, flag_index=3, fallback_to_nearest=False)
        date_line_idx = next((j for d, j, _, _ in date_candidates if d == chosen_date), None)
        description, text_found = find_text_forward(lines, idx, ICD_WINDOW_FWD)
        no_near_neighbor = not has_near_neighbor_code(idx, icd_positions, ICD_NEIGHBOR_MIN_DIST)
        provider_text = find_provider_text(lines, date_line_idx, idx)

        unambiguous = date_unambiguous and text_found and no_near_neighbor
        bundled = _looks_bundled(description)
        llm_attempted = False

        if unambiguous and not bundled:
            certainty, status, notes = 0.9, "confirmed", None
        elif use_llm:
            llm_attempted = True
            window = "\n".join(lines[max(0, idx - 20):idx + 21])
            result = llm_fallback_icd(window, icd_code, lang)
            if result and (result.get("date") or result.get("description") or result.get("icd_code")):
                chosen_date = result.get("date") or chosen_date
                chosen_date_to = result.get("date_to") or chosen_date_to
                description = result.get("description") or description
                llm_icd = result.get("icd_code")
                llm_icd_match = ICD_CODE_RE.fullmatch(llm_icd) if llm_icd else None
                if llm_icd_match:
                    icd_code = llm_icd_match.group(1)
                    kbv_marker = llm_icd_match.group(2) or kbv_marker
                location = result.get("fundstelle") or result.get("location")
                certainty, status, notes = 0.6, "needs_review", t(*build_ocr_note(page, window, location))
            else:
                prefix = (
                    "Zuordnung unsicher (OCR/Layout), auch per LLM nicht klärbar — bitte Originaldokument prüfen, ",
                    "Assignment uncertain (OCR/layout), LLM couldn't resolve it either — please check the "
                    "original document, ",
                )
                certainty, status, notes = 0.3, "needs_review", t(*build_ocr_note(page, window, prefix=prefix))
        elif bundled:
            certainty, status, notes = 0.3, "needs_review", t(
                f"Beschreibung wirkt wie mehrere zusammengezogene Diagnosen (Vorwärts-Fenster hat vermutlich "
                f"Text mehrerer ICD-Codes erfasst) — bitte Originaldokument prüfen, Seite {page}",
                f"Description looks like several diagnoses merged together (the forward text window likely "
                f"captured text belonging to multiple ICD codes) — please check the original document, page {page}",
            )
        else:
            certainty, status, notes = 0.3, "needs_review", t(
                f"Zuordnung unsicher (OCR/Layout) — bitte Originaldokument prüfen, Seite {page}",
                f"Assignment uncertain (OCR/layout) — please check the original document, page {page}",
            )

        provider_pseudonym = None
        if provider_text:
            # Eigene Identität NIE an die Provider-Erkennung weiterreichen --
            # Name/Geburtsdatum/Alter/Versichertennummer raus, bevor
            # scrub_provider_text() den Text überhaupt sieht.
            provider_text = scrub_patient_identity(provider_text)
            scrub = scrub_provider_text(provider_text)
            provider_pseudonym = scrub.provider_pseudonym
            if scrub.needs_review and not notes:
                notes = t("Leistungserbringer-Text nicht sicher zuordenbar",
                          "Treating-provider text could not be confidently resolved")

        description = scrub_patient_identity(description)
        if not description:
            # Freitext nicht zuordenbar (z.B. Spaltenlayout, in dem der
            # Beschreibungstext VOR statt nach dem Code steht) -- amtlicher Katalog-Titel als Fallback statt
            # eines reinen Platzhalters. Kein Originaltext-Ersatz, daher per
            # Notes klar als Katalog-Herkunft gekennzeichnet, nicht als
            # verifizierte Seiten-Transkription.
            catalog_entry = icd10_catalog.lookup(icd_code)
            if catalog_entry:
                description = catalog_entry["title"]
                catalog_note = t(
                    "Beschreibung aus dem amtlichen ICD-10-GM-Katalogtitel, nicht aus dem OCR-Text der Seite "
                    "übernommen (Freitext nicht zuordenbar) -- Wortlaut kann vom Originaldokument abweichen.",
                    "Description taken from the official ICD-10-GM catalog title, not from the page's OCR "
                    "text (free text could not be located) -- wording may differ from the source document.",
                )
                notes = f"{notes} {catalog_note}" if notes else catalog_note
            else:
                description = "(nicht automatisch zuordenbar)"

        # "Verdacht auf" und "ausgeschlossen" duerfen nie als bestaetigte Diagnose
        # gelten; das Kennzeichen geht sonst beim Schreiben in die DB verloren.
        kbv_label = _decode_kbv_marker(kbv_marker)
        if kbv_label:
            kbv_note = t(f"KBV-Kennzeichen: {kbv_label}.", f"KBV marker: {kbv_label}.")
            notes = f"{notes} {kbv_note}" if notes else kbv_note
            if kbv_marker[0] in ("A", "V"):
                status = "needs_review"

        emit({
            "table": "diagnoses",
            "date": _to_iso(chosen_date),
            "date_to": _to_iso(chosen_date_to),
            "icd_code": icd_code,
            "diagnosis_certainty": kbv_label,
            "description": description,
            "certainty": certainty,
            "status": status,
            "notes": scrub_patient_identity(notes) if notes else notes,
            "provider_pseudonym": provider_pseudonym,
            "llm_attempted": llm_attempted,
            "source_page": page,
            "source_line": idx + 1,
            "source_file": source_name,
        })
    return n_skipped


def find_nearest_free_text(lines: list[str], idx: int, window: int) -> str:
    """Nächstgelegene freie Textzeile (kein Label, kein Datum, keine PZN/IK-
    Zahl) in BEIDEN Richtungen um idx, wachsend im Abstand -- Präparatname
    steht nicht verlässlich vor oder nach der PZN (OCR-Spaltenverwürfelung,
    siehe Moduldocstring)."""
    for offset in range(1, window + 1):
        for j in (idx - offset, idx + offset):
            if 0 <= j < len(lines):
                line = lines[j].strip()
                if is_noise_line(line) or DATE_RE.search(line) or PZN_RE.fullmatch(line) or IK_RE.fullmatch(line):
                    continue
                return line
    return ""


def find_verordner_pseudonym(lines: list[str], idx: int, max_back: int) -> str | None:
    """Nächstgelegenes "Verordner"-Label rückwärts -- gilt für eine ganze
    Seite voller PZN-Einträge, nicht nur für einen einzelnen (siehe
    Moduldocstring), daher derselbe weite Rückwärts-Suchradius wie bei
    find_date_candidates(). Zwischen Label und Wert liegt im Dokument
    oft eine Leerzeile -- direkt lines[j+1] nehmen greift daher oft ins
    Leere, es muss bis zur ersten NICHT-leeren Zeile weitergesucht werden."""
    start = max(0, idx - max_back)
    for j in range(idx - 1, start - 1, -1):
        if lines[j].strip().lower() != "verordner":
            continue
        for k in range(j + 1, min(len(lines), j + 4)):
            raw = lines[k].strip()
            if not raw:
                continue
            if not is_noise_line(raw):
                return resolve_provider(raw)
            break
        break
    return None


def extract_medications(
    lines: list[str], page_of_line: list[int], lang: str, use_llm: bool, source_name: str,
    done_keys: set[tuple[str, str, int]], emit,
) -> int:
    """PZN-Zahlen (6-8-stellig, eigene Zeile) sind der Anker pro Eintrag --
    NICHT das "Apotheke"-Label, das sich als Spaltenkopf einmal pro Seite
    wiederholt (wenige "Apotheke"-Label-Zeilen stehen gegen viele einzelne PZN-Zahlen
    auf denselben Seiten --
    derselbe Fehler wie beim ICD-Zeilenfenster, nur beim Medikamenten-Pass
    zunächst übersehen). emit()/done_keys: siehe
    extract_diagnoses() -- gleiches Resume-/Checkpoint-Prinzip."""
    pzn_positions = [i for i, line in enumerate(lines) if PZN_RE.fullmatch(line.strip()) and not DATE_RE.search(line)]
    n_skipped = 0

    for idx in pzn_positions:
        if ("medications", source_name, idx + 1) in done_keys:
            n_skipped += 1
            continue
        page = page_of_line[idx]
        chosen_pzn = lines[idx].strip()
        date_candidates = find_date_candidates(lines, idx, ICD_WINDOW_BACK, "verordnung", "abgabe")
        chosen_date, date_unambiguous = choose_date(date_candidates, flag_index=2)
        chosen_date_abgabe, _ = choose_date(date_candidates, flag_index=3, fallback_to_nearest=False)
        drug_name = find_nearest_free_text(lines, idx, MED_WINDOW)
        no_near_neighbor = not has_near_neighbor_code(idx, pzn_positions, ICD_NEIGHBOR_MIN_DIST)
        verordner_pseudonym = find_verordner_pseudonym(lines, idx, ICD_WINDOW_BACK)

        unambiguous = date_unambiguous and bool(drug_name) and no_near_neighbor
        llm_attempted = False

        if unambiguous:
            certainty, status, notes = 0.7, "confirmed", None
        elif use_llm:
            llm_attempted = True
            window_text = "\n".join(lines[max(0, idx - MED_WINDOW):idx + MED_WINDOW + 1])
            result = llm_fallback_med(window_text, lang)
            if result and (result.get("date") or result.get("medication_id") or result.get("drug_name")):
                chosen_date = result.get("date") or chosen_date
                chosen_date_abgabe = result.get("date_abgabe") or chosen_date_abgabe
                chosen_pzn = result.get("medication_id") or chosen_pzn
                drug_name = result.get("drug_name") or drug_name
                location = result.get("fundstelle") or result.get("location")
                certainty, status, notes = 0.6, "needs_review", t(*build_ocr_note(page, window_text, location))
            else:
                prefix = (
                    "Zuordnung unsicher, auch per LLM nicht klärbar, ",
                    "Assignment uncertain, LLM couldn't resolve it either, ",
                )
                certainty, status, notes = 0.3, "needs_review", t(*build_ocr_note(page, window_text, prefix=prefix))
        else:
            certainty, status, notes = 0.3, "needs_review", t(
                f"Zuordnung unsicher (OCR/Layout) — bitte Originaldokument prüfen, Seite {page}",
                f"Assignment uncertain (OCR/layout) — please check the original document, page {page}",
            )

        emit({
            "table": "medications",
            "date": _to_iso(chosen_date),
            "date_abgabe": _to_iso(chosen_date_abgabe),
            "medication_id": chosen_pzn,
            "drug_name": scrub_patient_identity(drug_name) or "(nicht automatisch zuordenbar)",
            "verordner_pseudonym": verordner_pseudonym,
            "certainty": certainty,
            "status": status,
            "notes": scrub_patient_identity(notes) if notes else notes,
            "llm_attempted": llm_attempted,
            "source_page": page,
            "source_line": idx + 1,
            "source_file": source_name,
        })
    return n_skipped


def _to_iso(date_str: str | None) -> str | None:
    """TT.MM.JJJJ -> JJJJ-MM-TT; None bleibt None."""
    if not date_str:
        return None
    m = DATE_RE.fullmatch(date_str)
    if not m:
        return None
    d, mo, y = date_str.split(".")
    return f"{y}-{mo}-{d}"


CHECKPOINT_EVERY = 20  # bei ~10s/LLM-Aufruf alle ~3-4 Min. ein Zwischenstand --
                       # ein Absturz bei hunderten Aufrufen darf höchstens
                       # diese Anzahl Einträge kosten, nie den ganzen Lauf.


def _write_candidates_atomic(out_path: Path, candidates: list[dict]) -> None:
    """Schreibt über eine temporäre Datei + os.replace() (atomar unter POSIX)
    -- ein Absturz mitten im Schreiben darf die bisherigen Kandidaten nie
    korrumpieren, da sie die einzige Grundlage für einen Resume sind."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = out_path.with_suffix(out_path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(candidates, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(out_path)


def _load_resumable_candidates(out_path: Path, use_llm: bool) -> tuple[list[dict], set[tuple[str, str, int]]]:
    """Lädt eine ggf. vorhandene Kandidaten-Datei aus einem abgebrochenen
    Lauf. Ein Eintrag gilt als "fertig" (wird übersprungen), wenn er bereits
    hohe Konfidenz hat ODER unter den aktuellen --llm-fallback-Einstellungen
    schon einen LLM-Versuch bekommen hat (llm_attempted=True). Ein Eintrag,
    der vorher OHNE --llm-fallback nur strukturell unsicher blieb, wird bei
    einem Resume MIT --llm-fallback dagegen verworfen und neu versucht --
    sonst würde ein Upgrade auf --llm-fallback nie etwas verbessern."""
    if not out_path.exists():
        return [], set()
    try:
        existing = json.loads(out_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return [], set()

    def is_done(c: dict) -> bool:
        threshold = 0.9 if c["table"] == "diagnoses" else 0.7
        return c["certainty"] >= threshold or (use_llm and c.get("llm_attempted", False))

    keep = [c for c in existing if is_done(c)]
    n_requeued = len(existing) - len(keep)
    done_keys = {(c["table"], c["source_file"], c["source_line"]) for c in keep}
    if existing:
        print(t(
            f"Fortsetzung eines vorherigen Laufs: {len(keep)} bereits abgeschlossene "
            f"Kandidaten übernommen, {n_requeued} werden erneut versucht.",
            f"Resuming a previous run: {len(keep)} already-finished candidates kept, "
            f"{n_requeued} will be retried.",
        ))
    return keep, done_keys


def cmd_extract(files: list[Path], out_path: Path, lang: str, use_llm: bool) -> None:
    all_candidates, done_keys = _load_resumable_candidates(out_path, use_llm)

    def emit(candidate: dict) -> None:
        all_candidates.append(candidate)
        if len(all_candidates) % CHECKPOINT_EVERY == 0:
            _write_candidates_atomic(out_path, all_candidates)

    for f in files:
        if not f.exists():
            print(t(f"Nicht gefunden: {f}", f"Not found: {f}"))
            continue
        lines, page_of_line = read_lines(f)
        print(t(f"{f.name}: {len(lines)} Zeilen, {page_of_line[-1] if page_of_line else 0} Seiten",
                f"{f.name}: {len(lines)} lines, {page_of_line[-1] if page_of_line else 0} pages"))
        # Der rohe Scanner-Dateiname (z.B. mit Geräte-Batch-/Zeitstempel-Kennung)
        # ist selbst eine Re-Identifikations-Spur und wird nie in die
        # Kandidaten-Datei geschrieben -- nur sein Pseudonym.
        source_pseudonym = resolve_sourcefile(f.name)
        n_before = len(all_candidates)
        n_skipped_diag = extract_diagnoses(lines, page_of_line, lang, use_llm, source_pseudonym, done_keys, emit)
        n_after_diag = len(all_candidates)
        n_skipped_med = extract_medications(lines, page_of_line, lang, use_llm, source_pseudonym, done_keys, emit)
        n_new_diag, n_new_med = n_after_diag - n_before, len(all_candidates) - n_after_diag
        print(t(f"  {n_new_diag} neue Diagnose-Kandidaten ({n_skipped_diag} übersprungen), "
                f"{n_new_med} neue Medikamenten-Kandidaten ({n_skipped_med} übersprungen)",
                f"  {n_new_diag} new diagnosis candidates ({n_skipped_diag} skipped), "
                f"{n_new_med} new medication candidates ({n_skipped_med} skipped)"))

    _write_candidates_atomic(out_path, all_candidates)

    n_total = len(all_candidates)
    n_low = sum(1 for c in all_candidates if c["certainty"] < 0.9)
    print(t(f"\n{n_total} Kandidaten insgesamt ({n_low} mit certainty < 0.9) → {out_path}",
            f"\n{n_total} candidates total ({n_low} with certainty < 0.9) → {out_path}"))
    print(t("Bitte vor Import prüfen, dann: python3 import_billed_diagnoses.py --commit",
            "Please review before import, then: python3 import_billed_diagnoses.py --commit"))


def check_duplicate_diagnosis(conn, row: dict, person: str) -> bool:
    cur = conn.execute(
        "SELECT 1 FROM diagnoses WHERE person = ? AND icd_code = ? AND date = ?",
        (person, row["icd_code"], row["date"]),
    )
    return cur.fetchone() is not None


def check_duplicate_medication(conn, row: dict, person: str, ts: str) -> bool:
    cur = conn.execute(
        "SELECT 1 FROM medications WHERE ts = ? AND person = ? AND source = ?",
        (ts, person, "billed_diagnoses_scan_medication"),
    )
    return cur.fetchone() is not None


def cmd_commit(candidates_path: Path, person: str) -> None:
    if not candidates_path.exists():
        print(t(f"Nicht gefunden: {candidates_path}", f"Not found: {candidates_path}"))
        sys.exit(1)
    rows = json.loads(candidates_path.read_text(encoding="utf-8"))
    if not rows:
        print(t("Keine Kandidaten in der Datei.", "No candidates in the file."))
        return

    conn = open_medicine_db()
    n_written, n_skipped_null, n_dup = 0, 0, 0
    skipped_null_rows = []

    for r in rows:
        if r.get("date") is None:
            n_skipped_null += 1
            skipped_null_rows.append(r)
            continue

        if r["table"] == "diagnoses":
            if check_duplicate_diagnosis(conn, r, person):
                n_dup += 1
                continue
            conn.execute(
                """
                INSERT OR IGNORE INTO diagnoses
                    (person, date, date_to, icd_code, description, status, certainty,
                     source, notes, provider_pseudonym)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (person, r["date"], r.get("date_to"), r.get("icd_code"), r["description"], r["status"],
                 r["certainty"], "billed_diagnoses_scan", r.get("notes"), r.get("provider_pseudonym")),
            )
            n_written += 1
        elif r["table"] == "medications":
            ts = f"{r['date']}T00:00:00Z"
            if check_duplicate_medication(conn, r, person, ts):
                n_dup += 1
                continue
            conn.execute(
                """
                INSERT OR IGNORE INTO medications
                    (ts, date, date_abgabe, medication_id, drug_name, dose_value, dose_unit,
                     route, is_skipped, is_chronic, notes, prescriber_pseudonym,
                     person, source)
                VALUES (?, ?, ?, ?, ?, NULL, NULL, NULL, 0, 0, ?, ?, ?, ?)
                """,
                (ts, r["date"], r.get("date_abgabe"), r.get("medication_id"), r["drug_name"], r.get("notes"),
                 r.get("verordner_pseudonym"), person, "billed_diagnoses_scan_medication"),
            )
            n_written += 1

    conn.commit()
    log_import(conn, "billed_diagnoses", str(candidates_path), n_written, person=person)
    conn.close()

    print(t(f"→ {n_written} neue Einträge geschrieben, {n_dup} bereits vorhanden (übersprungen)",
            f"→ {n_written} new entries written, {n_dup} already present (skipped)"))
    if n_skipped_null:
        print(t(f"⚠ {n_skipped_null} Kandidaten ohne Datum übersprungen (nicht in die DB geschrieben):",
                f"⚠ {n_skipped_null} candidates without a date skipped (not written to the DB):"))
        for r in skipped_null_rows:
            print(f"    {r['table']} · {r.get('icd_code') or r.get('medication_id') or '?'} · "
                  f"{t('Seite', 'page')} {r.get('source_page')} ({r.get('source_file')})")


def main() -> None:
    parser = argparse.ArgumentParser(description=t(
        "Diagnose-/Medikamentenhistorie aus Krankenkassen-Leistungsübersicht extrahieren/importieren",
        "Extract/import diagnosis/medication history from a health-insurer benefits overview",
    ))
    parser.add_argument("--extract", action="store_true", help=t("Kandidaten extrahieren", "Extract candidates"))
    parser.add_argument("--commit", action="store_true", help=t("Kandidaten in die DB schreiben", "Write candidates to the DB"))
    parser.add_argument("--file", nargs="+", type=Path, default=None,
                        help=t("Bei --extract: PDF/TXT-Dateien. Bei --commit: Kandidaten-JSON (optional).",
                               "With --extract: PDF/TXT files. With --commit: candidates JSON (optional)."))
    parser.add_argument("--llm-fallback", action="store_true",
                        help=t("Uneindeutige Fälle zusätzlich einem lokalen LLM vorlegen (kann sehr lange dauern)",
                               "Also submit ambiguous cases to a local LLM (can take a very long time)"))
    parser.add_argument("--person", default=None, help=t("Ziel-Person (Default: OWN_PERSON_ID)", "Target person (default: OWN_PERSON_ID)"))
    add_lang_arg(parser)
    args = parser.parse_args()
    apply_lang_from_args(args)
    person = resolve_person(args.person)

    if args.extract == args.commit:
        print(t("Bitte genau eines von --extract oder --commit angeben.",
                "Please specify exactly one of --extract or --commit."))
        sys.exit(1)

    lang = getattr(args, "lang", "de") or "de"

    if args.extract:
        if not args.file:
            print(t("--extract braucht --file <pdf/txt> [...]", "--extract needs --file <pdf/txt> [...]"))
            sys.exit(1)
        cmd_extract(args.file, DEFAULT_CANDIDATES_PATH, lang, args.llm_fallback)
    else:
        candidates_path = args.file[0] if args.file else DEFAULT_CANDIDATES_PATH
        cmd_commit(candidates_path, person)


if __name__ == "__main__":
    main()
