#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Histamin-Trigger-Tagebuch → health.db (food_triggers + histamine_food_db)

@tier        infrastructure
@purpose.de  Importiert Histamin-Trigger-Tagebuch-Daten
@purpose.en  Imports histamine trigger diary data
@method.de   Dokumentiert Lebensmittel und auftretende Symptome.
             Beim ersten Lauf wird die Histamin-Referenzdatenbank befuellt.
             CSV-Format: ts,food_name,portion_g,reaction_h,symptoms,severity,meal_type,notes
             Histamin-Kategorien: high, medium, low, liberator, blocker.
@method.en   Documents food and occurring symptoms.
             On first run, the histamine reference database is populated.
             CSV format: ts,food_name,portion_g,reaction_h,symptoms,severity,meal_type,notes
             Histamine categories: high, medium, low, liberator, blocker.
@reads       CSV-Dateien aus ~/Kyoro-HealthHub/imports/histamine_diary/
@writes      food_triggers, histamine_food_db
@limits.de   Heuristische Kategorisierung. Abhaengig von Datenqualitaet.

@relevance.de  Ermöglicht den Import von Gesundheitsdaten, essentiell für die umfassende Datenanalyse
@relevance.en  Enables import of health data, essential for comprehensive data analysis
@limits.en   Heuristic categorization. Dependent on data quality.
@usage
    python3 import_histamine_diary.py           # alle CSVs
    python3 import_histamine_diary.py --manual  # interaktive Eingabe
    python3 import_histamine_diary.py --template
    python3 import_histamine_diary.py --show-db # Datenbank ausgeben
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
CSV_DIR = Path(_cfg._cfg.get("paths", {}).get("histamine_diary_dir",
          str(Path.home() / "Kyoro-HealthHub" / "imports" / "histamine_diary")))
CSV_DIR.mkdir(parents=True, exist_ok=True)

CSV_TEMPLATE = """\
# Histamin-Trigger-Tagebuch
# Spalten: ts,food_name,portion_g,reaction_h,symptoms,severity,meal_type,notes
#
# ts         : YYYY-MM-DDTHH:MM:SS
# food_name  : Lebensmittel (wird gegen Datenbank gemappt)
# portion_g  : Menge in Gramm (leer=unbekannt)
# reaction_h : Stunden bis Reaktion nach dem Essen (leer=keine)
# symptoms   : kommasepariert z.B. "Flush,Kopfschmerzen,Urtikaria"
# severity   : 0=keine 1=leicht 2=mäßig 3=stark 4=sehr stark
# meal_type  : breakfast | lunch | dinner | snack
# notes      : Freitext
#
ts,food_name,portion_g,reaction_h,symptoms,severity,meal_type,notes
"""

# Histamin-Referenzdatenbank: (name, cat, mg_100g, food_category, notes)
# Quellen: SIGHI 2016, Maintz & Novak 2007, Reese et al. 2018
HISTAMINE_DB = [
    # ── Hochhistaminhaltig ────────────────────────────────────────────────────
    ("Rotwein",              "high",      4.0,   "alcohol",    "bis 40 mg/L"),
    ("Weißwein",             "high",      0.4,   "alcohol",    "weniger als Rotwein"),
    ("Bier",                 "high",      0.6,   "alcohol",    "Hopfen enthält Histamin"),
    ("Sekt/Champagner",      "high",      None,  "alcohol",    "Hefe + Gärung"),
    ("Schnaps/Spirituosen",  "medium",    None,  "alcohol",    "DAO-Hemmer"),
    ("Thunfisch (Konserve)", "high",      50.0,  "fish",       "Lagerung erhöht stark"),
    ("Sardinen (Konserve)",  "high",      200.0, "fish",       "sehr hoch bei Konserven"),
    ("Makrele (Konserve)",   "high",      100.0, "fish",       None),
    ("Hering (mariniert)",   "high",      30.0,  "fish",       None),
    ("Lachs (geräuchert)",   "high",      20.0,  "fish",       "Räuchern erhöht"),
    ("Anchovis",             "high",      180.0, "fish",       None),
    ("Thunfisch (frisch)",   "low",       1.0,   "fish",       "frisch kochen, sofort essen"),
    ("Salami",               "high",      15.0,  "meat",       "Fermentierung"),
    ("Pepperoni",            "high",      20.0,  "meat",       None),
    ("Chorizo",              "high",      18.0,  "meat",       None),
    ("Schinken (gekocht)",   "medium",    5.0,   "meat",       "weniger als Rohschinken"),
    ("Rohschinken",          "high",      12.0,  "meat",       "Reifeprozess"),
    ("Hackfleisch (alt)",    "high",      None,  "meat",       "Lagerung kritisch"),
    ("Sauerkraut",           "high",      7.0,   "fermented",  "Lacto-Fermentation"),
    ("Kimchi",               "high",      10.0,  "fermented",  None),
    ("Miso",                 "high",      30.0,  "fermented",  None),
    ("Tempeh",               "high",      40.0,  "fermented",  None),
    ("Sojasoße",             "high",      25.0,  "fermented",  None),
    ("Fischsoße",            "high",      500.0, "fermented",  "sehr hoch"),
    ("Worcestersoße",        "high",      20.0,  "fermented",  None),
    ("Essig (Rotwein)",      "high",      None,  "fermented",  "Histamin + Liberator"),
    ("Essig (Apfel)",        "medium",    None,  "fermented",  "weniger als Rotweinessig"),
    ("Balsamico",            "high",      None,  "fermented",  None),
    ("Parmesan",             "high",      190.0, "dairy",      "gereifter Käse"),
    ("Camembert",            "high",      20.0,  "dairy",      None),
    ("Gouda (alt)",          "high",      15.0,  "dairy",      ">3 Monate Reifung"),
    ("Cheddar",              "high",      35.0,  "dairy",      None),
    ("Emmentaler",           "high",      25.0,  "dairy",      None),
    ("Gruyère",              "high",      50.0,  "dairy",      None),
    ("Harzer Käse",          "high",      60.0,  "dairy",      None),
    ("Joghurt",              "medium",    5.0,   "dairy",      "Fermentation, variabel"),
    ("Buttermilch",          "medium",    4.0,   "dairy",      None),
    ("Saure Sahne",          "medium",    3.0,   "dairy",      None),
    ("Quark",                "low",       1.0,   "dairy",      "frisch"),
    ("Frischkäse",           "low",       0.5,   "dairy",      None),
    ("Mozzarella (frisch)",  "low",       None,  "dairy",      "frisch essen"),
    ("Tomate",               "liberator", 10.0,  "vegetable",  "enthält auch Histamin"),
    ("Tomatensauce",         "high",      15.0,  "vegetable",  "konzentriert + gelagert"),
    ("Ketchup",              "high",      20.0,  "vegetable",  None),
    ("Spinat",               "high",      38.0,  "vegetable",  "höchste Gemüsewerte"),
    ("Aubergine",            "high",      26.0,  "vegetable",  None),
    ("Avocado",              "liberator", None,  "vegetable",  "Biogene Amine"),
    ("Erdbeeren",            "liberator", None,  "fruit",      "klassischer Liberator"),
    ("Himbeeren",            "liberator", None,  "fruit",      None),
    ("Zitrone",              "liberator", None,  "fruit",      "Citrusfrüchte allgemein"),
    ("Orange",               "liberator", None,  "fruit",      None),
    ("Grapefruit",           "liberator", None,  "fruit",      None),
    ("Ananas",               "liberator", None,  "fruit",      "Bromealin + Liberator"),
    ("Kiwi",                 "liberator", None,  "fruit",      None),
    ("Banane",               "liberator", 10.0,  "fruit",      "enthält Serotonin"),
    ("Papaya",               "liberator", None,  "fruit",      None),
    ("Weintrauben",          "medium",    None,  "fruit",      None),
    ("Schokolade",           "liberator", 20.0,  "other",      "Kakao + Theobromin"),
    ("Kakao",                "liberator", 30.0,  "other",      None),
    ("Nüsse (Walnuss)",      "liberator", None,  "other",      None),
    ("Nüsse (Erdnuss)",      "liberator", None,  "other",      None),
    ("Nüsse (Cashew)",       "liberator", None,  "other",      None),
    ("Hülsenfrüchte",        "medium",    None,  "other",      "variabel"),
    ("Linsen",               "medium",    3.0,   "other",      None),
    ("Eiweiß (roh)",         "liberator", None,  "other",      "hemmt DAO"),
    ("Schwarztee",           "blocker",   None,  "beverage",   "DAO-Hemmer"),
    ("Grüntee",              "blocker",   None,  "beverage",   "DAO-Hemmer"),
    ("Energydrinks",         "blocker",   None,  "beverage",   "Coffein + DAO-Hemmer"),
    ("Kaffee",               "blocker",   None,  "beverage",   "schwacher DAO-Hemmer"),
    # ── Niedrig / gut verträglich ─────────────────────────────────────────────
    ("Rindfleisch (frisch)", "low",       0.2,   "meat",       "frisch kochen"),
    ("Hühnchen (frisch)",    "low",       0.1,   "meat",       "frisch kochen"),
    ("Milch",                "low",       0.3,   "dairy",      None),
    ("Butter",               "low",       0.1,   "dairy",      None),
    ("Reis",                 "low",       None,  "grain",      None),
    ("Pasta (frisch)",       "low",       None,  "grain",      "frisch, kein Sourdough"),
    ("Brot (Hefe, frisch)",  "low",       None,  "grain",      None),
    ("Kartoffeln",           "low",       None,  "vegetable",  None),
    ("Zucchini",             "low",       None,  "vegetable",  None),
    ("Brokkoli",             "low",       None,  "vegetable",  None),
    ("Karotten",             "low",       None,  "vegetable",  None),
    ("Blumenkohl",           "low",       None,  "vegetable",  None),
    ("Salat (Kopf)",         "low",       None,  "vegetable",  None),
    ("Apfel",                "low",       None,  "fruit",      None),
    ("Birne",                "low",       None,  "fruit",      None),
    ("Mango",                "low",       None,  "fruit",      "frisch"),
    ("Wassermelone",         "low",       None,  "fruit",      None),
]


def _ensure_tables(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS food_triggers (
            ts TEXT NOT NULL, date TEXT NOT NULL, time_str TEXT,
            food_name TEXT NOT NULL, portion_g REAL, histamine_cat TEXT,
            reaction_h REAL, symptoms TEXT,
            severity INTEGER CHECK (severity BETWEEN 0 AND 4),
            meal_type TEXT, notes TEXT,
            person TEXT NOT NULL DEFAULT 'unknown',
            PRIMARY KEY (ts, food_name, person)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS histamine_food_db (
            name TEXT PRIMARY KEY, histamine_cat TEXT NOT NULL,
            histamine_mg_100g REAL, food_category TEXT, notes TEXT
        )
    """)
    # Seed-Daten eintragen (nur wenn noch nicht vorhanden)
    existing = conn.execute("SELECT COUNT(*) FROM histamine_food_db").fetchone()[0]
    if existing == 0:
        conn.executemany("""
            INSERT OR IGNORE INTO histamine_food_db
            (name, histamine_cat, histamine_mg_100g, food_category, notes)
            VALUES (?,?,?,?,?)
        """, HISTAMINE_DB)
        print(t(f"  Histamin-Datenbank: {len(HISTAMINE_DB)} Einträge befüllt.",
                f"  Histamine database: {len(HISTAMINE_DB)} entries populated."))


def _lookup_cat(conn, food_name: str) -> str | None:
    row = conn.execute(
        "SELECT histamine_cat FROM histamine_food_db WHERE lower(name)=lower(?)",
        (food_name,)
    ).fetchone()
    if row:
        return row[0]
    # Teilstring-Suche
    row = conn.execute(
        "SELECT histamine_cat FROM histamine_food_db WHERE lower(?) LIKE '%' || lower(name) || '%' OR lower(name) LIKE '%' || lower(?) || '%'",
        (food_name, food_name)
    ).fetchone()
    return row[0] if row else None


def _parse_row(row: dict, conn) -> dict | None:
    ts = row.get("ts", "").strip()
    if not ts:
        return None
    try:
        dt = datetime.fromisoformat(ts)
    except ValueError:
        print(t(f"  Ungültiges Datum: {ts}", f"  Invalid date: {ts}"))
        return None
    food = row.get("food_name", "").strip()
    if not food:
        return None

    hist_cat = row.get("histamine_cat", "").strip() or _lookup_cat(conn, food) or "unknown"

    def _f(k):
        v = row.get(k, "").strip()
        return float(v) if v else None

    def _i(k):
        v = row.get(k, "").strip()
        return int(v) if v else None

    return {
        "ts":           ts,
        "date":         dt.strftime("%Y-%m-%d"),
        "time_str":     dt.strftime("%H:%M"),
        "food_name":    food,
        "portion_g":    _f("portion_g"),
        "histamine_cat":hist_cat,
        "reaction_h":   _f("reaction_h"),
        "symptoms":     row.get("symptoms", "").strip() or None,
        "severity":     _i("severity"),
        "meal_type":    row.get("meal_type", "").strip() or None,
        "notes":        row.get("notes", "").strip() or None,
    }


def _insert(conn, rec, person) -> bool:
    try:
        conn.execute("""
            INSERT OR IGNORE INTO food_triggers
            (ts, date, time_str, food_name, portion_g, histamine_cat,
             reaction_h, symptoms, severity, meal_type, notes, person)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            rec["ts"], rec["date"], rec["time_str"], rec["food_name"],
            rec.get("portion_g"), rec["histamine_cat"], rec.get("reaction_h"),
            rec.get("symptoms"), rec.get("severity"), rec.get("meal_type"),
            rec.get("notes"), person,
        ))
        inserted = conn.total_changes > 0
        if inserted and rec.get("notes"):
            conn.execute(
                "INSERT OR IGNORE INTO user_context"
                " (id, date, ts_start, ts_end, person, source, source_app, tag, note)"
                " VALUES (?,?,?,?,?,?,?,?,?)",
                (f"histamine_diary:{rec['ts']}", rec["date"], rec["ts"], None,
                 person, 'histamine_diary', 'histamine_diary',
                 rec.get("food_name"), rec["notes"]),
            )
        return inserted
    except DB_ERRORS as e:
        print(t(f"  DB-Fehler: {e}", f"  DB error: {e}"))
        return False


def _import_csv(conn, path, person):
    inserted = skipped = 0
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(row for row in f if not row.startswith("#"))
        for row in reader:
            rec = _parse_row(row, conn)
            if rec is None:
                skipped += 1
                continue
            if _insert(conn, rec, person):
                inserted += 1
                react = (t(f"  → Reaktion {rec['reaction_h']}h", f"  → Reaction {rec['reaction_h']}h")
                         if rec.get("reaction_h") else "")
                cat   = rec['histamine_cat']
                print(f"    {rec['date']} {rec['time_str']}  {rec['food_name']} [{cat}]{react}")
            else:
                skipped += 1
    return inserted, skipped


def _manual_entry(conn, person):
    print(t("\n── Histamin-Trigger Eingabe ────────────────────────────────────",
            "\n── Histamine Trigger Entry ─────────────────────────────────────"))
    ts_str = input(t("Zeitpunkt (YYYY-MM-DDTHH:MM, Enter=jetzt): ",
                     "Time (YYYY-MM-DDTHH:MM, Enter=now): ")).strip()
    if not ts_str:
        ts_str = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    elif len(ts_str) == 16:
        ts_str += ":00"
    food = input(t("Lebensmittel: ", "Food: ")).strip()
    portion = input(t("Menge in g (leer=unbekannt): ", "Amount in g (empty=unknown): ")).strip()
    cat_auto = _lookup_cat(conn, food)
    if cat_auto:
        print(t(f"  → Datenbank: {food} = {cat_auto}", f"  → Database: {food} = {cat_auto}"))
    hist_cat = input(t(f"Histamin-Kategorie [{cat_auto or 'unknown'}] (Enter=übernehmen): ",
                       f"Histamine category [{cat_auto or 'unknown'}] (Enter=accept): ")).strip()
    reaction = input(t("Stunden bis Reaktion (leer=keine): ", "Hours until reaction (empty=none): ")).strip()
    symptoms = input(t("Symptome (kommasepariert): ", "Symptoms (comma-separated): ")).strip()
    severity = input(t("Schweregrad 0–4: ", "Severity 0–4: ")).strip()
    meal     = input(t("Mahlzeit (breakfast/lunch/dinner/snack): ", "Meal (breakfast/lunch/dinner/snack): ")).strip()
    notes    = input(t("Notizen: ", "Notes: ")).strip()

    rec = {
        "ts":           ts_str,
        "date":         ts_str[:10],
        "time_str":     ts_str[11:16],
        "food_name":    food,
        "portion_g":    float(portion) if portion else None,
        "histamine_cat":hist_cat or cat_auto or "unknown",
        "reaction_h":   float(reaction) if reaction else None,
        "symptoms":     symptoms or None,
        "severity":     int(severity) if severity else None,
        "meal_type":    meal or None,
        "notes":        notes or None,
    }
    if _insert(conn, rec, person):
        print(t(f"  ✓ {food} gespeichert.", f"  ✓ {food} saved."))
        conn.commit()
    else:
        print(t("  Bereits vorhanden oder Fehler.", "  Already exists or error."))


def main():
    parser = argparse.ArgumentParser(
        description=t("Histamin-Trigger-Tagebuch importieren", "Import histamine trigger diary"))
    parser.add_argument("--manual",   action="store_true")
    parser.add_argument("--template", action="store_true")
    parser.add_argument("--show-db",  action="store_true",
                        help=t("Histamin-Datenbank ausgeben", "Show histamine database"))
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
    _ensure_tables(conn)

    if args.show_db:
        rows = conn.execute(
            "SELECT name, histamine_cat, histamine_mg_100g, food_category FROM histamine_food_db ORDER BY histamine_cat, name"
        ).fetchall()
        print(t("\nHistamin-Datenbank:", "\nHistamine database:"))
        for r in rows:
            mg = f" ({r[2]} mg/100g)" if r[2] else ""
            print(f"  [{r[1]:10}] {r[0]:30} {r[3] or ''}{mg}")
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
        ins, skip = _import_csv(conn, f, person)
        total_ins += ins
        total_skip += skip
        print(t(f"  {f.name}: {ins} neu, {skip} übersprungen",
                f"  {f.name}: {ins} new, {skip} skipped"))

    log_import(conn, 'histamine_diary', str(CSV_DIR), total_ins, total_skip)
    conn.commit()
    conn.close()
    print(t(f"\nHistamin-Tagebuch: {total_ins} importiert, {total_skip} übersprungen.",
            f"\nHistamine diary: {total_ins} imported, {total_skip} skipped."))


if __name__ == "__main__":
    main()
