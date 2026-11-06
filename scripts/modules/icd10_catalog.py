#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
icd10_catalog.py — Lokaler ICD-10-GM-Katalog-Abgleich (Code-Existenz + amtlicher Text)

@tier        infrastructure
@purpose.de  Prüft, ob ein ICD-10-GM-Code tatsächlich existiert (nicht nur
             formal wie ICD_RE in import_billed_diagnoses.py) und liefert
             dessen amtlichen Klassentitel zum Abgleich gegen einen
             extrahierten Freitext -- entstanden aus einem echten Fund: eine
             OCR-Extraktion hatte den Code F32.9 (Depressive Episode) mit
             einem Freitext aus VIER fremden Diagnosen bestückt, ohne dass
             das formale Regex-Format dies verhindert hätte (siehe
             import_billed_diagnoses.py::_looks_bundled() für die
             Struktur-Heuristik; dieses Modul deckt die inhaltliche Prüfung
             ab, die eine Formatprüfung nicht leisten kann).
@purpose.en  Checks whether an ICD-10-GM code actually exists (not merely
             shape-valid like ICD_RE in import_billed_diagnoses.py) and
             returns its official class title for comparison against an
             extracted free-text description -- built from a real finding:
             an OCR extraction had attached code F32.9 (depressive episode)
             to free text drawn from FOUR unrelated diagnoses, something no
             amount of regex-shape checking would have caught (see
             import_billed_diagnoses.py::_looks_bundled() for the
             structural heuristic; this module covers the content check a
             format check cannot).
@method.de   Liest NICHT aus dem Repo (das Repo enthält keine ICD-10-GM-
             Daten, siehe @limits), sondern aus einer lokalen, von
             scripts/utils/update_icd10_catalog.py heruntergeladenen Datei
             unter data/reference/icd10gm/ -- Format laut BfArM-Spezifikation
             (Semikolon-getrennt, Feld 7 = Code ohne Strich/Stern/
             Ausrufezeichen, Feld 2 = T/N terminal-Flag, Feld 9 =
             zusammengesetzter Klassentitel). Wird
             lazy beim ersten Aufruf geladen und pro Prozess gecacht (Datei
             hat >16.000 Zeilen, soll nicht pro Kandidat neu eingelesen
             werden). check_description_plausible() vergleicht Inhaltswort-
             Mengen (≥4 Zeichen, Boilerplate wie "nicht näher bezeichnet"
             per _STOPWORDS_DE herausgefiltert) statt eines rohen Zeichen-
             Ratios -- ein roher difflib.SequenceMatcher-Ratio-Vergleich
             wurde zuerst versucht und beim Testen verworfen: kurze
             deutsche Wörter teilen so viele Buchstaben, dass selbst ein
             klar falsches Paar (J42 "chronische Bronchitis" vs. Text
             "Fraktur einer sonstigen Zehe") einen Ratio von 0.30 erreichte
             -- oberhalb jeder sinnvollen Schwelle. Keine Embeddings/kein
             LLM -- bewusst simpel und deterministisch, da hier nur grobe
             Fehlzuordnungen wie das F32.9-Beispiel gefunden werden müssen,
             keine feinen Formulierungsunterschiede.
@method.en   Does NOT read from the repo (the repo contains no ICD-10-GM
             data, see @limits), but from a local file downloaded by
             scripts/utils/update_icd10_catalog.py under
             data/reference/icd10gm/ -- format per the BfArM spec
             (semicolon-separated, field 7 = code without dash/star/
             exclamation mark, field 2 = T/N terminal flag, field 9 =
             combined class title). Loaded lazily
             on first call and cached per process (the file has >16,000
             lines, shouldn't be re-read per candidate). check_description_plausible()
             compares content-word sets (≥4 chars, boilerplate like "nicht
             näher bezeichnet" filtered via _STOPWORDS_DE) instead of a raw
             character ratio -- a raw difflib.SequenceMatcher ratio was
             tried first and discarded during testing: short German words
             share so many letters that even a clearly wrong pair (J42
             "chronic bronchitis" vs. text "fracture of an unspecified
             toe") reached a ratio of 0.30 -- above any sensible threshold.
             No embeddings/no LLM -- deliberately simple and deterministic,
             since this only needs to catch gross misassignments like the
             F32.9 example, not fine wording differences.
@reads       data/reference/icd10gm/icd10gm<JAHR>syst_kodes.txt (lokal,
             nicht im Repo -- siehe @limits)
@writes      keine Tabellen (reine Nachschlage-/Prüffunktion)
@limits.de   KEIN Katalog im Repo gebündelt -- der ICD-10-GM-Download bei
             BfArM erfordert pro Nutzer*in die Zustimmung zu einem eigenen
             Nutzungsvertrag (Downloadbedingungen), das kann und soll nicht
             stellvertretend für alle Nutzer*innen des öffentlichen Repos
             einmalig geschehen. Jede Installation muss
             update_icd10_catalog.py selbst einmal laufen lassen (eigener
             Formular-Durchlauf) oder die ZIP-Datei von bfarm.de manuell
             ablegen. Ohne diese lokale Datei liefert jede Funktion hier
             None/False mit einem Hinweis auf update_icd10_catalog.py, KEIN
             Absturz. Nur Codes der aktuell heruntergeladenen Jahresversion
             werden erkannt -- ein Code, der zwischen zwei ICD-10-GM-
             Versionen gestrichen oder neu eingeführt wurde, kann je nach
             Jahr der Abrechnung fälschlich als unbekannt/bekannt gelten
             (siehe scripts/utils/update_icd10_catalog.py --check für
             Versionsstand). check_description_plausible() ist eine grobe
             Wortüberlappungs-Heuristik, kein semantischer Vergleich -- ein
             spezifischerer Text als der knappe amtliche Titel (z.B. ein
             ausführlicher Arztbrief-Satz) kann fälschlich als "nicht
             plausibel" markiert werden; gedacht als Review-Hinweis, nicht
             als automatische Korrektur.
@limits.en   NO catalog bundled in the repo -- the ICD-10-GM download at
             BfArM requires each user to accept their OWN usage contract
             (download conditions); this cannot and should not be done
             once on behalf of every user of the public repo. Each
             installation must run update_icd10_catalog.py itself (its own
             form submission) or manually place the ZIP from bfarm.de.
             Without that local file, every function here returns
             None/False with a pointer to update_icd10_catalog.py, NOT a
             crash. Only codes from the currently downloaded year's version
             are recognized -- a code retired or introduced between two
             ICD-10-GM versions can be wrongly judged unknown/known
             depending on the billing year (see
             scripts/utils/update_icd10_catalog.py --check for the
             installed version). check_description_plausible() is a rough
             word-overlap heuristic, not a semantic comparison -- a more
             specific text than the terse official title (e.g. a detailed
             doctor's-letter sentence) can be wrongly flagged as "not
             plausible"; meant as a review hint, not an automatic
             correction.

@relevance.de  Fängt inhaltliche Fehlzuordnungen (falscher/nicht-existenter Code, Code↔Text-Mismatch) ab, die eine reine Formatprüfung nicht erkennen kann, essentiell für die Zuverlässigkeit importierter Diagnosedaten
@relevance.en  Catches content-level misassignments (wrong/non-existent code, code↔text mismatch) that a pure format check cannot detect, essential for the reliability of imported diagnosis data
@usage
    from modules.icd10_catalog import lookup, is_known, check_description_plausible, catalog_version

    if not is_known("F32.9"):
        ...  # Code existiert nicht im geladenen Katalogjahr
    entry = lookup("F32.9")  # {"title": "...", "terminal": True, "level": 4}
    plausible, official_title = check_description_plausible("F32.9", "Tachykardie, ...")
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

# Fester Pfad relativ zum Repo-Root, NICHT ueber health_config.data_root
# (das zeigt auf imports/, nicht auf data/) -- dieselbe Konvention wie
# scripts/calibration/download_afdb.py fuer data/calibration/afdb/.
_REPO_ROOT = Path(__file__).parents[2]
_CATALOG_DIR = _REPO_ROOT / "data" / "reference" / "icd10gm"


def _catalog_dir() -> Path:
    return _CATALOG_DIR


@lru_cache(maxsize=1)
def _load_catalog() -> dict[str, dict] | None:
    """Gibt None zurück (statt zu werfen), wenn keine Katalogdatei lokal
    vorhanden ist -- siehe Moduldocstring @limits: fehlende Zustimmung zu
    den BfArM-Downloadbedingungen ist ein normaler, erwartbarer Zustand
    jeder frischen Installation, kein Fehler."""
    catalog_dir = _catalog_dir()
    if not catalog_dir.exists():
        return None
    candidates = sorted(catalog_dir.glob("icd10gm*syst_kodes.txt"))
    if not candidates:
        return None
    # Falls mehrere Jahresversionen nebeneinander liegen (altes Jahr noch
    # nicht geloescht): die neueste (hoechste Jahreszahl im Dateinamen) gilt.
    path = candidates[-1]
    entries: dict[str, dict] = {}
    with path.open(encoding="utf-8") as f:
        for line in f:
            fields = line.rstrip("\n").split(";")
            if len(fields) < 9:
                continue
            # Feld 6 (fields[5]) behaelt Kreuz/Stern/Ausrufezeichen/Strich
            # (z.B. "U07.1!", "F60.3-") -- Feld 7 (fields[6]) ist die
            # bereinigte Form ohne diese Zeichen, die zu den aus OCR-Text
            # per ICD_RE (nur Buchstabe+Ziffern+Punkt+Ziffern) extrahierten
            # Codes passt. Ohne diesen Unterschied galten U07.1 (COVID-19)
            # und jeder Nicht-Endstufen-Codes wie F60.3/N28.8 faelschlich
            # als "unbekannt" -- gefunden beim ersten echten Testlauf.
            code = fields[6]  # Feld 7: Schluesselnummer ohne Strich/Stern/Ausrufezeichen
            entries[code] = {
                "title": fields[8],  # Feld 9: zusammengesetzter Klassentitel
                "terminal": fields[1] == "T",  # Feld 2
                "level": int(fields[0]) if fields[0].isdigit() else None,  # Feld 1
            }
    return entries


def catalog_version() -> str | None:
    """Jahr der geladenen Katalogdatei (aus dem Dateinamen), oder None wenn
    kein Katalog installiert ist."""
    catalog_dir = _catalog_dir()
    if not catalog_dir.exists():
        return None
    candidates = sorted(catalog_dir.glob("icd10gm*syst_kodes.txt"))
    if not candidates:
        return None
    m = re.search(r"icd10gm(\d{4})syst_kodes\.txt$", candidates[-1].name)
    return m.group(1) if m else None


def is_available() -> bool:
    return _load_catalog() is not None


def is_known(code: str) -> bool | None:
    """True/False bei geladenem Katalog, None wenn kein Katalog installiert
    ist (Aufrufer sollte None von False unterscheiden -- None heisst
    'ungeprueft', nicht 'ungueltig')."""
    catalog = _load_catalog()
    if catalog is None:
        return None
    return code in catalog


def lookup(code: str) -> dict | None:
    """Liefert {"title", "terminal", "level"} oder None (Code unbekannt
    ODER kein Katalog installiert -- siehe is_available(), um die beiden
    Faelle zu unterscheiden)."""
    catalog = _load_catalog()
    if catalog is None:
        return None
    return catalog.get(code)


# Woerter, die in praktisch jedem ICD-10-GM-Kurztitel auftauchen
# ("nicht naeher bezeichnet" & Verwandte) -- als Ueberlappungssignal nutzlos,
# da sie KEINEN Code von einem anderen unterscheiden. Ohne diese Liste
# wuerde z.B. jeder "...nicht naeher bezeichnet"-Text mit jedem anderen
# "...nicht naeher bezeichnet"-Code ueberlappen, unabhaengig vom Inhalt --
# gefunden beim Testen mit einem echten Fall (J42 vs. "Fraktur einer
# sonstigen Zehe": ein roher Zeichen-Ratio-Vergleich lag bei 0.30 allein durch
# gemeinsame haeufige Buchstaben in kurzen deutschen Woertern, oberhalb der
# ersten Testschwelle -- Zeichen-Ratio auf kurzen Strings ist zu unspezifisch,
# daher Wortmengen-Ueberlappung auf Inhaltswoertern statt Zeichen-Ratio).
_STOPWORDS_DE_RAW = {
    "nicht", "näher", "bezeichnet", "bezeichnete", "bezeichneter",
    "sonstige", "sonstiger", "sonstigen", "sonstiges", "andere", "anderer",
    "anderen", "anderes", "ohne", "mit", "als", "und", "oder", "der", "die",
    "das", "des", "dem", "den", "ein", "eine", "einer", "einem", "eines",
}

_UMLAUT_MAP = str.maketrans({"ä": "a", "ö": "o", "ü": "u", "ß": "s"})
# Normalisierte Form einmal vorab berechnen, statt bei jedem Aufruf neu --
# dieselbe Umlaut-Normalisierung wie fuer die verglichenen Woerter, damit
# z.B. "näher" (Stoppwort) UND dessen OCR-Variante "naher" beide greifen,
# ohne jede Variante hier von Hand aufzaehlen zu muessen.
_STOPWORDS_DE = {w.translate(_UMLAUT_MAP) for w in _STOPWORDS_DE_RAW}


def _content_words(text: str) -> set[str]:
    """Umlaute/ß werden vor dem Vergleich normalisiert -- die OCR-Quelle
    verschluckt sie fast durchgaengig (z.B. "ndher" statt "näher",
    "Storung" statt "Störung", durchgaengig im ganzen Dokument), eine
    exakte Umlaut-Uebereinstimmung waere also selbst bei inhaltlich
    korrekten Treffern unzuverlaessig (beim Testen am echten Datensatz:
    ein Teil der Mismatches war ausschliesslich Umlaut-Artefakte, kein
    echter Inhaltsunterschied)."""
    words = re.findall(r"[a-zäöüß]+", (text or "").lower())
    normalized = (w.translate(_UMLAUT_MAP) for w in words)
    return {w for w in normalized if len(w) >= 4 and w not in _STOPWORDS_DE}


def check_description_plausible(code: str, description: str) -> tuple[bool | None, str | None]:
    """(plausible, official_title). plausible ist None, wenn der Code
    unbekannt ist oder kein Katalog installiert ist (siehe is_known()) --
    in diesem Fall ist auch official_title None. Sonst: Wortmengen-
    Überlappung auf Inhaltswörtern (siehe _STOPWORDS_DE/@method) zwischen
    description und dem amtlichen Titel; True wenn mindestens ein
    Inhaltswort gemeinsam vorkommt ODER der Titel nach Boilerplate-Abzug
    keine Inhaltswörter mehr hat (z.B. ein Titel, der nur aus Boilerplate
    besteht, liefert kein auswertbares Signal -- dann nicht fälschlich als
    'nicht plausibel' werten)."""
    entry = lookup(code)
    if entry is None:
        return None, None
    official_title = entry["title"]
    title_words = _content_words(official_title)
    if not title_words:
        return True, official_title
    desc_words = _content_words(description)
    return bool(title_words & desc_words), official_title


def check_bundled_contamination(code: str, description: str) -> tuple[bool | None, str | None]:
    """(bundled, official_title). bundled ist None, wenn der Code
    unbekannt ist oder kein Katalog installiert ist. Erkennt eine Lücke,
    die check_description_plausible() NICHT abdeckt: eine description, die
    eine echte Diagnose (die zum Code passt) zusammen mit FREMDEM Text
    anderer Diagnosen enthält -- check_description_plausible() liefert für
    so einen Fall plausible=True, weil die passenden Wörter ja tatsächlich
    enthalten sind, irgendwo in der Mitte eines viel längeren, kontaminierten
    Textes. Gefunden beim Review: F32.9 (Depressive Episode) mit description
    "Tachykardie... Bronchitis... Fraktur... Depressive Episode..." --
    plausible nach der reinen Überlappungs-Prüfung, aber klar kontaminiert.
    Zweistufig: (1) günstiger Vorfilter wie
    import_billed_diagnoses.py::_looks_bundled() (">1x 'bezeichnet'" oder
    ">2 Kommas") -- OHNE diesen Vorfilter würde JEDE auch nur geringfügig
    längere, aber vollkommen plausible description durchfallen; (2) NUR
    wenn der Vorfilter anschlägt: zählt Inhaltswörter in description, die
    NICHT im amtlichen Titel vorkommen ("extra"). Schwelle extra>=2, aus
    echten Daten kalibriert -- amtliche 5-Steller-Titel wie "Rückenschmerzen,
    nicht näher bezeichnet: Nicht näher bezeichnete Lokalisation" treffen
    den Vorfilter (zweimal "bezeichnet"), haben aber extra=0/1 (nur
    OCR-Rauschen) und sind damit korrekt NICHT kontaminiert -- während echte
    Fremddiagnosen-Reste (z.B. "tachykardie", "bronchitis", "fraktur") als
    extra>=2 zuverlässig auffallen."""
    entry = lookup(code)
    if entry is None:
        return None, None
    official_title = entry["title"]
    if description.count("bezeichnet") <= 1 and description.count(",") <= 2:
        return False, official_title
    title_words = _content_words(official_title)
    desc_words = _content_words(description)
    extra = desc_words - title_words
    return len(extra) >= 2, official_title
