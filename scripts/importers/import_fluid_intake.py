#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Fluessigkeitsaufnahme → health.db (fluid_intake)

@tier        infrastructure
@purpose.de  Trackt taegliche Fluessigkeits- und Salzaufnahme
@purpose.en  Tracks daily fluid and salt intake
@method.de   Trackt taegliche Fluessigkeits- und Salzaufnahme.
             Ziele konfigurierbar via clinical.fluid_target_ml / clinical.sodium_target_mg.
             CSV-Format: ts,beverage,volume_ml,caffeine_mg,alcohol_g,sodium_mg,notes
             Beverages: water, tea, coffee, juice, broth, sports_drink, other
             Koffein-Lookup fuer Standardwerte.
@method.en   Tracks daily fluid and salt intake.
             Goals configurable via clinical.fluid_target_ml / clinical.sodium_target_mg.
             CSV format: ts,beverage,volume_ml,caffeine_mg,alcohol_g,sodium_mg,notes
             Beverages: water, tea, coffee, juice, broth, sports_drink, other
             Caffeine lookup for standard values.
@reads       CSV-Dateien aus ~/Kyoro-HealthHub/imports/fluid_intake/
@writes      fluid_intake
@limits.de   Abhaengig von manueller Eingabe.

@relevance.de  Ermöglicht den Import von Gesundheitsdaten, essentiell für die umfassende Datenanalyse
@relevance.en  Enables import of health data, essential for comprehensive data analysis
@limits.en   Dependent on manual input.
@usage
    python3 import_fluid_intake.py           # alle CSVs
    python3 import_fluid_intake.py --update  # nur neue Daten
    python3 import_fluid_intake.py --manual  # interaktive Eingabe
    python3 import_fluid_intake.py --template
    python3 import_fluid_intake.py --summary # Tagesuebersicht
"""

import argparse
import csv
import sqlite3
from datetime import datetime
from pathlib import Path
import sys as _sys
_sys.path.insert(0, str(Path(__file__).parent.parent))
from health_config import Config as _Cfg, OWN_PERSON_ID
from modules.db import open_db, DB_ERRORS
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from modules.base import log_import
_cfg = _Cfg()

DB_PATH = _cfg.db_path
CSV_DIR = Path(_cfg._cfg.get("paths", {}).get("fluid_intake_dir",
          str(Path.home() / "Kyoro-HealthHub" / "imports" / "fluid_intake")))
CSV_DIR.mkdir(parents=True, exist_ok=True)

# Tägliche Flüssigkeits- und Natriumziele — aus health_config.json (clinical.fluid_target_ml / clinical.sodium_target_mg)
_clinical        = _cfg._cfg.get("clinical", {})
FLUID_TARGET_ML  = int(_clinical.get("fluid_target_ml",  2500))
SODIUM_TARGET_MG = int(_clinical.get("sodium_target_mg", 3000))

# Koffein-Standardwerte pro 100 ml (mg)
CAFFEINE_PER_100ML = {
    "espresso":      200.0,
    "coffee":         36.0,
    "filterkaffee":   36.0,
    "kaffee":         36.0,
    "cappuccino":     24.0,
    "latte":          12.0,
    "schwarztee":     20.0,
    "black_tea":      20.0,
    "grüntee":        12.5,
    "green_tea":      12.5,
    "matcha":         35.0,
    "cola":           10.6,
    "energydrink":    32.0,
    "energy_drink":   32.0,
}

BEVERAGE_NAMES = {
    "water": "Wasser", "tea": "Tee", "coffee": "Kaffee", "juice": "Saft",
    "broth": "Brühe", "sports_drink": "Sportgetränk", "milk": "Milch",
    "cola": "Cola", "energydrink": "Energydrink", "other": "Sonstiges",
}

CSV_TEMPLATE = """\
# Flüssigkeitsaufnahme — CSV-Vorlage
# POTS-Ziel: 2500 ml Flüssigkeit + 3000 mg Natrium täglich
# Spalten: ts,beverage,volume_ml,caffeine_mg,alcohol_g,sodium_mg,notes
#
# ts          : YYYY-MM-DDTHH:MM:SS
# beverage    : water | tea | coffee | espresso | juice | broth | sports_drink | milk | cola | energydrink | other
# volume_ml   : Menge in ml
# caffeine_mg : Koffein (leer = automatisch aus Lookup)
# alcohol_g   : Alkohol in g (leer = 0)
# sodium_mg   : Natrium in mg (Elektrolyttablette ~460 mg, Salz 1g ~390 mg)
# notes       : Freitext
#
# Hilfswerte: Elektrolyttablette ~460 mg Na, 1 TL Salz (~5g) ~1950 mg Na
# 1 Glas Wasser = 250 ml, 1 Flasche = 500/750 ml, 1 Tasse = 200-250 ml
#
ts,beverage,volume_ml,caffeine_mg,alcohol_g,sodium_mg,notes
"""

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS fluid_intake (
    ts TEXT NOT NULL, date TEXT NOT NULL, time_str TEXT,
    beverage TEXT NOT NULL, volume_ml REAL NOT NULL,
    caffeine_mg REAL DEFAULT 0, alcohol_g REAL DEFAULT 0,
    sodium_mg REAL DEFAULT 0, notes TEXT,
    person TEXT NOT NULL DEFAULT 'unknown', source TEXT,
    PRIMARY KEY (ts, beverage, person)
)
"""


def _caffeine_lookup(beverage: str, volume_ml: float) -> float:
    key = beverage.lower().replace(" ", "_")
    rate = CAFFEINE_PER_100ML.get(key)
    if rate is None:
        for k, v in CAFFEINE_PER_100ML.items():
            if k in key or key in k:
                rate = v
                break
    if rate is None:
        return 0.0
    return round(rate * volume_ml / 100.0, 1)


def _parse_row(row: dict) -> dict | None:
    ts = row.get("ts", "").strip()
    if not ts:
        return None
    try:
        dt = datetime.fromisoformat(ts)
    except ValueError:
        print(t(f"  Ungültiges Datum: {ts}", f"  Invalid date: {ts}"))
        return None
    beverage = row.get("beverage", "").strip()
    vol_s    = row.get("volume_ml", "").strip()
    if not beverage or not vol_s:
        return None
    try:
        volume = float(vol_s)
    except ValueError:
        return None

    caf_s = row.get("caffeine_mg", "").strip()
    caffeine = float(caf_s) if caf_s else _caffeine_lookup(beverage, volume)

    def _f(k):
        v = row.get(k, "").strip()
        return float(v) if v else 0.0

    return {
        "ts":          ts,
        "date":        dt.strftime("%Y-%m-%d"),
        "time_str":    dt.strftime("%H:%M"),
        "beverage":    beverage,
        "volume_ml":   volume,
        "caffeine_mg": caffeine,
        "alcohol_g":   _f("alcohol_g"),
        "sodium_mg":   _f("sodium_mg"),
        "notes":       row.get("notes", "").strip() or None,
    }


def _insert(conn, rec, person, source) -> bool:
    try:
        conn.execute("""
            INSERT OR IGNORE INTO fluid_intake
            (ts, date, time_str, beverage, volume_ml, caffeine_mg, alcohol_g,
             sodium_mg, notes, person, source)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """, (
            rec["ts"], rec["date"], rec["time_str"], rec["beverage"],
            rec["volume_ml"], rec["caffeine_mg"], rec["alcohol_g"],
            rec["sodium_mg"], rec.get("notes"), person, source,
        ))
        inserted = conn.total_changes > 0
        if inserted and rec.get("notes"):
            conn.execute(
                "INSERT OR IGNORE INTO user_context"
                " (id, date, ts_start, ts_end, person, source, source_app, tag, note)"
                " VALUES (?,?,?,?,?,?,?,?,?)",
                (f"fluid:{rec['ts']}", rec["date"], rec["ts"], None,
                 person, 'fluid_intake', 'fluid_intake',
                 rec.get("beverage"), rec["notes"]),
            )
        return inserted
    except DB_ERRORS as e:
        print(t(f"  DB-Fehler: {e}", f"  DB error: {e}"))
        return False


def _import_csv(conn, path, person, update_only, source):
    inserted = skipped = 0
    if update_only:
        latest = conn.execute(
            "SELECT MAX(ts) FROM fluid_intake WHERE person=?", (person,)
        ).fetchone()[0] or "1900-01-01"
    else:
        latest = None

    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(row for row in f if not row.startswith("#"))
        for row in reader:
            if latest and row.get("ts", "") <= latest:
                skipped += 1
                continue
            rec = _parse_row(row)
            if rec is None:
                skipped += 1
                continue
            if _insert(conn, rec, person, source):
                inserted += 1
            else:
                skipped += 1
    return inserted, skipped


def _daily_summary(conn, person, days=7):
    rows = conn.execute("""
        SELECT date,
               SUM(volume_ml) as total_ml,
               SUM(caffeine_mg) as caf,
               SUM(sodium_mg) as na,
               SUM(alcohol_g) as alc
        FROM fluid_intake
        WHERE person=?
          AND date >= date('now', ? || ' days')
        GROUP BY date
        ORDER BY date DESC
    """, (person, f"-{days}")).fetchall()
    if not rows:
        print(t("Keine Flüssigkeitsdaten.", "No fluid intake data."))
        return
    print(t(f"\n── Flüssigkeitsaufnahme letzte {days} Tage ──────────────────────",
            f"\n── Fluid intake last {days} days ──────────────────────────────"))
    fluid_target = FLUID_TARGET_ML
    na_target    = SODIUM_TARGET_MG
    for d, ml, caf, na, alc in rows:
        fl_ok = "✓" if ml and ml >= fluid_target else "△"
        na_ok = "✓" if na and na >= na_target else "△"
        print(t(
            f"  {d}  {fl_ok} {ml:.0f} ml  Na {na_ok} {na:.0f} mg  "
            f"Koffein {caf:.0f} mg  Alkohol {alc:.1f} g",
            f"  {d}  {fl_ok} {ml:.0f} ml  Na {na_ok} {na:.0f} mg  "
            f"Caffeine {caf:.0f} mg  Alcohol {alc:.1f} g",
        ))
    print(t(f"\n  Ziele: {fluid_target} ml Flüssigkeit, {na_target} mg Natrium",
            f"\n  Targets: {fluid_target} ml fluid, {na_target} mg sodium"))


def _manual_entry(conn, person):
    print(t("\n── Flüssigkeitsaufnahme eingeben ───────────────────────────────",
            "\n── Enter fluid intake ──────────────────────────────────────────"))
    ts_str = input(t("Zeitpunkt (YYYY-MM-DDTHH:MM, Enter=jetzt): ",
                     "Time (YYYY-MM-DDTHH:MM, Enter=now): ")).strip()
    if not ts_str:
        ts_str = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    elif len(ts_str) == 16:
        ts_str += ":00"
    beverage = input(t("Getränk (water/coffee/tea/broth/...): ", "Beverage (water/coffee/tea/broth/...): ")).strip()
    volume   = input(t("Menge in ml: ", "Volume in ml: ")).strip()
    caf_s    = input(t("Koffein in mg (leer=auto): ", "Caffeine in mg (empty=auto): ")).strip()
    sodium   = input(t("Natrium in mg (leer=0): ", "Sodium in mg (empty=0): ")).strip()
    alcohol  = input(t("Alkohol in g (leer=0): ", "Alcohol in g (empty=0): ")).strip()
    notes    = input(t("Notizen: ", "Notes: ")).strip()

    try:
        vol = float(volume)
    except ValueError:
        print(t("Ungültige Menge.", "Invalid volume."))
        return

    caffeine = float(caf_s) if caf_s else _caffeine_lookup(beverage, vol)

    rec = {
        "ts":          ts_str,
        "date":        ts_str[:10],
        "time_str":    ts_str[11:16],
        "beverage":    beverage,
        "volume_ml":   vol,
        "caffeine_mg": caffeine,
        "alcohol_g":   float(alcohol) if alcohol else 0.0,
        "sodium_mg":   float(sodium) if sodium else 0.0,
        "notes":       notes or None,
    }
    if _insert(conn, rec, person, "manual"):
        print(t(f"  ✓ {beverage} {vol:.0f} ml gespeichert (Koffein: {caffeine:.0f} mg).",
                f"  ✓ {beverage} {vol:.0f} ml saved (caffeine: {caffeine:.0f} mg)."))
        conn.commit()
    else:
        print(t("  Bereits vorhanden oder Fehler.", "  Already exists or error."))


def main():
    parser = argparse.ArgumentParser(
        description=t("Flüssigkeitsaufnahme importieren", "Import fluid intake"))
    parser.add_argument("--update",   action="store_true")
    parser.add_argument("--manual",   action="store_true")
    parser.add_argument("--template", action="store_true")
    parser.add_argument("--summary",  action="store_true",
                        help=t("Tagesübersicht anzeigen", "Show daily summary"))
    parser.add_argument("--days",     type=int, default=7)
    parser.add_argument("--file",     type=str, default=None)
    parser.add_argument("--person",   type=str, default=None)
    add_lang_arg(parser)
    args = parser.parse_args()
    apply_lang_from_args(args)

    if args.template:
        print(CSV_TEMPLATE)
        return

    person = args.person or OWN_PERSON_ID
    conn   = open_db()
    conn.execute(CREATE_TABLE_SQL)

    if args.summary:
        _daily_summary(conn, person, args.days)
        conn.close()
        return

    if args.manual:
        _manual_entry(conn, person)
        conn.close()
        return

    files = [Path(args.file)] if args.file else sorted(CSV_DIR.glob("*.csv"))
    if not files:
        print(t(f"Keine CSV-Dateien in {CSV_DIR}. Vorlage: --template",
                f"No CSV files in {CSV_DIR}. Template: --template"))
        conn.close()
        return

    total_ins = total_skip = 0
    for f in files:
        ins, skip = _import_csv(conn, f, person, args.update, "csv")
        total_ins += ins
        total_skip += skip
        print(t(f"  {f.name}: {ins} neu, {skip} übersprungen",
                f"  {f.name}: {ins} new, {skip} skipped"))

    log_import(conn, 'fluid_intake', str(CSV_DIR), total_ins, total_skip)
    conn.commit()
    conn.close()
    print(t(f"\nFlüssigkeitsaufnahme: {total_ins} importiert, {total_skip} übersprungen.",
            f"\nFluid intake: {total_ins} imported, {total_skip} skipped."))


if __name__ == "__main__":
    main()
