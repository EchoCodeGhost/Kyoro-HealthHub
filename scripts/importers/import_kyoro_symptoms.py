#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Kyoro SymptomTrack CSV-Export → health.db (symptoms)

@tier        infrastructure
@purpose.de  Importiert Kyoro SymptomTrack CSV-Exporte
@purpose.en  Imports Kyoro SymptomTrack CSV exports
@method.de   Liest symptom-history*.csv Exporte aus der Kyoro SymptomTrack App und
             schreibt in die gemeinsame symptoms-Tabelle (source='kyoro_st').
             Gegenueber dem Symptomtagebuch-Importer hat Kyoro ST:
               - volle ISO-Timestamps (ts-Spalte)
               - Koerperregion (body_region-Spalte)
               - Notizen (notes-Spalte)
             PRIMARY KEY (date, symptom, person, source): bei mehrfachem Eintrag
             desselben Symptoms am selben Tag gewinnt der Eintrag mit dem hoechsten Wert.
             CSV-Format (multi-sektionell) mit Metadaten, Eintraegen pro Tag, etc.
@method.en   Reads symptom-history*.csv exports from the Kyoro SymptomTrack app and
             writes to the common symptoms table (source='kyoro_st').
             Compared to the symptom diary importer, Kyoro ST has:
               - full ISO timestamps (ts column)
               - body region (body_region column)
               - notes (notes column)
             PRIMARY KEY (date, symptom, person, source): for multiple entries
             of the same symptom on the same day, the entry with the highest value wins.
             CSV format (multi-sectional) with metadata, entries per day, etc.
@reads       CSV-Dateien aus imports/kyoro-ST/
@writes      symptoms
@limits.de   Multi-sektionelles Format. Abhaengig von App-Export.
             run()/import_file() reichten person schon vorher korrekt durch;
             main() hatte aber kein --person-Flag, war also faktisch trotzdem fest
             auf die eigene Person verdrahtet. Jetzt ergaenzt; --rebuild loescht
             dadurch auch nur noch die Eintraege der gewaehlten Person.

@relevance.de  Ermöglicht den Import von Symptomdaten, essentiell für die klinische Analyse
@relevance.en  Enables import of symptom data, essential for clinical analysis
@limits.en   Multi-sectional format. Dependent on app export.
             run()/import_file() already threaded person through correctly, but
             main() had no --person flag, so it was still effectively hardcoded
             to the own person. Now added; --rebuild consequently only deletes
             the selected person's entries.
@usage
    python3 import_kyoro_symptoms.py            # alle CSVs in imports/kyoro-ST/
    python3 import_kyoro_symptoms.py --update   # nur neue Eintraege
    python3 import_kyoro_symptoms.py --file /pfad/symptom-history.csv
    python3 import_kyoro_symptoms.py --rebuild  # kyoro_st-Eintraege loeschen + neu
    python3 import_kyoro_symptoms.py --person PER-xxxxxxxx
"""

import argparse
import csv
import io
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from health_config import Config as _Cfg, OWN_PERSON_ID
from modules.db import open_db
from modules.base import ImportResult, log_import, resolve_person
from modules.i18n import t, add_lang_arg, apply_lang_from_args

_cfg    = _Cfg()
CSV_DIR = Path(_cfg._cfg.get("paths", {}).get(
    "kyoro_st_dir",
    str(_cfg.data_root / "kyoro-ST")
))
CSV_DIR.mkdir(parents=True, exist_ok=True)

SOURCE = "kyoro_st"


# ── Schema-Erweiterung ────────────────────────────────────────────────────────

def _extend_symptoms(conn) -> None:
    """Ergänzt symptoms um ts, body_region, notes falls noch nicht vorhanden."""
    existing = {row[1] for row in conn.execute("PRAGMA table_info(symptoms)").fetchall()}
    for col, typedef in [
        ("ts",          "TEXT"),
        ("body_region", "TEXT"),
        ("notes",       "TEXT"),
    ]:
        if col not in existing:
            conn.execute(f"ALTER TABLE symptoms ADD COLUMN {col} {typedef}")
    conn.commit()


# ── CSV-Parser ────────────────────────────────────────────────────────────────

_ENTRY_HEADER = {"date", "time", "Symptom auswählen", "Wert"}


def _parse_csv(path: Path) -> list[dict]:
    """Extrahiert die 'Einträge'-Sektion aus dem Kyoro SymptomTrack CSV."""
    text  = path.read_bytes().decode("utf-8-sig")
    lines = text.splitlines()

    start = None
    for i, line in enumerate(lines):
        fields = {f.strip() for f in line.split(",")}
        if _ENTRY_HEADER.issubset(fields):
            start = i
            break

    if start is None:
        return []

    reader = csv.DictReader(io.StringIO("\n".join(lines[start:])))
    entries = []
    for row in reader:
        if not row.get("date", "").strip():
            break
        entries.append(row)
    return entries


# ── Import ────────────────────────────────────────────────────────────────────

def _to_utc(ts_raw: str) -> str | None:
    ts_raw = ts_raw.strip().replace("Z", "+00:00")
    if not ts_raw:
        return None
    try:
        return datetime.fromisoformat(ts_raw).astimezone(timezone.utc).isoformat()
    except ValueError:
        return None


def import_file(conn, path: Path, person: str = OWN_PERSON_ID) -> ImportResult:
    result  = ImportResult(source=f"kyoro_st:{path.name}")
    entries = _parse_csv(path)
    if not entries:
        return result

    # Pro (date, symptom) den Eintrag mit dem höchsten Wert behalten
    best: dict[tuple, dict] = {}
    for e in entries:
        ts_raw  = e.get("time", "").strip()
        symptom = e.get("Symptom auswählen", "").strip()
        date    = e.get("date", "").strip()
        if not symptom or not date:
            continue

        raw_val = e.get("Wert", "").strip()
        if raw_val.lower() in ("true", "false"):
            value_num  = None
            value_text = raw_val.lower()
        else:
            try:
                value_num  = float(raw_val) if raw_val else None
                value_text = None
            except ValueError:
                value_num  = None
                value_text = raw_val or None

        key = (date, symptom)
        existing = best.get(key)
        if existing is None or (value_num or 0) > (existing.get("value_num") or 0):
            best[key] = {
                "date":        date,
                "symptom":     symptom,
                "value_num":   value_num,
                "value_text":  value_text,
                "ts":          _to_utc(ts_raw),
                "body_region": e.get("Körperregion", "").strip() or None,
                "notes":       e.get("Notizen", "").strip() or None,
            }

    rows = [
        (v["date"], v["symptom"], v["value_num"], v["value_text"],
         None, person, SOURCE, v["ts"], v["body_region"], v["notes"])
        for v in best.values()
    ]

    if rows:
        conn.executemany("""
            INSERT OR IGNORE INTO symptoms
            (date, symptom, value_num, value_text,
             category, person, source, ts, body_region, notes)
            VALUES (?,?,?,?,?,?,?,?,?,?)
        """, rows)
        for v in best.values():
            if v.get("notes"):
                conn.execute(
                    "INSERT OR IGNORE INTO user_context"
                    " (id, date, ts_start, ts_end, person, source, source_app, tag, note)"
                    " VALUES (?,?,?,?,?,?,?,?,?)",
                    (f"kyoro_st:{v['date']}:{v['symptom']}", v["date"], None, None,
                     person, 'kyoro_st', 'kyoro_st', v["symptom"], v["notes"]),
                )
        log_import(conn, 'kyoro_symptoms', str(path), len(rows))
        conn.commit()
        result.rows_inserted = len(rows)
    else:
        result.rows_skipped = len(entries)

    return result


def run(conn, _data_path=None, lang: str = "de",
        person: str | None = None) -> ImportResult:
    person = person or OWN_PERSON_ID
    total  = ImportResult(source="kyoro_st")
    _extend_symptoms(conn)

    for f in sorted(CSV_DIR.glob("symptom-history*.csv")):
        r = import_file(conn, f, person)
        total.rows_inserted += r.rows_inserted
        total.rows_skipped  += r.rows_skipped
        total.errors.extend(r.errors)

    return total


# ── Hauptprogramm ─────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description=t("Kyoro SymptomTrack CSV → symptoms",
                      "Kyoro SymptomTrack CSV → symptoms"))
    parser.add_argument("--file",    metavar="PATH",
                        help=t("Einzelne CSV-Datei", "Single CSV file"))
    parser.add_argument("--update",  action="store_true",
                        help=t("Nur neue Einträge", "New entries only"))
    parser.add_argument("--rebuild", action="store_true",
                        help=t("kyoro_st-Einträge löschen + neu",
                               "Delete kyoro_st entries and reimport"))
    parser.add_argument("--person", default=None, metavar="PERSON_ID",
                        help=t("Person-ID (Standard: eigene Person aus Config)",
                               "Person ID (default: own person from config)"))
    add_lang_arg(parser)
    args = parser.parse_args()
    apply_lang_from_args(args)
    person = resolve_person(args.person)

    conn = open_db()
    conn.execute("PRAGMA journal_mode=WAL")
    _extend_symptoms(conn)

    if args.rebuild:
        conn.execute("DELETE FROM symptoms WHERE source=? AND person=?", (SOURCE, person))
        conn.commit()
        print(t("kyoro_st-Einträge gelöscht.", "kyoro_st entries deleted."))

    files = [Path(args.file).expanduser()] if args.file \
            else sorted(CSV_DIR.glob("symptom-history*.csv"))

    if not files:
        print(t(f"Keine symptom-history*.csv in {CSV_DIR}",
                f"No symptom-history*.csv in {CSV_DIR}"))
        sys.exit(0)

    total_ins = total_skip = 0
    for f in files:
        r = import_file(conn, f, person)
        total_ins  += r.rows_inserted
        total_skip += r.rows_skipped
        print(f"  {f.name}: {r.rows_inserted} neu, {r.rows_skipped} bereits vorhanden")

    print(t(f"\n  Gesamt: {total_ins} Einträge, {total_skip} übersprungen",
            f"\n  Total: {total_ins} entries, {total_skip} skipped"))

    r = conn.execute(
        "SELECT COUNT(*), COUNT(DISTINCT symptom), MIN(date), MAX(date) "
        "FROM symptoms WHERE source=? AND person=?", (SOURCE, person)
    ).fetchone()
    print(t(f"  symptoms (kyoro_st): {r[0]} Zeilen | {r[1]} Symptome | {r[2]} → {r[3]}",
            f"  symptoms (kyoro_st): {r[0]} rows | {r[1]} symptoms | {r[2]} → {r[3]}"))
    conn.close()


if __name__ == "__main__":
    main()
