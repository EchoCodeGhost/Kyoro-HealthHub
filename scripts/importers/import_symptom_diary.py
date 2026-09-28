#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Symptomtagebuch CSV → health.db (symptoms)

@tier infrastructure
@purpose.de Import von Symptomdaten aus der Symptom diary-App (Adam C.) für Longitudinal-Analysen
@purpose.en Import symptom data from Symptom diary app (Adam C.) for longitudinal analysis
@method.de Parsen von CSV-Dateien mit breitem Format (ein Symptom pro Spalte, ein Tag pro Zeile).
           Werte-Mapping auf numerische Skala (0-4) und Speicherung in symptoms-Tabelle.
           Kategorie-Zuordnung über KATEGORIE_DEFAULTS und DB-Abfrage.
@method.en Parse CSV files with wide format (one symptom per column, one day per row).
           Value mapping to numeric scale (0-4) and storage in symptoms table.
           Category assignment via KATEGORIE_DEFAULTS and DB lookup.
@reads ~/Kyoro-HealthHub/imports/symptomtagebuch/*.csv, health.db:symptoms, health.db:user_context
@writes health.db:symptoms, health.db:user_context, health.db:import_log
@limits.de Verarbeitet nur Dateien im CSV-Format. Notizen werden separat in user_context gespeichert.
           Historische Daten können nicht nachträglich geändert werden (INSERT OR IGNORE).

@relevance.de  Ermöglicht den Import von Symptomdaten, essentiell für die klinische Analyse
@relevance.en  Enables import of symptom data, essential for clinical analysis
@limits.en Only processes CSV files. Notes are stored separately in user_context.
           Historical data cannot be modified retroactively (INSERT OR IGNORE).
@usage python3 import_symptom_diary.py         # all CSVs
       python3 import_symptom_diary.py --update # only neue Daten
"""

import argparse
import csv
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
import sys as _sys
_sys.path.insert(0, str(Path(__file__).parent.parent))
from health_config import Config as _Cfg, OWN_PERSON_ID
from modules.db import open_db
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from modules.base import log_import
_cfg = _Cfg()

DB_PATH = _cfg.db_path
CSV_DIR = _cfg.symptom_diary_dir
CSV_DIR.mkdir(parents=True, exist_ok=True)

# Kategorie-Mapping: Symptom → Kategorie
# Wird aus der DB geladen + durch dieses Dict ergänzt
KATEGORIE_DEFAULTS = {
    # Erkältung
    "Verstopfte Nase": "Erkältung", "Schnupfen": "Erkältung",
    "Husten": "Erkältung", "Trockene Nasenschleimhaut": "Erkältung",
    "Halsschmerzen": "Erkältung", "Schüttelfrost": "Erkältung",
    # Erschöpfung/Neurologie
    "Konzentrationsstörungen": "Erschöpfung/Neurologie",
    "Erschöpfung/Fatigue": "Erschöpfung/Neurologie",
    "Wandernde Schmerzen": "Erschöpfung/Neurologie",
    "Kribbeln/Taubheit": "Erschöpfung/Neurologie",
    "Wortfindungsstörungen": "Erschöpfung/Neurologie",
    "Tinnitus": "Erschöpfung/Neurologie",
    "Herzrasen": "Erschöpfung/Neurologie",
    "Lymphknotenschwellung": "Erschöpfung/Neurologie",
    "Atemnot (physiologisch)": "Erschöpfung/Neurologie",
    # Sensorisch/Neurologie
    "Autistischer Shutdown": "Sensorisch/Neurologie", "Autistischer Meltdown": "Sensorisch/Neurologie",
    "Mutismus": "Sensorisch/Neurologie", "Geräuschempfindlichkeit": "Sensorisch/Neurologie",
    "Masking-Aufwand": "Sensorisch/Neurologie", "Sensorischer Overload": "Sensorisch/Neurologie",
    "Sprachliche Erschöpfung": "Sensorisch/Neurologie", "Lichtempfindlichkeit": "Sensorisch/Neurologie",
    # Ressourcen
    "Energie-Budget Morgens": "Ressourcen",
    "Energie-Budget Abends": "Ressourcen",
    "Sicherheitsgefühl": "Ressourcen",
    # Psyche
    "Flashbacks/Intrusionen": "Psyche",
    "Albträume": "Psyche",
    "Hypervigilianz - Anspannungslevel": "Psyche",
    "Dissoziationen": "Psyche",
    "Atemnot (Panik)": "Sonstiges",
    # Schmerz
    "Gelenkschmerzen": "Schmerz", "Muskelschmerzen": "Schmerz",
    "Gelenksteife": "Schmerz", "Körperschmerz": "Schmerz",
    "Bauchschmerzen": "Schmerz", "Nackensteifigkeit": "Schmerz",
    "Zahnschmerzen": "Schmerz",
    # Auge
    "Trockenes Auge": "Auge", "Augenschmerzen": "Auge",
    "Sehstörungen": "Auge", "Augentropfen/-spray": "Auge",
    "Augensalbe": "Auge",
    # Balsoraum/GI
    "Blähungen": "Bauchraum/GI", "Verstopfung": "Bauchraum/GI",
    "Durchfall": "Bauchraum/GI",
    # Behandlung
    "Inhalation Mit Inhalationsgerät": "Behandlung",
    "Inhalation (ohne Inhalationsgerät)": "Behandlung",
    "Nasendusche (abschwellend‬ 2.95g Salz)": "Behandlung",
    "Nasendusche (Standard‬ 2.5g Salz)": "Behandlung",
    "Meersalz Nasenspray": "Behandlung",
    "Abschwellendes Nasenspray": "Behandlung",
    "Nasensalbe": "Behandlung",
    "Erkältungsbad": "Behandlung",
    "Erkältungsmittel": "Behandlung",
    "Flow Neuroscience": "Behandlung",
    "Novafon": "Behandlung",
    "Massagepistole": "Behandlung",
    "TENS": "Behandlung",
    "TENS mit Wärme": "Behandlung",
    "Faszienrolle": "Behandlung",
    "Physiotherapie": "Behandlung",
    "Notfallmedikament (Psyche)": "Behandlung",
    "Arztbesuch": "Behandlung",
    "Operation": "Behandlung",
}

# Übersprungene columns (no Symptom)
SKIP_COLS = {"Datum", "Tag", "Krankheit", "Notizen"}

# Germane Monatsnamen
DE_MONTHS = {
    "jan": 1, "feb": 2, "mär": 3, "mar": 3, "apr": 4,
    "mai": 5, "jun": 6, "jul": 7, "aug": 8,
    "sep": 9, "okt": 10, "nov": 11, "dez": 12
}


def parse_de_date(s: str) -> str | None:
    """Parsen eines deutschen Datumsstrings in ISO-Format.
    
    @purpose.de Konvertierung von Datumsstrings im Format '11 mär 2024' zu '2024-03-11'
    @purpose.en Convert date strings in format '11 mar 2024' to '2024-03-11'
    @method.de Nutzt DE_MONTHS-Mapping für Monatsnamen und gibt None bei Parse-Fehlern zurück
    @method.en Uses DE_MONTHS mapping for month names, returns None on parse errors
    @param s Datumsstring im Format 'Tag Monat Jahr' (z.B. '11 mär 2024')
    @returns ISO-Datumsstring (YYYY-MM-DD) oder None
    """
    parts = s.strip().split()
    if len(parts) != 3:
        return None
    try:
        day   = int(parts[0])
        month = DE_MONTHS.get(parts[1].lower().rstrip("."), 0)
        year  = int(parts[2])
        if not month:
            return None
        return f"{year:04d}-{month:02d}-{day:02d}"
    except Exception:
        return None


def parse_wert(val: str) -> tuple[float | None, str]:
    """Parsen von Symptomwerten aus CSV in numerische und Text-Repräsentation.
    
    @purpose.de Mapping von textuellen Werten zu numerischer Skala für Symptomstärke
    @purpose.en Map textual values to numeric scale for symptom severity
    @method.de Nutzt festes Mapping für deutsche und numerische Werte. Freitext wird als wert_text gespeichert.
    @method.en Uses fixed mapping for German and numeric values. Free text is stored as wert_text.
    @param val Wert aus CSV (z.B. 'Leicht', '2', 'Freitext Notiz')
    @returns Tuple aus (wert_num: float|None, wert_text: str)
    """
    v = val.strip()
    if not v or v == "-":
        return 0.0, "0"
    mapping = {
        "keine": 0.0, "0": 0.0,
        "leicht": 1.0, "1": 1.0,
        "mäßig": 2.0, "2": 2.0,
        "schwer": 3.0, "3": 3.0,
        "sehr schwer": 4.0, "4": 4.0,
        "ja": 1.0, "nein": 0.0,
    }
    lower = v.lower()
    if lower in mapping:
        return mapping[lower], v
    # Numerisch?
    try:
        num = float(v.replace(",", "."))
        return num, v
    except ValueError:
        pass
    # Freitext (e.g. Notizen)
    return None, v


def load_kategorie_map(conn: sqlite3.Connection) -> dict:
    """Laden bekannter Symptom-zu-Kategorie-Zuordnungen aus der Datenbank.
    
    @purpose.de Ergänzung der statischen KATEGORIE_DEFAULTS um benutzerdefinierte Zuordnungen aus der DB
    @purpose.en Augment static KATEGORIE_DEFAULTS with user-defined mappings from DB
    @method.de Abfrage der symptoms-Tabelle nach bestehenden category-Zuordnungen für OWN_PERSON_ID
    @method.en Query symptoms table for existing category assignments for OWN_PERSON_ID
    @param conn SQLite-Datenbankverbindung
    @returns Dictionary mit Symptom → Kategorie-Mapping
    """
    result = dict(KATEGORIE_DEFAULTS)
    try:
        for sym, kat in conn.execute(
            "SELECT DISTINCT symptom, category FROM symptoms WHERE category IS NOT NULL AND person=?",
            (OWN_PERSON_ID,)
        ).fetchall():
            result[sym] = kat
    except Exception:
        pass
    return result


def get_last_import(conn: sqlite3.Connection) -> str | None:
    """Ermitteln des letzten Import-Datums aus der symptoms-Tabelle.
    
    @purpose.de Bestimmung des Startdatums für Update-Importe
    @purpose.en Determine start date for update imports
    @method.de Abfrage des maximalen Datums aus symptoms für source='symptomtagebuch'
    @method.en Query maximum date from symptoms for source='symptomtagebuch'
    @param conn SQLite-Datenbankverbindung
    @returns Letztes Import-Datum als String (YYYY-MM-DD) oder None
    """
    r = conn.execute("SELECT MAX(date) FROM symptoms WHERE person=? AND source='symptomtagebuch'", (OWN_PERSON_ID,)).fetchone()
    return r[0] if r and r[0] else None


def import_csv(conn: sqlite3.Connection, filepath: Path,
               kat_map: dict, update_from: str | None) -> int:
    """Import einer einzelnen Symptomtagebuch-CSV-Datei.
    
    @purpose.de Verarbeitung einer CSV-Datei und Speicherung der Symptomdaten in der DB
    @purpose.en Process a CSV file and store symptom data in the database
    @method.de Parsen der CSV mit DictReader, Mapping der Werte, Speicherung in symptoms und user_context
    @method.en Parse CSV with DictReader, map values, store in symptoms and user_context
    @param conn SQLite-Datenbankverbindung
    @param filepath Pfad zur CSV-Datei
    @param kat_map Kategorie-Mapping (Symptom → Kategorie)
    @param update_from Nur Daten ab diesem Datum importieren (für Update-Modus)
    @returns Anzahl der importierten Tage
    """
    rows = []
    with open(filepath, encoding="utf-8-sig", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            date = parse_de_date(row.get("Datum", ""))
            if not date:
                continue
            if update_from and date < update_from:
                continue

            # Notizen separat
            notiz = row.get("Notizen", "").strip()
            if notiz and notiz != "-":
                rows.append((date, "Notizen", None, notiz,
                             "Sonstiges", OWN_PERSON_ID, "symptomtagebuch"))
                conn.execute(
                    "INSERT OR IGNORE INTO user_context"
                    " (id, date, ts_start, ts_end, person, source, source_app, tag, note)"
                    " VALUES (?,?,?,?,?,?,?,?,?)",
                    (f"symptom_diary:{date}", date, None, None,
                     OWN_PERSON_ID, 'symptom_diary', 'symptom_diary', None, notiz),
                )

            for symptom, raw_val in row.items():
                if symptom in SKIP_COLS:
                    continue
                sym = symptom.strip()
                wert_num, wert_text = parse_wert(raw_val)
                kat = kat_map.get(sym, "Sonstiges")
                rows.append((date, sym, wert_num, wert_text, kat, OWN_PERSON_ID, "symptomtagebuch"))

    if rows:
        conn.executemany("""
            INSERT OR IGNORE INTO symptoms
            (date, symptom, value_num, value_text, category, person, source)
            VALUES (?,?,?,?,?,?,?)
        """, rows)
        conn.commit()

    return len(set(r[0] for r in rows))


def main():
    """Hauptfunktion für den Symptomtagebuch-Import.
    
    @purpose.de Orchestrierung des Import-Prozesses für alle CSV-Dateien im Verzeichnis
    @purpose.en Orchestrate import process for all CSV files in the directory
    @method.de Lädt Kategorie-Mapping, prüft Update-Modus, verarbeitet alle CSV-Dateien,
               zeigt Statistik an und speichert Import-Log
    @method.en Load category mapping, check update mode, process all CSV files,
               display statistics and save import log
    """
    parser = argparse.ArgumentParser(description=t("Symptomtagebuch → health.db", "Symptom diary → health.db"))
    parser.add_argument("--update", action="store_true", help="Only neue Daten")
    add_lang_arg(parser)

    args = parser.parse_args()
    apply_lang_from_args(args)

    conn = open_db()
    conn.execute("PRAGMA journal_mode=WAL")

    kat_map = load_kategorie_map(conn)

    update_from = None
    if args.update:
        last = get_last_import(conn)
        if last:
            d = datetime.strptime(last, "%Y-%m-%d") + timedelta(days=1)
            update_from = d.strftime("%Y-%m-%d")
            print(t(f"Update-Modus: ab {update_from}", f"Update mode: from {update_from}"))

    files = sorted(CSV_DIR.glob("*.csv")) + sorted(CSV_DIR.glob("*.CSV"))
    if not files:
        print(t(f"Keine CSV-Dateien in {CSV_DIR}", f"No CSV files in {CSV_DIR}"))
        return

    total_days = 0
    for f in files:
        print(f"  {f.name} ...", flush=True)
        n = import_csv(conn, f, kat_map, update_from)
        total_days += n
        print(t(f"    {n} Tage importiert", f"    {n} days imported"))

    r = conn.execute(
        "SELECT COUNT(DISTINCT date), MIN(date), MAX(date), COUNT(DISTINCT symptom) "
        "FROM symptoms WHERE person=? AND source='symptomtagebuch'",
        (OWN_PERSON_ID,)
    ).fetchone()

    print(t("\n── Symptomtagebuch ──────────────────────────────────────────", "\n── Symptom diary ───────────────────────────────────────────"))
    print(t(f"  {r[0]} Tage | {r[1]} – {r[2]} | {r[3]} verschiedene Symptome", f"  {r[0]} days | {r[1]} – {r[2]} | {r[3]} different symptoms"))
    log_import(conn, 'symptom_diary', str(CSV_DIR), total_days)
    conn.commit()
    conn.close()


if __name__ == "__main__":
    main()
