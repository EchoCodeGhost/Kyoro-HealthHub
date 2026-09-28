#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
FibriCheck-PDF-Bericht → health.db

@tier        infrastructure
@purpose.de  Importiert FibriCheck-Herzrhythmus-Berichte (PPG-Einzelmessungen,
             smartphone-basiert, vom FibriCheck-Expertengremium ueberprueft)
             aus PDF-Exporten in eine strukturierte Tabelle.
@purpose.en  Imports FibriCheck heart-rhythm reports (smartphone-based PPG
             spot checks, reviewed by the FibriCheck expert panel) from PDF
             exports into a structured table.
@method.de   Liest den PDF-Text (pdfplumber), extrahiert Messzeitpunkt,
             Pruefzeitpunkt, Ergebnisklassifikation (Freitext + normalisierter
             Code ueber ein Schluesselwort-Mapping), Herzfrequenz-Durchschnitt,
             Aktivitaetskontext, gemeldete Symptome, Aufnahmegeraet,
             Algorithmus-Version und Expertengremium-Status. Kein OCR noetig —
             FibriCheck-PDFs sind textbasiert, kein Scan. PDF wird danach wie
             bei import_lab_results.py PII-bereinigt archiviert.
@method.en   Reads the PDF text (pdfplumber), extracts measurement timestamp,
             review timestamp, result classification (free text + normalised
             code via a keyword mapping), average heart rate, activity
             context, reported symptoms, recording device, algorithm version,
             and expert-panel review status. No OCR needed — FibriCheck PDFs
             are text-based, not scanned. PDF is archived PII-scrubbed
             afterwards, same as import_lab_results.py.
@reads       PDF-Dateien (FibriCheck-Berichte)
@writes      fibricheck_sessions: ts, ts_reviewed, date, result_code,
             result_text, hr_avg_bpm, activity_context, symptoms_reported,
             recording_device, algorithm_version, panel_reviewed, person,
             source_file

@relevance.de  Ermoeglicht die Einbindung unabhaengiger PPG-Herzrhythmus-Einzelmessungen
               (z.B. Verdacht auf Extrasystolen/Bigeminie), essentiell als externe
               Vergleichsquelle neben der kontinuierlichen Wearable-Erkennung.
@relevance.en  Enables inclusion of independent PPG heart-rhythm spot checks (e.g.
               suspected extrasystoles/bigeminy), essential as an external comparison
               source alongside continuous wearable-based detection.
@limits.de   Smartphone-Kamera-PPG, keine EKG-Ableitung — dieselbe methodische
             Einschraenkung wie andere optische Quellen im Projekt (s.
             compute_arrhythmia.py). FibriCheck ist CE-gekennzeichnet und
             Berichte werden von einem Expertengremium gegengeprueft, das
             ersetzt aber keine 12-Kanal-EKG-Untersuchung (Disclaimer im
             Bericht selbst). result_code-Mapping deckt nur bisher bekannte
             Formulierungen ab — neue/unbekannte Ergebnistexte landen als
             'unknown' mit dem Rohtext in result_text, nicht stillschweigend
             falsch zugeordnet.
@limits.en   Smartphone camera PPG, not an ECG lead — same methodological
             limitation as other optical sources in the project (s.
             compute_arrhythmia.py). FibriCheck is CE-marked and reports are
             counter-checked by an expert panel, but that does not replace a
             12-lead ECG examination (disclaimer in the report itself).
             result_code mapping only covers previously seen phrasings — new/
             unknown result text lands as 'unknown' with the raw text kept in
             result_text, never silently mis-mapped.
@usage
    python import_fibricheck.py bericht.pdf
    python import_fibricheck.py *.pdf
    python import_fibricheck.py --person PER-XXXXXXXX bericht.pdf
"""

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))
from modules.base import log_import, resolve_person
from modules.db import open_db
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from utils.scrub_pdf_metadata import scrub as _scrub_pdf_metadata

PDF_DIR       = Path(__file__).parents[2] / "imports" / "fibricheck"
ORIGINALE_DIR = PDF_DIR / "originals"

# Bekannte Ergebnistext-Fragmente → normalisierter Code. Case-insensitiv,
# gegen den fett hervorgehobenen Klassifikationstext im Bericht geprueft
# ("EXTRASYSTOLEN - BIGEMINIEEPISODE" u.ae.) sowie gegen den Fliesstext
# ("...die auf X hindeuten koennten"). Neue Formulierungen hier ergaenzen,
# sobald ein Bericht mit einem noch nicht gelisteten Ergebnis auftaucht —
# nicht raten, s. CLAUDE.md Regel 4.
RESULT_CODE_MAP = [
    (re.compile(r"bigeminie", re.IGNORECASE), "extrasystoles_bigeminy"),
    (re.compile(r"extrasystol", re.IGNORECASE), "extrasystoles"),
    (re.compile(r"vorhofflimmern|atrial\s*fibrillation|afib", re.IGNORECASE), "afib_suspected"),
    (re.compile(r"unregelm[aä]ßig", re.IGNORECASE), "irregular_unspecified"),
    (re.compile(r"normal|regelm[aä]ßig", re.IGNORECASE), "normal"),
]


def _extract_text(pdf_path: Path) -> str:
    import pdfplumber
    parts = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        for page in pdf.pages:
            parts.append(page.extract_text() or "")
    return "\n".join(parts)


def _classify_result(snippet: str) -> str:
    for pattern, code in RESULT_CODE_MAP:
        if pattern.search(snippet):
            return code
    return "unknown"


def parse_report(text: str) -> dict | None:
    m_ts = re.search(r"Herzrhythmusmessung durchgef[uü]hrt am:\s*(\d{4}-\d{2}-\d{2})\s+(\d{1,2}:\d{2})", text)
    if not m_ts:
        return None
    ts = f"{m_ts.group(1)}T{m_ts.group(2)}:00"
    date = m_ts.group(1)

    # "Messung erhalten am: / Messung ueberprueft am: / Geraet:" sind ein
    # 3-Spalten-Layout: alle drei Label auf einer Zeile, alle drei Werte
    # (Datum+Zeit, Datum+Zeit, Geraetename) zusammen auf der naechsten Zeile
    # (pdfplumber extrahiert Tabellenspalten so, nicht zeilenweise je Label).
    m_block = re.search(
        r"Messung erhalten am:.*?Ger[aä]t:\s*\n"
        r"(\d{4}-\d{2}-\d{2}\s+\d{1,2}:\d{2})\s+"
        r"(\d{4}-\d{2}-\d{2}\s+\d{1,2}:\d{2})\s+(.+)",
        text)
    ts_reviewed = None
    recording_device = None
    if m_block:
        rd, rt = m_block.group(2).split()
        ts_reviewed = f"{rd}T{rt}:00"
        recording_device = m_block.group(3).strip()

    m_result = re.search(
        r"(Ihr Herzrhythmus\s+.*?meldeten\s+(?:KEINE\s+)?SYMPTOME\.)", text, re.DOTALL)
    result_text = " ".join(m_result.group(1).split()) if m_result else None
    result_code = _classify_result(result_text or "")

    m_hr = re.search(r"Durchschnitt betr[aä]gt\s*(\d+(?:[.,]\d+)?)\s*Schl[aä]ge", text)
    hr_avg = float(m_hr.group(1).replace(",", ".")) if m_hr else None

    m_activity = re.search(r"der Aktivit[aä]t\s+([\s\S]+?)\s+nachgegangen", text)
    activity_context = " ".join(m_activity.group(1).split()) if m_activity else None

    symptoms_reported = 1 if re.search(r"meldeten\s+SYMPTOME", text, re.IGNORECASE) else \
        (0 if re.search(r"meldeten\s+KEINE\s+SYMPTOME", text, re.IGNORECASE) else None)

    m_algo = re.search(r"Algorithmus-Version:\s*(\S+)", text)
    algorithm_version = m_algo.group(1) if m_algo else None

    panel_reviewed = 1 if re.search(r"Expertengremium\s+[uü]berpr[uü]ft", text) else 0

    return {
        "ts": ts, "ts_reviewed": ts_reviewed, "date": date,
        "result_code": result_code, "result_text": result_text,
        "hr_avg_bpm": hr_avg, "activity_context": activity_context,
        "symptoms_reported": symptoms_reported,
        "recording_device": recording_device,
        "algorithm_version": algorithm_version,
        "panel_reviewed": panel_reviewed,
    }


def _archive_original(pdf_path: Path, ziel: Path) -> None:
    _scrub_pdf_metadata(pdf_path, ziel)
    pdf_path.unlink()


def run(conn, data_path, lang: str = 'de', person: str | None = None):
    from modules.base import ImportResult
    person = resolve_person(person)
    pdf_path = Path(data_path)
    if not pdf_path.exists():
        return ImportResult("import_fibricheck", 0, 0,
                             [t(f"Nicht gefunden: {pdf_path}", f"Not found: {pdf_path}")])

    text = _extract_text(pdf_path)
    parsed = parse_report(text)
    if not parsed:
        return ImportResult("import_fibricheck", 0, 1,
                             [t(f"Kein Messzeitpunkt gefunden: {pdf_path.name}",
                                f"No measurement timestamp found: {pdf_path.name}")])

    PDF_DIR.mkdir(parents=True, exist_ok=True)
    ORIGINALE_DIR.mkdir(parents=True, exist_ok=True)
    ziel = ORIGINALE_DIR / pdf_path.name

    cur = conn.execute("""
        INSERT OR IGNORE INTO fibricheck_sessions
        (ts, ts_reviewed, date, result_code, result_text, hr_avg_bpm,
         activity_context, symptoms_reported, recording_device,
         algorithm_version, panel_reviewed, person, source_file)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        parsed["ts"], parsed["ts_reviewed"], parsed["date"],
        parsed["result_code"], parsed["result_text"], parsed["hr_avg_bpm"],
        parsed["activity_context"], parsed["symptoms_reported"],
        parsed["recording_device"], parsed["algorithm_version"],
        parsed["panel_reviewed"], person, pdf_path.name,
    ))
    rows_inserted = cur.rowcount
    log_import(conn, "import_fibricheck", pdf_path.name, rows_inserted, person=person)
    conn.commit()

    _archive_original(pdf_path, ziel)

    msg = t(f"  → {parsed['date']}: {parsed['result_code']} (HR∅ {parsed['hr_avg_bpm']})",
            f"  → {parsed['date']}: {parsed['result_code']} (HR avg {parsed['hr_avg_bpm']})")
    return ImportResult("import_fibricheck", rows_inserted, 1 - rows_inserted, [msg])


def main():
    parser = argparse.ArgumentParser(description=t("FibriCheck-PDF → health.db", "FibriCheck PDF → health.db"))
    parser.add_argument("pdfs", nargs="+", metavar="PDF", help="PDF-Dateien")
    parser.add_argument("--person", default=None, help=t("Ziel-Person (Default: OWN_PERSON_ID)", "Target person (default: OWN_PERSON_ID)"))
    add_lang_arg(parser)
    args = parser.parse_args()
    apply_lang_from_args(args)

    conn = open_db()
    total = 0
    for pdf_str in args.pdfs:
        result = run(conn, pdf_str, person=args.person)
        for msg in result.errors:
            print(msg)
        total += result.rows_inserted
    conn.close()
    print(t(f"\n{total} FibriCheck-Bericht(e) importiert.", f"\n{total} FibriCheck report(s) imported."))


if __name__ == "__main__":
    main()
