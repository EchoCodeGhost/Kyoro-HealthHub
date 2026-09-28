#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Beurer Health Manager Pro → health.db

@tier        infrastructure
@purpose.de  Importiert CSV-Exporte des Beurer Health Manager Pro in die health.db.
             Unterstützt Körperzusammensetzung (BF 990), Blutzucker (GL 60),
             Körpertemperatur (FT 95) und Pulsoximetrie (PO60).
@purpose.en  Imports CSV exports from Beurer Health Manager Pro into health.db.
             Supports body composition (BF 990), blood glucose (GL 60),
             body temperature (FT 95), and pulse oximetry (PO60).
@method.de   Liest CSV-Dateien aus ~/Kyoro-HealthHub/imports/beurer/ oder einem
             expliziten Pfad. Jede CSV-Datei wird geparst und die Daten in die
             entsprechenden Tabellen geschrieben: body_composition, blood_glucose,
             measurements (body_temperature, spo2, heart_rate).
@method.en   Reads CSV files from ~/Kyoro-HealthHub/imports/beurer/ or an explicit
             path. Each CSV file is parsed and data is written to the
             corresponding tables: body_composition, blood_glucose,
             measurements (body_temperature, spo2, heart_rate).
@reads       {imports/beurer/}*.csv (Beurer Health Manager Pro Export)
@writes      health.db (body_composition, blood_glucose, measurements)
@limits.de   Keine Validierung der Beurer-Datenqualität. Abhängig von der
             Korrektheit des CSV-Exports. Keine medizinische Interpretation.
             Das FT 95 hat drei Messmodi (Körper 34,0-42,2°C, Objekt/Oberfläche
             0-80°C, Raum), der CSV-Export (Datum;Uhrzeit;°C;Kommentar;
             Medikation) enthält aber KEINE Modus-Spalte — eine Objekt-/
             Raummodus-Messung ist aus den Exportdaten heraus nicht von einer
             Körpertemperaturmessung unterscheidbar. Plausibilitätsprüfung:
             Werte außerhalb des Körpermodus-Bereichs (34,0-42,2°C, s.
             BODY_TEMP_MIN_C/MAX_C) werden verworfen und gezählt ausgegeben —
             das deckt aber keine im Objekt-Modus gemessenen Werte ab, die
             zufällig im plausiblen Körpertemperatur-Bereich liegen (z. B. eine
             warme Flasche bei ~37°C). Das bleibt ein Restrisiko, nur durch
             disziplinierte Nutzung im Alltag zu vermeiden (Objekt-Modus-
             Messungen nicht mit demselben Gerät im selben Zeitraum wie die
             eigene Fiebermessung loggen), nicht durch den Importer selbst.

@relevance.de  Ermöglicht den Import von Gesundheitsdaten, essentiell für die umfassende Datenanalyse
@relevance.en  Enables import of health data, essential for comprehensive data analysis
@limits.en   No validation of Beurer data quality. Dependent on the correctness
             of the CSV export. No medical interpretation.
             The FT 95 has three measurement modes (body 34.0-42.2°C,
             object/surface 0-80°C, room), but the CSV export (Datum;Uhrzeit;
             °C;Kommentar;Medikation) carries NO mode column — an object/room-
             mode reading is indistinguishable from a body-temperature reading
             in the export data. Plausibility check: values outside the body-
             mode range (34.0-42.2°C, see BODY_TEMP_MIN_C/MAX_C) are discarded
             and the count is reported — but this doesn't catch object-mode
             readings that happen to fall in a plausible body-temperature
             range (e.g. a warm bottle at ~37°C). That remains a residual
             risk, avoidable only through disciplined use (don't log object-
             mode readings with the same device in the same period as your
             own fever tracking), not by the importer itself.
@usage
    python3 import_beurer.py                     # all CSVs im Folder
    python3 import_beurer.py --file export.csv
    python3 import_beurer.py --update            # only neue Daten
    python3 import_beurer.py --user Hauptnutzer
"""

import argparse
from datetime import datetime
from pathlib import Path
import sys as _sys
_sys.path.insert(0, str(Path(__file__).parent.parent))
from health_config import Config as _Cfg
from modules.db import open_db
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from modules.base import log_import, resolve_person
from modules.identity_resolver import resolve_device
_cfg = _Cfg()

DEVICE_BF990 = resolve_device("beurer_bf990")
DEVICE_GL60  = resolve_device("beurer_gl60")
DEVICE_FT95  = resolve_device("beurer_ft95")
DEVICE_PO60  = resolve_device("beurer_po60")

DB_PATH = _cfg.db_path
BEURER_DIR = _cfg.beurer_dir
BEURER_DIR.mkdir(parents=True, exist_ok=True)

# Der Beurer-App-Export markiert Zeilen mit dem Vornamen aus dem Geräte-Profil
# (Kommentar-Spalte), nicht mit einem generischen Platzhalter. Ohne diesen
# Abgleich filtert is_user() alle Zeilen fälschlich als "falscher Benutzer"
# heraus (betraf bisher u. a. den gesamten Pulsoxymetrie-Import).
def _default_user() -> str:
    name = (_cfg.name or "").strip()
    return name.split()[0] if name else "Hauptnutzer"


DEFAULT_USER = _default_user()

MG_DL_TO_MMOL = 0.0555179


def parse_date(s: str) -> str:
    try:
        return datetime.strptime(s.strip(), "%d.%m.%Y").strftime("%Y-%m-%d")
    except ValueError:
        return s.strip()


def parse_float(s: str) -> float | None:
    try:
        return float(s.strip().replace(",", ".")) if s.strip() else None
    except ValueError:
        return None


def is_user(comment: str, user: str) -> bool:
    c = comment.strip().lower()
    if not c:
        return True
    return user.lower() in c


def parse_csv(filepath: Path) -> dict:
    text = filepath.read_text(encoding="utf-8-sig", errors="replace")
    sections = {}
    current_section = None
    current_rows = []

    for line in text.splitlines():
        line = line.strip()
        if not line:
            if current_section and current_rows:
                sections[current_section] = current_rows
                current_rows = []
                current_section = None
            continue

        if ";" not in line and len(line) < 50 and not line.startswith("Benutzer"):
            if current_section and current_rows:
                sections[current_section] = current_rows
            current_section = line
            current_rows = []
        else:
            current_rows.append(line)

    if current_section and current_rows:
        sections[current_section] = current_rows

    return sections


def import_weight(conn, rows: list, user: str, update_from: str | None, person: str | None = None) -> int:
    if not rows:
        return 0
    # Spalten nachruesten falls body_composition aus einer aelteren Schema-Version stammt
    for col, typ in [("soft_lean_mass_kg", "REAL"), ("lean_body_mass_kg", "REAL"),
                      ("protein_pct", "REAL"), ("muscle_mass_organ_kg", "REAL")]:
        try:
            conn.execute(f"ALTER TABLE body_composition ADD COLUMN {col} {typ}")
            conn.commit()
        except Exception:
            pass
    person = resolve_person(person)
    imported = 0
    for row in rows[1:]:
        parts = row.split(";")
        if len(parts) < 4:
            continue
        d = parse_date(parts[0])
        t = parts[1].strip() if len(parts) > 1 else "00:00"
        # Spalte 27 (1-indiziert) ist "Kommentar" laut Header (Datum;Uhrzeit;kg;
        # BMI;...;Protein;Muskelmasse inkl. Organmuskeln;Kommentar;Medikation) —
        # parts[23] war "Lean Body Mass" (Spalte 24), eine Zahl statt des
        # Kommentarfelds. is_user() verglich dadurch den Vornamen gegen Werte wie
        # "62.1", was praktisch nie zutraf und fast jede Gewichtszeile mit
        # gefülltem Lean-Body-Mass-Wert stillschweigend überspringen liess.
        comment = parts[26].strip() if len(parts) > 26 else ""

        if not is_user(comment, user):
            continue
        if update_from and d < update_from:
            continue

        dt = f"{d}T{t}:00"
        # range(2,26) statt (2,22): Spalten 23-26 (Soft Lean Mass, Lean Body
        # Mass, Protein, Muskelmasse inkl. Organmuskeln) fehlten bislang komplett,
        # obwohl sie im CSV-Export vorhanden sind (s. Header-Kommentar oben).
        vals = [parse_float(parts[i]) if len(parts) > i else None for i in range(2, 26)]
        # Puls 0.0 = nicht gemessen (Hände nicht an den Griffen)
        if vals[19] is not None and vals[19] <= 0:
            vals[19] = None

        try:
            # ON CONFLICT statt reinem INSERT OR IGNORE: die vier neuen Spalten
            # (soft_lean_mass_kg etc.) wurden erst nachtraeglich ergaenzt — Zeilen,
            # die schon vor dieser Erweiterung importiert wurden, existieren unter
            # demselben (ts, person) bereits und wuerden von INSERT OR IGNORE
            # komplett uebersprungen, die vier Werte blieben dauerhaft NULL.
            # COALESCE(bestehend, neu) traegt sie gezielt nach, ohne andere,
            # bereits korrekte Spalten anzutasten.
            conn.execute("""
                INSERT INTO body_composition
                (ts, date, weight_kg, bmi, body_fat_pct, water_pct, muscle_pct, bone_kg,
                 fat_arm_left, fat_arm_right, fat_leg_left, fat_leg_right, fat_trunk, fat_visceral_pct,
                 muscle_arm_left, muscle_arm_right, muscle_leg_left, muscle_leg_right, muscle_trunk,
                 metabolic_age, visceral_fat, pulse_bpm,
                 soft_lean_mass_kg, lean_body_mass_kg, protein_pct, muscle_mass_organ_kg,
                 comment, device_id, person, source)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(ts, person) DO UPDATE SET
                    soft_lean_mass_kg    = COALESCE(body_composition.soft_lean_mass_kg,    excluded.soft_lean_mass_kg),
                    lean_body_mass_kg    = COALESCE(body_composition.lean_body_mass_kg,    excluded.lean_body_mass_kg),
                    protein_pct          = COALESCE(body_composition.protein_pct,          excluded.protein_pct),
                    muscle_mass_organ_kg = COALESCE(body_composition.muscle_mass_organ_kg, excluded.muscle_mass_organ_kg)
            """, (dt, d, *vals, comment, DEVICE_BF990, person, "beurer_hmp"))
            imported += 1
            # Puls in measurements spiegeln (für HR-Multisource-Analyse)
            if vals[19] is not None:
                conn.execute("""
                    INSERT OR IGNORE INTO measurements
                    (ts, date, metric, value, unit, device_id, person, source_app)
                    VALUES (?,?,?,?,?,?,?,?)
                """, (dt, d, "heart_rate", vals[19], "bpm",
                      DEVICE_BF990, person, "beurer_hmp"))
        except Exception:
            pass
    conn.commit()
    return imported


def import_glucose(conn, rows: list, user: str, update_from: str | None, person: str | None = None) -> int:
    if not rows:
        return 0
    person = resolve_person(person)
    imported = 0
    for row in rows[1:]:
        parts = row.split(";")
        if len(parts) < 3:
            continue
        d = parse_date(parts[0])
        t = parts[1].strip() if len(parts) > 1 else "00:00"
        mg = parse_float(parts[2])
        marker   = parts[4].strip() if len(parts) > 4 else ""
        hba1c    = parse_float(parts[5]) if len(parts) > 5 else None
        comment  = parts[6].strip() if len(parts) > 6 else ""

        if not is_user(comment, user):
            continue
        if update_from and d < update_from:
            continue
        if mg is None:
            continue

        dt   = f"{d}T{t}:00"
        mmol = round(mg * MG_DL_TO_MMOL, 2) if mg else None

        try:
            conn.execute("""
                INSERT OR IGNORE INTO blood_glucose
                (ts, date, glucose_mmol, glucose_mgdl, meal_context, hba1c,
                 comment, device_id, person, source)
                VALUES (?,?,?,?,?,?,?,?,?,?)
            """, (dt, d, mmol, mg, marker or None, hba1c,
                  comment or None, DEVICE_GL60, person, "beurer_hmp"))
            imported += 1
        except Exception:
            pass
    conn.commit()
    return imported


# FT95-Körpermodus-Messbereich lt. Beurer-Handbuch (Stirn, kontaktlos):
# 34.0-42.2°C. Objekt-/Raummodus deckt 0-80°C ab und ist im CSV-Export nicht
# von Körpermodus unterscheidbar (keine Modus-Spalte) — Werte außerhalb des
# Körpermodus-Bereichs sind aber physiologisch sicher keine Körpertemperatur
# und werden verworfen. Werte innerhalb des Bereichs, die trotzdem im
# Objekt-Modus gemessen wurden (z.B. warme Flasche bei 37°C), bleiben ein
# Restrisiko, s. @limits.
BODY_TEMP_MIN_C = 34.0
BODY_TEMP_MAX_C = 42.2


def import_temperature(conn, rows: list, user: str, update_from: str | None, person: str | None = None) -> int:
    if not rows:
        return 0
    person = resolve_person(person)
    imported = 0
    implausible = 0
    for row in rows[1:]:
        parts = row.split(";")
        if len(parts) < 3:
            continue
        d    = parse_date(parts[0])
        t    = parts[1].strip() if len(parts) > 1 else "00:00"
        temp = parse_float(parts[2])
        comment = parts[3].strip() if len(parts) > 3 else ""

        if not is_user(comment, user):
            continue
        if update_from and d < update_from:
            continue
        if temp is None:
            continue
        if temp < BODY_TEMP_MIN_C or temp > BODY_TEMP_MAX_C:
            implausible += 1
            continue

        dt = f"{d}T{t}:00"
        try:
            conn.execute("""
                INSERT OR IGNORE INTO measurements
                (ts, date, metric, value, unit, device_id, person, source_app)
                VALUES (?,?,?,?,?,?,?,?)
            """, (dt, d, "body_temperature", temp, "°C", DEVICE_FT95, person, "beurer_hmp"))
            imported += 1
        except Exception:
            pass
    conn.commit()
    if implausible:
        print(t(f"    ⚠️  {implausible} Temperaturwert(e) außerhalb des FT95-Körpermodus-Bereichs "
                f"({BODY_TEMP_MIN_C}-{BODY_TEMP_MAX_C}°C) übersprungen — vermutlich Objekt-/Raummodus",
                f"    ⚠️  {implausible} temperature value(s) outside the FT95 body-mode range "
                f"({BODY_TEMP_MIN_C}-{BODY_TEMP_MAX_C}°C) skipped — likely object/room mode"))
    return imported


def import_pulse_oximetry(conn, rows: list, user: str, update_from: str | None, person: str | None = None) -> int:
    """PO60 (Health Manager Pro "Pulsoxy"-Export, sitzungsbasiert):
    Datum;Startzeit;Endzeit;Dauer;SpO2 (Min);SpO2 (Max);SpO2 (Durchschnitt);bpm;Kommentar;Medikation

    Frühere Versionen dieses Parsers gingen von einem älteren, minutenweisen
    PO60-Exportformat aus (Datum;Uhrzeit;SpO2;Pulsrate;Kommentar) und lasen
    dadurch bei diesem sitzungsbasierten Format stillschweigend 0 Zeilen ein
    (Spalte 2 = Endzeit statt SpO2, parse_float scheiterte, Zeile übersprungen).

    Speichert pro Sitzung zwei 'spo2'-Punkte (Minimum bei Startzeit — die
    klinisch relevante Desaturation —, Durchschnitt bei Endzeit, damit
    nachgelagerte MIN()/AVG()-Auswertungen beide Kennzahlen sehen) sowie
    die Pulsfrequenz bei Startzeit.
    """
    if not rows:
        return 0
    person = resolve_person(person)
    imported = 0
    for row in rows[1:]:
        parts = row.split(";")
        if len(parts) < 7:
            continue
        d          = parse_date(parts[0])
        start_tm   = parts[1].strip() or "00:00"
        end_tm     = parts[2].strip() or start_tm
        spo2_min   = parse_float(parts[4])
        spo2_avg   = parse_float(parts[6]) if len(parts) > 6 else None
        pulse      = parse_float(parts[7]) if len(parts) > 7 else None
        comment    = parts[8].strip() if len(parts) > 8 else ""

        if not is_user(comment, user):
            continue
        if update_from and d < update_from:
            continue

        ts_start = f"{d}T{start_tm}:00"
        ts_end   = f"{d}T{end_tm}:00"
        try:
            if spo2_min is not None and 50 <= spo2_min <= 100:
                conn.execute("""
                    INSERT OR IGNORE INTO measurements
                    (ts, date, metric, value, unit, device_id, person, source_app)
                    VALUES (?,?,?,?,?,?,?,?)
                """, (ts_start, d, "spo2", spo2_min, "%", DEVICE_PO60, person, "beurer_hmp"))
                imported += 1
            if spo2_avg is not None and 50 <= spo2_avg <= 100 and ts_end != ts_start:
                conn.execute("""
                    INSERT OR IGNORE INTO measurements
                    (ts, date, metric, value, unit, device_id, person, source_app)
                    VALUES (?,?,?,?,?,?,?,?)
                """, (ts_end, d, "spo2", spo2_avg, "%", DEVICE_PO60, person, "beurer_hmp"))
                imported += 1
            if pulse is not None and pulse > 20:
                conn.execute("""
                    INSERT OR IGNORE INTO measurements
                    (ts, date, metric, value, unit, device_id, person, source_app)
                    VALUES (?,?,?,?,?,?,?,?)
                """, (ts_start, d, "heart_rate", pulse, "bpm", DEVICE_PO60, person, "beurer_hmp"))
        except Exception:
            pass
    conn.commit()
    return imported


def get_last_import(conn) -> str | None:
    dates = []
    try:
        r = conn.execute("SELECT MAX(date) FROM body_composition WHERE source='beurer_hmp'").fetchone()
        if r and r[0]: dates.append(r[0])
    except Exception:
        pass
    try:
        r = conn.execute("SELECT MAX(date) FROM blood_glucose WHERE source='beurer_hmp'").fetchone()
        if r and r[0]: dates.append(r[0])
    except Exception:
        pass
    try:
        r = conn.execute(
            "SELECT MAX(date) FROM measurements WHERE metric='body_temperature' AND source_app='beurer_hmp'"
        ).fetchone()
        if r and r[0]: dates.append(r[0])
    except Exception:
        pass
    try:
        r = conn.execute(
            "SELECT MAX(date) FROM measurements WHERE metric='spo2' AND device_id=?", (DEVICE_PO60,)
        ).fetchone()
        if r and r[0]: dates.append(r[0])
    except Exception:
        pass
    return max(dates) if dates else None


def main():
    """
    Hauptfunktion: Koordiniert den Import der Beurer CSV-Daten.

    Command-Line-Argumente:
        --file: Bestimmte CSV-Datei
        --update: Nur neue Daten
        --user: Benutzername filtern
    """
    parser = argparse.ArgumentParser(description=t("Beurer Health Manager Pro → health.db", "Beurer Health Manager Pro → health.db"))
    parser.add_argument("--file",   help="Bestimmte CSV-File")
    parser.add_argument("--update", action="store_true", help=t("Nur neue Daten", "Only new data"))
    parser.add_argument("--user",   default=DEFAULT_USER, help="Benutzername filtern")
    parser.add_argument("--person", default=None,
                        help="Ziel-Person für DB-Zuordnung (Default: OWN_PERSON_ID); "
                             "unabhängig von --user, das nur die CSV-Zeilen filtert")
    add_lang_arg(parser)

    args = parser.parse_args()
    apply_lang_from_args(args)
    person = resolve_person(args.person)

    conn = open_db()
    conn.execute("PRAGMA journal_mode=WAL")

    update_from = None
    if args.update:
        last = get_last_import(conn)
        if last:
            from datetime import timedelta
            d = datetime.strptime(last, "%Y-%m-%d") + timedelta(days=1)
            update_from = d.strftime("%Y-%m-%d")
            print(t(f"Update-Modus: ab {update_from}", f"Update mode: from {update_from}"))

    files = ([Path(args.file)] if args.file
             else sorted(BEURER_DIR.glob("*.csv")) + sorted(BEURER_DIR.glob("*.CSV")))

    if not files:
        print(t(f"Keine CSV-Dateien in {BEURER_DIR}", f"No CSV files in {BEURER_DIR}"))
        return

    total_w = total_g = total_t = total_o = 0

    for f in files:
        print(f"  {f.name} ...", flush=True)
        sections = parse_csv(f)

        for section_name, rows in sections.items():
            sl = section_name.lower()
            if "gewicht" in sl or "weight" in sl:
                n = import_weight(conn, rows, args.user, update_from, person)
                total_w += n
                print(t(f"    Gewicht/Körperzusammensetzung: {n} Einträge",
                        f"    Weight/body composition: {n} entries"))
            elif "pulsox" in sl or "sauerstoff" in sl or "oxygen" in sl or "spo2" in sl:
                n = import_pulse_oximetry(conn, rows, args.user, update_from, person)
                total_o += n
                print(t(f"    Pulsoximetrie (SpO2): {n} Einträge",
                        f"    Pulse oximetry (SpO2): {n} entries"))
            elif "blutzucker" in sl or "glucose" in sl or "blood" in sl:
                n = import_glucose(conn, rows, args.user, update_from, person)
                total_g += n
                print(t(f"    Blutzucker: {n} Einträge",
                        f"    Blood glucose: {n} entries"))
            elif "temperatur" in sl or "temp" in sl:
                n = import_temperature(conn, rows, args.user, update_from, person)
                total_t += n
                print(t(f"    Temperatur: {n} Einträge",
                        f"    Temperature: {n} entries"))

    print(t("\n── Beurer-Daten importiert ──────────────────────────────", "\n── Beurer data imported ──────────────────────────────────"))
    print(t(f"  Gewicht/Körperzusammensetzung: {total_w}", f"  Weight/body composition: {total_w}"))
    print(t(f"  Blutzucker:                    {total_g}", f"  Blood glucose:                 {total_g}"))
    print(t(f"  Temperatur:                    {total_t}", f"  Temperature:                   {total_t}"))
    print(t(f"  Pulsoximetrie (SpO2):          {total_o}", f"  Pulse oximetry (SpO2):         {total_o}"))

    for q, params, lbl in [
        ("SELECT COUNT(*), MIN(date), MAX(date) FROM body_composition WHERE device_id=?", (DEVICE_BF990,), "Weight"),
        ("SELECT COUNT(*), MIN(date), MAX(date) FROM blood_glucose WHERE device_id=?", (DEVICE_GL60,), "Glukose"),
        ("SELECT COUNT(*), MIN(date), MAX(date) FROM measurements WHERE metric='body_temperature' AND source_app LIKE 'beurer%'", (), "Temperatur"),
        ("SELECT COUNT(*), MIN(date), MAX(date) FROM measurements WHERE metric='spo2' AND device_id=?", (DEVICE_PO60,), "SpO2"),
    ]:
        try:
            r = conn.execute(q, params).fetchone()
            print(t(f"  {lbl:<12} gesamt: {r[0]:>4} | {r[1]}–{r[2]}",
                    f"  {lbl:<12} total:  {r[0]:>4} | {r[1]}–{r[2]}"))
        except Exception:
            pass

    log_import(conn, 'beurer', str(BEURER_DIR), total_w + total_g + total_t, person=person)
    conn.commit()
    conn.close()


if __name__ == "__main__":
    main()
