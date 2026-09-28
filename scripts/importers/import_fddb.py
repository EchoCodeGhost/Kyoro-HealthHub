#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
FDDB Ernährungs-Export → health.db (nutrition_entries, nutrition_daily, body_composition)

@tier infrastructure
@purpose.de Import von Ernährungsdaten und Körpermessungen aus der FDDB-App/Website
@purpose.en Import nutrition data and body measurements from FDDB app/website
@method.de Parsen von diary_*.csv (Ernährungstagebuch), userhistory_*.csv (Gewichtsverlauf)
           und complete_*.csv (FDDBs kombinierter Export, enthält beide als Sektionen,
           getrennt durch Marker-Zeilen wie "diary;"/"userhistory;"). Ernährungsdaten
           werden in nutrition_entries gespeichert und täglich aggregiert. Gewichts- und
           Körperdaten werden in body_composition gespeichert.
@method.en Parse diary_*.csv (nutrition diary), userhistory_*.csv (weight history), and
           complete_*.csv (FDDB's combined export, contains both as sections separated
           by marker lines like "diary;"/"userhistory;"). Nutrition data is stored in
           nutrition_entries and aggregated daily. Weight and body data is stored in
           body_composition.
@reads ~/Kyoro-HealthHub/imports/fddb/diary_*.csv, ~/Kyoro-HealthHub/imports/fddb/userhistory_*.csv,
       ~/Kyoro-HealthHub/imports/fddb/complete_*.csv
@writes health.db:nutrition_entries, health.db:nutrition_daily, health.db:body_composition, health.db:import_log
@limits.de Verarbeitet nur FDDB-spezifische CSV-Formate. Referenzwerte werden als Float geparst.

@relevance.de  Ermöglicht den Import von Gesundheitsdaten, essentiell für die umfassende Datenanalyse
@relevance.en  Enables import of health data, essential for comprehensive data analysis
@limits.en Only processes FDDB-specific CSV formats. Reference values are parsed as float.
@usage python3 import_fddb.py           # all CSVs
       python3 import_fddb.py --update  # only neue entries ergänzen
"""

import argparse
import csv
import re
import sqlite3
from pathlib import Path
import sys as _sys
_sys.path.insert(0, str(Path(__file__).parent.parent))
from health_config import Config as _Cfg
from modules.db import open_db
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from modules.base import log_import, resolve_person

_cfg = _Cfg()
DB_PATH  = _cfg.db_path
FDDB_DIR = _cfg.data_root / "fddb"
FDDB_DIR.mkdir(parents=True, exist_ok=True)


def _num(v: str) -> float | None:
    """Parsen eines numerischen Werts aus String mit Komma-Unterstützung.
    
    @purpose.de Konvertierung von deutschen Zahlenformaten (Komma als Dezimaltrennzeichen) zu Float
    @purpose.en Convert German number formats (comma as decimal separator) to float
    @method.de Ersetzt Komma durch Punkt vor der Float-Konvertierung
    @method.en Replace comma with period before float conversion
    @param v Numerischer String (z.B. '12,5' oder '12.5')
    @returns Float-Wert oder None bei Parse-Fehler
    """
    if not v:
        return None
    try:
        return float(v.strip().replace(',', '.'))
    except (ValueError, TypeError):
        return None


def _parse_fddb_dt(raw: str) -> tuple[str, str, str] | None:
    """Parsen eines FDDB-Datums- und Zeitstrings in ISO-Format.
    
    @purpose.de Konvertierung von FDDB-spezifischen Datumsformaten (TT.MM.JJJJ) zu ISO
    @purpose.en Convert FDDB-specific date formats (DD.MM.YYYY) to ISO
    @method.de Parsen von 'TT.MM.JJJJ HH:MM' oder 'TT.MM.JJJJ' und Rückgabe als (datetime, date, time)
    @method.en Parse 'DD.MM.YYYY HH:MM' or 'DD.MM.YYYY' and return as (datetime, date, time)
    @param raw Datumsstring im FDDB-Format
    @returns Tuple aus (ISO-datetime, ISO-date, time_str) oder None
    """
    raw = raw.strip().strip('"')
    if ' ' in raw:
        date_part, time_part = raw.rsplit(' ', 1)
    else:
        date_part, time_part = raw, '00:00'
    try:
        d, m, y = date_part.split('.')
        date_iso = f"{y}-{m.zfill(2)}-{d.zfill(2)}"
        dt_iso   = f"{date_iso}T{time_part}"
        return dt_iso, date_iso, time_part
    except Exception:
        return None


_SECTION_MARKER_RE = re.compile(r'^[a-z_]+;$')


def _extract_fddb_section(lines: list[str], section: str) -> list[str]:
    """Extrahiert eine benannte Sektion aus einem FDDB complete_*.csv-Kombi-Export.

    @purpose.de FDDBs "vollständiger Export" bündelt userhistory, diary und weitere
                Datentypen in einer Datei, getrennt durch Marker-Zeilen wie "diary;".
    @purpose.en FDDB's "complete export" bundles userhistory, diary, and other data
                types in one file, separated by marker lines like "diary;".
    @method.de Sucht die Marker-Zeile "{section};", sammelt alle folgenden Zeilen bis
               zur nächsten Marker-Zeile oder Dateiende (Header + Datenzeilen der Sektion).
    @method.en Finds the "{section};" marker line, collects all following lines until
               the next marker line or end of file (section header + data rows).
    @param lines Alle Zeilen der complete_*.csv-Datei
    @param section Sektionsname ohne Semikolon, z. B. "diary" oder "userhistory"
    @returns Header- und Datenzeilen der Sektion, leer wenn Sektion nicht vorhanden
    """
    out: list[str] = []
    in_section = False
    for line in lines:
        stripped = line.strip()
        if _SECTION_MARKER_RE.match(stripped):
            in_section = stripped == f"{section};"
            continue
        if in_section:
            out.append(line)
    return out


def _diary_rows_from_reader(reader: csv.DictReader, person: str) -> list[tuple]:
    rows = []
    for row in reader:
        parsed = _parse_fddb_dt(row.get('datum_tag_monat_jahr_stunde_minute', ''))
        if not parsed:
            continue
        dt_iso, date_iso, time_str = parsed
        rows.append((
            dt_iso, date_iso, time_str,
            row.get('bezeichnung', '').strip().strip('"'),
            row.get('interne_id', '').strip().strip('"') or None,
            _num(row.get('kj', '')),
            _num(row.get('fett_g', '')),
            _num(row.get('kh_g', '')),
            _num(row.get('protein_g', '')),
            person, 'fddb',
        ))
    return rows


def import_fddb_diary(conn: sqlite3.Connection, fddb_dir: Path, update_only: bool, person: str | None = None) -> int:
    """Import von Ernährungstagebuch-Daten aus FDDB CSV-Dateien.

    @purpose.de Verarbeitung von diary_*.csv und der diary-Sektion aus complete_*.csv
                mit Tagesbucheintragungen
    @purpose.en Process diary_*.csv and the diary section of complete_*.csv with
                daily nutrition entries
    @method.de Parsen jeder CSV-Datei, Extraktion von Datum, Uhrzeit, Lebensmittelname,
               Makronährstoffen und Energiegehalt. Speicherung in nutrition_entries.
    @method.en Parse each CSV file, extract date, time, food name, macronutrients,
               and energy content. Store in nutrition_entries.
    @param conn SQLite-Datenbankverbindung
    @param fddb_dir Verzeichnis mit FDDB CSV-Dateien
    @param update_only Nur neue Einträge einfügen (INSERT OR IGNORE)
    @returns Anzahl der importierten Einträge
    """
    person = resolve_person(person)
    diary_files = sorted(fddb_dir.glob("diary_*.csv"))
    complete_files = sorted(fddb_dir.glob("complete_*.csv"))
    rows = []
    for csv_path in diary_files:
        with open(csv_path, newline='', encoding='utf-8-sig') as f:
            rows += _diary_rows_from_reader(csv.DictReader(f, delimiter=';'), person)
    for csv_path in complete_files:
        lines = csv_path.read_text(encoding='utf-8-sig').splitlines()
        section = _extract_fddb_section(lines, 'diary')
        if section:
            rows += _diary_rows_from_reader(csv.DictReader(section, delimiter=';'), person)
    mode = "OR IGNORE"
    conn.executemany(
        "INSERT " + mode + " INTO nutrition_entries "
        "(ts, date, time_str, name, product_id, energy_kj, fat_g, carbs_g, protein_g, person, source) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?)", rows)
    conn.commit()
    return len(rows)


def _weight_rows_from_reader(reader: csv.DictReader, person: str) -> list[tuple]:
    rows = []
    for row in reader:
        raw_date = row.get('datum_tag_monat_jahr', '').strip().strip('"')
        if not raw_date:
            continue
        try:
            d, m, y = raw_date.split('.')
            date_iso = f"{y}-{m.zfill(2)}-{d.zfill(2)}"
        except Exception:
            continue
        ts = f"{date_iso}T12:00:00"
        rows.append((
            ts, date_iso,
            _num(row.get('gewicht_kg', '')),
            None,  # bmi
            _num(row.get('koerperfett_prozent', '')),
            _num(row.get('wassergehalt_prozent', '')),
            None,  # muscle_pct
            None,  # bone_kg
            None, None, None, None, None, None,  # fat segments
            None, None, None, None, None,        # muscle segments
            None, None, None,                    # metabolic_age, visceral_fat, pulse_bpm
            _num(row.get('taillenumfang_cm', '')),
            _num(row.get('hueftumfang_cm', '')),
            None,                                # comment
            None,                                # device_id
            person, 'fddb',
        ))
    return rows


def import_fddb_weight(conn: sqlite3.Connection, fddb_dir: Path, update_only: bool, person: str | None = None) -> int:
    """Import von Gewichts- und Körpermessdaten aus FDDB userhistory CSV-Dateien.

    @purpose.de Verarbeitung von userhistory_*.csv und der userhistory-Sektion aus
                complete_*.csv mit Gewichtsverlauf und Körperdaten
    @purpose.en Process userhistory_*.csv and the userhistory section of complete_*.csv
                with weight history and body measurements
    @method.de Parsen von userhistory CSV, Extraktion von Gewicht, Körperfettanteil,
               Wassergehalt, Taillenumfang und Hüftumfang. Speicherung in body_composition.
               Fügt ggf. fehlende Spalten zur Tabelle hinzu.
    @method.en Parse userhistory CSV, extract weight, body fat percentage,
               water content, waist and hip circumference. Store in body_composition.
               Add missing columns to table if needed.
    @param conn SQLite-Datenbankverbindung
    @param fddb_dir Verzeichnis mit FDDB CSV-Dateien
    @param update_only Nur neue Einträge einfügen (INSERT OR IGNORE)
    @returns Anzahl der importierten Messungen
    """
    person = resolve_person(person)
    weight_files = sorted(fddb_dir.glob("userhistory_*.csv"))
    complete_files = sorted(fddb_dir.glob("complete_*.csv"))
    rows = []
    for csv_path in weight_files:
        with open(csv_path, newline='', encoding='utf-8-sig') as f:
            rows += _weight_rows_from_reader(csv.DictReader(f, delimiter=';'), person)
    for csv_path in complete_files:
        lines = csv_path.read_text(encoding='utf-8-sig').splitlines()
        section = _extract_fddb_section(lines, 'userhistory')
        if section:
            rows += _weight_rows_from_reader(csv.DictReader(section, delimiter=';'), person)
    # Spalten nachrüsten falls DB älter als Schema
    for col, typ in [("waist_cm", "REAL"), ("hip_cm", "REAL")]:
        try:
            conn.execute(f"ALTER TABLE body_composition ADD COLUMN {col} {typ}")
            conn.commit()
        except Exception:
            pass
    mode = "OR IGNORE"
    conn.executemany(
        "INSERT " + mode + " INTO body_composition "
        "(ts, date, weight_kg, bmi, body_fat_pct, water_pct, muscle_pct, bone_kg, "
        "fat_arm_left, fat_arm_right, fat_leg_left, fat_leg_right, fat_trunk, fat_visceral_pct, "
        "muscle_arm_left, muscle_arm_right, muscle_leg_left, muscle_leg_right, muscle_trunk, "
        "metabolic_age, visceral_fat, pulse_bpm, waist_cm, hip_cm, comment, device_id, person, source) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        rows)
    conn.commit()
    return len(rows)


def aggregate_daily(conn: sqlite3.Connection, person: str | None = None) -> int:
    """Aggregation von Ernährungsdaten zu täglichen Summen.
    
    @purpose.de Berechnung täglicher Kalorien- und Makronährstoffsummen aus nutrition_entries
    @purpose.en Calculate daily calorie and macronutrient sums from nutrition_entries
    @method.de Löscht bestehende Einträge in nutrition_daily für Quelle 'fddb',
               dann Aggregation nach Datum mit SUM für alle Nährstoffe.
               Konvertierung von kJ zu kcal (1 kcal = 4.184 kJ).
    @method.en Delete existing entries in nutrition_daily for source 'fddb',
               then aggregate by date with SUM for all nutrients.
               Convert kJ to kcal (1 kcal = 4.184 kJ).
    @param conn SQLite-Datenbankverbindung
    @returns Anzahl der aggregierten Tage
    """
    person = resolve_person(person)
    conn.execute("DELETE FROM nutrition_daily WHERE source='fddb'")
    conn.execute(
        "INSERT INTO nutrition_daily"
        " (date, kcal, fat_g, carbs_g, protein_g, meal_count, last_meal, person, source)"
        " SELECT date, ROUND(SUM(energy_kj)/4.184,1), ROUND(SUM(fat_g),1),"
        " ROUND(SUM(carbs_g),1), ROUND(SUM(protein_g),1), COUNT(*), MAX(time_str), ?, 'fddb'"
        " FROM nutrition_entries WHERE source='fddb' GROUP BY date",
        (person,)
    )
    conn.commit()
    return conn.execute("SELECT COUNT(*) FROM nutrition_daily WHERE source='fddb'").fetchone()[0]


def main():
    """Hauptfunktion für den FDDB-Import.
    
    @purpose.de Orchestrierung des Import-Prozesses für Ernährungs- und Körperdaten
    @purpose.en Orchestrate import process for nutrition and body data
    @method.de Parsen von CLI-Argumenten, Verarbeitung von Tagebuch- und Gewichtsdateien,
               Aggregation der Ernährungsdaten, Anzeige von Statistiken
    @method.en Parse CLI arguments, process diary and weight files,
               aggregate nutrition data, display statistics
    """
    parser = argparse.ArgumentParser(description=t("FDDB Nutrition-Export → health.db", "FDDB Nutrition Export → health.db"))
    parser.add_argument("--update", action="store_true",
                        help="Only neue entries ergänzen (no Überschreiben)")
    parser.add_argument("--fddb-dir", metavar="DIR", default=None)
    parser.add_argument("--person", default=None, help="Ziel-Person (Default: OWN_PERSON_ID)")
    add_lang_arg(parser)

    args = parser.parse_args()
    apply_lang_from_args(args)
    person = resolve_person(args.person)

    fddb_dir = Path(args.fddb_dir) if args.fddb_dir else FDDB_DIR
    if not fddb_dir.exists():
        print(t(f"FDDB-Verzeichnis nicht gefunden: {fddb_dir}", f"FDDB directory not found: {fddb_dir}"))
        raise SystemExit(1)

    conn = open_db()
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")

    print(t("\n── FDDB ───────────────────────────────────────────────", "\n── FDDB ───────────────────────────────────────────────"))
    n_diary = import_fddb_diary(conn, fddb_dir, args.update, person)
    print(t(f"  {n_diary} Tagebuch-Einträge verarbeitet", f"  {n_diary} diary entries processed"))
    n_weight = import_fddb_weight(conn, fddb_dir, args.update, person)
    print(t(f"  {n_weight} Gewichtsmessungen verarbeitet", f"  {n_weight} weight measurements processed"))
    nd = aggregate_daily(conn, person)
    print(t(f"  {nd} Tage aggregiert (nutrition_daily)", f"  {nd} days aggregated (nutrition_daily)"))

    for q, lbl in [
        ("SELECT COUNT(*) FROM nutrition_entries WHERE source='fddb'", "nutrition_entries"),
        ("SELECT COUNT(*) FROM nutrition_daily WHERE source='fddb'",   "nutrition_daily"),
        ("SELECT COUNT(*) FROM body_composition WHERE source='fddb'",  "body_composition"),
    ]:
        count = conn.execute(q).fetchone()[0]
        print(t(f"  {lbl:<28} {count:>6} Einträge", f"  {lbl:<28} {count:>6} entries"))

    log_import(conn, 'fddb', str(fddb_dir), n_diary + n_weight, person=person)
    conn.commit()
    conn.close()


if __name__ == "__main__":
    main()
