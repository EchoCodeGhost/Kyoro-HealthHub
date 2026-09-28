#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
import_symptomtagebuch.py — Symptomtagebuch-App CSV → Datenbank

@tier        infrastructure
@purpose.de  Importiert Tagesdaten aus der Symptomtagebuch-App CSV-Exporten in die health.db
@purpose.en  Imports daily data from Symptomtagebuch app CSV exports into health.db
@method.de   Importiert den 7-Tage-CSV-Bericht der Symptomtagebuch-App.
             Format: eine Zeile pro Tag, eine Spalte pro Kategorie.
             Schwergrade: Keine=0, Leicht=1, Maessig=2, Schwer=3, Ja=1, Nein=0, Zahl (0-9) direkt.
             Leere Werte oder "-" werden uebersprungen.
             Spaltentypen werden automatisch erkannt: Ja/Nein-Werte → category='behandlung', sonst 'kategorie'.
             Notizen werden in user_context gespeichert.
@method.en   Imports the 7-day CSV report from the Symptomtagebuch app.
             Format: one line per day, one column per category.
             Severity: None=0, Light=1, Moderate=2, Severe=3, Yes=1, No=0, Number (0-9) direct.
             Empty values or "-" are skipped.
             Column types are automatically detected: Yes/No values → category='behandlung', others 'category'.
             Notes are stored in user_context.
@reads       CSV-Dateien aus imports/symptomtagebuch/ Verzeichnis
@writes      Datenbanktabellen, user_context, import_log
@limits.de   Abhaengig vom CSV-Format der Symptomtagebuch-App. Keine medizinische Validierung.
             --person war frueher in run() deklariert aber ungenutzt (Schreibpfad
             fest auf OWN_PERSON_ID) und in main() gar nicht vorhanden — jetzt in
             beiden Pfaden durchgereicht; --rebuild loescht dadurch auch nur noch
             die Eintraege der gewaehlten Person, nicht mehr aller Personen.

@relevance.de  Ermöglicht den Import von Symptomdaten, essentiell für die klinische Analyse
@relevance.en  Enables import of symptom data, essential for clinical analysis
@limits.en   Depends on the CSV format of the Symptomtagebuch app. No medical validation.
             --person used to be declared in run() but unused (write path
             hardcoded to OWN_PERSON_ID) and absent from main() entirely — now
             threaded through both paths; --rebuild consequently only deletes
             the selected person's entries, not everyone's.
@usage
    python import_symptomtagebuch.py
    python import_symptomtagebuch.py --file bericht.csv
    python import_symptomtagebuch.py --dry-run
    python import_symptomtagebuch.py --rebuild
    python import_symptomtagebuch.py --file bericht.csv --person PER-xxxxxxxx
"""

import argparse
import csv
import io
import re
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from health_config import Config as _Cfg
from modules.db import open_db
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from modules.base import ImportResult, log_import, resolve_person

_cfg = _Cfg()

IMPORT_DIR = _cfg.data_root / "symptomtagebuch"

_DE_MONTHS = {
    "Januar": 1, "Februar": 2, "März": 3, "April": 4, "Mai": 5, "Juni": 6,
    "Juli": 7, "August": 8, "September": 9, "Oktober": 10, "November": 11,
    "Dezember": 12,
    "Jan": 1, "Feb": 2, "Mär": 3, "Apr": 4, "Jun": 6, "Jul": 7,
    "Aug": 8, "Sep": 9, "Okt": 10, "Nov": 11, "Dez": 12,
}

_SEVERITY = {
    "keine": 0,
    "leicht": 1,
    "mäßig": 2,
    "schwer": 3,
    "ja": 1,
    "nein": 0,
}

_SKIP_COLS = {"datum", "tag"}


def _parse_date(s: str) -> str | None:
    """'11 Mai 2026' → '2026-05-11'"""
    parts = s.strip().split()
    if len(parts) == 3:
        day, month_str, year = parts
        month = _DE_MONTHS.get(month_str)
        if month:
            return f"{year}-{month:02d}-{int(day):02d}"
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", s.strip())
    if m:
        return s.strip()[:10]
    return None


def _parse_value(raw: str) -> tuple[float | None, str | None]:
    """Gibt (value_num, value_text) zurück. None, None = überspringen."""
    v = raw.strip()
    if not v or v == "-":
        return None, None
    lower = v.lower()
    if lower in _SEVERITY:
        num = float(_SEVERITY[lower])
        return num, v
    try:
        return float(v), None
    except ValueError:
        return None, v


def _is_behandlung(col_values: list[str]) -> bool:
    """True wenn die Spalte überwiegend Ja/Nein-Werte enthält."""
    yn = sum(1 for v in col_values if v.strip().lower() in ("ja", "nein"))
    real = sum(1 for v in col_values if v.strip() and v.strip() != "-")
    return real > 0 and yn / real >= 0.7


def parse_csv(path: Path) -> list[dict]:
    """Gibt [{date, symptom, value_num, value_text, category, notes}] zurück."""
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    lines = [l for l in text.splitlines() if l.strip()]
    if not lines:
        return []

    reader = list(csv.DictReader(io.StringIO("\n".join(lines))))
    if not reader:
        return []

    # Spaltentyp vorab bestimmen (Behandlung vs Symptom)
    columns = [c for c in reader[0].keys() if c.lower() not in _SKIP_COLS]
    behandlung_cols = set()
    for col in columns:
        vals = [row.get(col, "") for row in reader]
        if _is_behandlung(vals):
            behandlung_cols.add(col)

    records = []
    for row in reader:
        date_str = _parse_date(row.get("Datum", ""))
        if not date_str:
            continue

        notiz = row.get("Notizen", "").strip()

        for col in columns:
            raw = row.get(col, "")
            if col == "Notizen":
                if raw.strip() and raw.strip() != "-":
                    records.append({
                        "date":       date_str,
                        "symptom":    "notiz",
                        "value_num":  None,
                        "value_text": raw.strip(),
                        "category":   "notiz",
                        "notes":      None,
                    })
                continue

            num, txt = _parse_value(raw)
            if num is None and txt is None:
                continue

            records.append({
                "date":       date_str,
                "symptom":    col,
                "value_num":  num,
                "value_text": txt,
                "category":   "behandlung" if col in behandlung_cols else "symptom",
                "notes":      notiz or None,
            })

    return records


def _save(conn, records: list[dict], person: str, dry_run: bool) -> int:
    neu = 0
    for r in records:
        if dry_run:
            val = r["value_num"] if r["value_num"] is not None else r["value_text"]
            print(f"  [dry] {r['date']}  {r['symptom']:<40}  {val}")
            neu += 1
            continue
        cur = conn.execute(
            """INSERT OR IGNORE INTO symptoms
               (date, symptom, value_num, value_text, category, person, source, notes)
               VALUES (?,?,?,?,?,?,?,?)""",
            (r["date"], r["symptom"], r["value_num"], r["value_text"],
             r["category"], person, "symptomtagebuch", r["notes"]),
        )
        if cur.rowcount:
            neu += 1
        if r["symptom"] == "notiz" and r.get("value_text"):
            conn.execute(
                "INSERT OR IGNORE INTO user_context"
                " (id, date, ts_start, ts_end, person, source, source_app, tag, note)"
                " VALUES (?,?,?,?,?,?,?,?,?)",
                (f"symptomtagebuch:{r['date']}", r["date"], None, None,
                 person, 'symptomtagebuch', 'symptomtagebuch',
                 None, r["value_text"]),
            )
    conn.commit()
    return neu


def run(conn, _data_path=None, lang: str = "de", person: str | None = None) -> ImportResult:
    apply_lang_from_args(type("A", (), {"lang": lang})())
    person = resolve_person(person)
    result = ImportResult(source="symptomtagebuch")
    if not IMPORT_DIR.exists():
        return result
    files = sorted(IMPORT_DIR.glob("*.csv"))
    for p in files:
        records = parse_csv(p)
        n = _save(conn, records, person, dry_run=False)
        result.rows_inserted += n
    log_import(conn, 'symptomtagebuch', str(IMPORT_DIR), result.rows_inserted)
    conn.commit()
    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description=t("Symptomtagebuch CSV importieren", "Import Symptomtagebuch CSV"))
    parser.add_argument("--file", metavar="CSV",
                        help=t("Einzelne CSV-Datei", "Single CSV file"))
    parser.add_argument("--update", action="store_true",
                        help=t("Nur neue Daten (INSERT OR IGNORE)", "Only new data (INSERT OR IGNORE)"))
    parser.add_argument("--dry-run", action="store_true",
                        help=t("Nur anzeigen, nicht schreiben", "Show only, do not write"))
    parser.add_argument("--rebuild", action="store_true",
                        help=t("Alle vorhandenen Einträge löschen und neu importieren",
                               "Delete existing entries and reimport"))
    parser.add_argument("--person", default=None, metavar="PERSON_ID",
                        help=t("Person-ID (Standard: eigene Person aus Config)",
                               "Person ID (default: own person from config)"))
    add_lang_arg(parser)
    args = parser.parse_args()
    apply_lang_from_args(args)
    person = resolve_person(args.person)

    conn = open_db()

    if args.file:
        files = [Path(args.file)]
    else:
        files = sorted(IMPORT_DIR.glob("*.csv")) if IMPORT_DIR.exists() else []

    if not files:
        print(t(f"Keine CSV-Dateien in {IMPORT_DIR}", f"No CSV files in {IMPORT_DIR}"))
        return

    if args.rebuild and not args.dry_run:
        conn.execute("DELETE FROM symptoms WHERE source='symptomtagebuch' AND person=?", (person,))
        conn.commit()
        print(t("Bestehende symptomtagebuch-Einträge gelöscht.", "Deleted existing entries."))

    total = 0
    for p in files:
        print(t(f"\n→ {p.name}", f"\n→ {p.name}"))
        records = parse_csv(p)
        if not records:
            print(t("  Keine Einträge gefunden.", "  No entries found."))
            continue
        print(t(f"  {len(records)} Einträge geparst", f"  {len(records)} entries parsed"))
        n = _save(conn, records, person, args.dry_run)
        print(t(f"  → {n} neu importiert", f"  → {n} newly imported"))
        total += n

    conn.close()

    if args.dry_run:
        print(t(f"\nDRY-RUN: {total} Einträge würden importiert.",
                f"\nDRY-RUN: {total} entries would be imported."))
    else:
        print(t(f"\nGesamt: {total} neue Einträge importiert.",
                f"\nTotal: {total} new entries imported."))


if __name__ == "__main__":
    main()
