#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Omron Connect → health.db

@tier        infrastructure
@purpose.de  Importiert Blutdruckmessungen aus Omron Connect CSV-Exporten in die
             health.db. Ergänzt Apple Health um spezifische Omron-Daten wie
             IHB-Flag, mögliches Vorhofflimmern (AFib), TruRead und vollständige
             Messreihen.
@purpose.en  Imports blood pressure measurements from Omron Connect CSV exports
             into health.db. Supplements Apple Health with specific Omron data
             such as IHB flag, possible atrial fibrillation (AFib), TruRead, and
             complete measurement series.
@method.de   Liest CSV-Dateien aus dem Omron-Verzeichnis und parst die
             Blutdruckmessungen. Unterstützt Omron AFib-fähige Blutdruckmessgeräte.
             Ergänzende Daten: IHB (Irregulärer Herzschlag), AFib-Erkennung,
             TruRead (mehrfache Messungen), vollständige Messreihe.
@method.en   Reads CSV files from the Omron directory and parses blood pressure
             measurements. Supports Omron AFib-capable blood pressure monitors.
             Additional data: IHB (Irregular Heartbeat), AFib detection,
             TruRead (multiple measurements), complete measurement series.
@reads       {imports/omron/}*.csv (Omron Connect Export)
@writes      health.db (blood_pressure)
@limits.de   Keine Validierung der Omron-Datenqualität. Abhängig von der
             Korrektheit des CSV-Exports. Keine medizinische Bewertung aus IHB/AFib.

@relevance.de  Ermöglicht den Import von Gesundheitsdaten, essentiell für die umfassende Datenanalyse
@relevance.en  Enables import of health data, essential for comprehensive data analysis
@limits.en   No validation of Omron data quality. Dependent on the correctness
             of the CSV export. No medical evaluation from IHB/AFib data.
@usage
    python3 import_omron.py                   # all CSVs in Omron/
    python3 import_omron.py --update          # only neue Daten
    python3 import_omron.py --file export.csv
"""

import argparse
import csv
from datetime import datetime
from pathlib import Path
import sys as _sys
_sys.path.insert(0, str(Path(__file__).parent.parent))
from health_config import Config as _Cfg, OWN_PERSON_ID
from modules.db import open_db
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from modules.base import log_import
_cfg = _Cfg()

DB_PATH = _cfg.db_path
OMRON_DIR = _cfg.omron_dir
OMRON_DIR.mkdir(parents=True, exist_ok=True)

DE_MONTHS = {
    "jan": 1, "feb": 2, "mär": 3, "mar": 3, "apr": 4,
    "mai": 5, "jun": 6, "jul": 7, "aug": 8,
    "sep": 9, "okt": 10, "nov": 11, "dez": 12
}


def parse_de_date(date_str: str, time_str: str) -> str | None:
    """'18 ', '16:52' → '2024-01-18T16:52:00'"""
    try:
        parts = date_str.strip().split()
        if len(parts) != 3:
            return None
        day   = int(parts[0])
        month = DE_MONTHS.get(parts[1].lower().rstrip("."), 0)
        year  = int(parts[2])
        if not month:
            return None
        t = time_str.strip()
        if len(t) == 5:
            t += ":00"
        return f"{year:04d}-{month:02d}-{day:02d}T{t}"
    except Exception:
        return None


def flag(val: str) -> int | None:
    v = val.strip()
    if not v or v == "-":
        return 0
    if v.upper() in ("X", "✓", "✔", "JA", "YES", "TRUE", "1"):
        return 1
    return None


def get_last_import(conn) -> str | None:
    r = conn.execute(
        "SELECT MAX(date) FROM blood_pressure WHERE person=? AND source='omron_connect'",
        (OWN_PERSON_ID,)
    ).fetchone()
    return r[0] if r and r[0] else None


def import_csv(conn, filepath: Path, update_from: str | None) -> int:
    rows = []
    # columns: 0=Datum, 1=Zeit, 2=Systolisch, 3=Diastolisch, 4=Puls,
    # 5=Symptoms, 6=Eingenommen, 7=TruRead, 8=IHB, 9=Bewegung, 10=Manschette,
    # 11=Positionierung, 12=Messmodus, 13=Error, 14=AFib, 15=Device, 16=Notizen
    with open(filepath, encoding="utf-8-sig", errors="replace") as f:
        reader = csv.reader(f)
        next(reader, None)
        for parts in reader:
            # Manche Omron-Exporte mischen zwei Zeilenformate: volle Zeilen
            # (16 Spalten, mit Puls/Geraet/Symptome) und ein reduziertes
            # Format mit nur 4 Spalten (Datum, Zeit, Systolisch, Diastolisch,
            # kein Puls). Vorher wurden Kurzzeilen komplett verworfen — bei
            # gemischten Exporten macht das reduzierte Format den Grossteil
            # der Zeilen aus, sodass fast alle Messungen stillschweigend
            # uebersprungen wurden. g() liefert fuer fehlende Spalten ohnehin
            # "" (None nach der Typkonvertierung unten), daher reicht die
            # Mindestlaenge fuer Datum+Zeit+Sys+Dia.
            if len(parts) < 4:
                continue
            def g(i): return parts[i].strip() if i < len(parts) else ""

            dt = parse_de_date(g(0), g(1))
            if not dt:
                continue

            date = dt[:10]
            if update_from and date < update_from:
                continue

            try:
                rows.append((
                    dt, date,
                    int(g(2)) if g(2) and g(2) != "-" else None,
                    int(g(3)) if g(3) and g(3) != "-" else None,
                    int(g(4)) if g(4) and g(4) != "-" else None,
                    flag(g(8)), flag(g(14)),
                    g(7) if g(7) and g(7) != "-" else None,
                    g(5) if g(5) and g(5) != "-" else None,
                    g(9) if g(9) and g(9) != "-" else None,
                    g(10) if g(10) and g(10) != "-" else None,
                    'omron_bp',
                    g(16) if g(16) and g(16) != "-" else None,
                    OWN_PERSON_ID,
                    'omron_connect',
                ))
            except Exception:
                continue

    if rows:
        conn.executemany("""
            INSERT OR IGNORE INTO blood_pressure
            (ts, date, systolic, diastolic, pulse,
             ihb_flag, afib_possible, truread, symptoms,
             movement, cuff_ok, device_id, notes, person, source)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, rows)
        log_import(conn, 'omron_connect', str(filepath), len(rows))
        conn.commit()

    return len(rows)


def main():
    """
    Hauptfunktion: Koordiniert den Import der Omron Blutdruckdaten.

    Command-Line-Argumente:
        --file: Bestimmte CSV-Datei
        --update: Nur neue Daten
    """
    parser = argparse.ArgumentParser(description=t("Omron Connect → health.db", "Omron Connect → health.db"))
    parser.add_argument("--file",   help="Bestimmte CSV-File")
    parser.add_argument("--update", action="store_true", help=t("Nur neue Daten", "Only new data"))
    add_lang_arg(parser)

    args = parser.parse_args()
    apply_lang_from_args(args)

    conn = open_db()
    conn.execute("PRAGMA journal_mode=WAL")

    update_from = None
    if args.update:
        last = get_last_import(conn)
        if last:
            from datetime import timedelta
            d = datetime.strptime(last, "%Y-%m-%d")
            update_from = (d + timedelta(days=1)).strftime("%Y-%m-%d")
            print(t(f"Update-Modus: ab {update_from}", f"Update mode: from {update_from}"))

    files = ([Path(args.file)] if args.file
             else sorted(OMRON_DIR.glob("*.csv")) + sorted(OMRON_DIR.glob("*.CSV")))

    if not files:
        print(t(f"Keine CSV-Dateien in {OMRON_DIR}", f"No CSV files in {OMRON_DIR}"))
        return

    total = 0
    for f in files:
        print(f"  {f.name} ...", flush=True)
        n = import_csv(conn, f, update_from)
        total += n
        print(t(f"    {n} Einträge", f"    {n} entries"))

    r = conn.execute(
        "SELECT COUNT(*), MIN(date), MAX(date),"
        " SUM(CASE WHEN ihb_flag=1 THEN 1 ELSE 0 END),"
        " SUM(CASE WHEN afib_possible=1 THEN 1 ELSE 0 END),"
        " ROUND(AVG(systolic),1), ROUND(AVG(diastolic),1)"
        " FROM blood_pressure WHERE person=? AND source='omron_connect'",
        (OWN_PERSON_ID,)
    ).fetchone()

    print(t("\n── Omron Blutdruck ──────────────────────────────────────────────", "\n── Omron blood pressure ─────────────────────────────────────────"))
    print(t(f"  Gesamt: {r[0]} Messungen | {r[1]} – {r[2]}", f"  Total: {r[0]} measurements | {r[1]} – {r[2]}"))
    print(t(f"  IHB-Events: {r[3]} | AFib-Verdacht: {r[4]}", f"  IHB events: {r[3]} | AFib suspected: {r[4]}"))
    print(f"  ∅ {r[5]}/{r[6]} mmHg")
    conn.close()


if __name__ == "__main__":
    main()
