#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later

"""
Wellue O2Ring S (ViHealth-App-Export) → health.db

@tier        infrastructure
@purpose.de  Importiert sekundengenaue SpO2/Puls-Rohdaten des Wellue O2Ring S
             (ViHealth-App CSV-Export) in health.db. Speichert volle Auflösung
             in o2ring_raw und spiegelt Minuten-Mittelwerte nach measurements
             (Metriken spo2, heart_rate) für die geräteübergreifende
             Kalibrierungs-Pipeline (compute_calibrate_sources.py).
@purpose.en  Imports second-resolution SpO2/pulse raw data from the Wellue
             O2Ring S (ViHealth app CSV export) into health.db. Stores full
             resolution in o2ring_raw and mirrors per-minute averages into
             measurements (metrics spo2, heart_rate) for the cross-device
             calibration pipeline (compute_calibrate_sources.py).
@method.de   Liest CSV mit deutscher Kopfzeile, englischem Datumsformat
             (%H:%M:%S %b %d %Y) je Zeile. '--' markiert fehlende SpO2/Puls-
             Werte (Kontaktverlust) und wird als NULL gespeichert, Bewegung/
             Alarmflags bleiben erhalten. Lokale Zeit wird via
             ZoneInfo(_cfg.home_timezone) nach UTC konvertiert. Die ersten
             WARMUP_SECONDS (Default 15s) jeder Datei ab dem ersten Zeitstempel
             werden als warmup_flag=1 markiert (rein deskriptiv — eigene
             Testnächte zeigten kein einheitliches Artefaktmuster, daher
             KEIN Ausschluss aus der Aggregation). Minuten-Aggregation nach
             measurements erfolgt in-memory beim Parsen (Bucket-Key ts[:16])
             über alle validen Werte unabhängig von warmup_flag.
@method.en   Reads CSV with German header, English date format per row
             (%H:%M:%S %b %d %Y). '--' marks missing SpO2/pulse values
             (contact loss) and is stored as NULL; movement/alarm flags are
             kept. Local time is converted to UTC via
             ZoneInfo(_cfg.home_timezone). The first WARMUP_SECONDS (default
             15s) of each file from its first timestamp are marked
             warmup_flag=1 (descriptive only — own test nights showed no
             consistent artifact pattern, so it does NOT exclude rows from
             aggregation). Per-minute aggregation into measurements happens
             in-memory while parsing (bucket key ts[:16]) over all valid
             values regardless of warmup_flag.
@reads       o2ring_raw (MAX(ts) für --update-Modus)
@writes      o2ring_raw: ts TEXT, date TEXT, spo2 INTEGER, pulse INTEGER,
             movement INTEGER, o2_alarm INTEGER, pr_alarm INTEGER,
             warmup_flag INTEGER, device_id TEXT, person TEXT, source TEXT;
             measurements: ts TEXT, date TEXT, metric TEXT, value REAL,
             unit TEXT, device_id TEXT, person TEXT, source_app TEXT
@limits.de   Kein Sitzungs-/Geräte-Identifier im CSV selbst. Bewegungsskala
             nicht herstellerdokumentiert (roh gespeichert). warmup_flag ist
             rein informativ (kein verlässlicher Artefaktfilter gefunden, s.
             Plan Abschnitt 3) — SpO2/Puls-Sprünge in den ersten Sekunden
             (Anlege-Artefakt oder echtes Ereignis, z. B. Lagewechsel) landen
             ungefiltert in measurements. Minuten mit ausschließlich '--'
             tragen keinen measurements-Eintrag bei. Keine medizinische
             Interpretation.

@relevance.de  Ermöglicht den Import von Gesundheitsdaten, essentiell für die umfassende Datenanalyse
@relevance.en  Enables import of health data, essential for comprehensive data analysis
@limits.en   No session/device identifier in the CSV itself. Movement scale
             is not documented by the manufacturer (stored raw). warmup_flag
             is informational only (no reliable artifact filter found, see
             plan section 3) — SpO2/pulse jumps in the first seconds (device
             settling or a real event, e.g. postural change) enter
             measurements unfiltered. Minutes with only '--' values
             contribute no measurements entry. No medical interpretation.
@usage
    python3 import_wellue_o2ring.py
    python3 import_wellue_o2ring.py --update
    python3 import_wellue_o2ring.py --file imports/_inbox/O2Ring_S_20260715005402.csv
    python3 import_wellue_o2ring.py --inbox
"""

import sys
from datetime import datetime, timezone
from pathlib import Path
import csv
import argparse
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).parent.parent))
from health_config import Config as _Cfg, OWN_PERSON_ID
from modules.db import open_db
from modules.base import log_import
from modules.identity_resolver import resolve_device

DEVICE_O2RING = resolve_device("wellue_o2ring_s")
from modules.i18n import t, add_lang_arg, apply_lang_from_args

# Konstante für Warmup-Flag (rein deskriptiv, kein Filter - siehe Plan Abschnitt 3)
WARMUP_SECONDS = 15  # erste 15s jeder Datei werden als warmup_flag=1 markiert

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS o2ring_raw (
    ts           TEXT NOT NULL,
    date         TEXT NOT NULL,
    spo2         INTEGER,
    pulse        INTEGER,
    movement     INTEGER,
    o2_alarm     INTEGER NOT NULL DEFAULT 0,
    pr_alarm     INTEGER NOT NULL DEFAULT 0,
    warmup_flag  INTEGER NOT NULL DEFAULT 0,
    device_id    TEXT NOT NULL DEFAULT 'wellue_o2ring_s',
    person       TEXT NOT NULL DEFAULT 'unknown',
    source       TEXT NOT NULL DEFAULT 'wellue_o2ring',
    PRIMARY KEY (ts, person)
);
CREATE INDEX IF NOT EXISTS idx_o2ring_date   ON o2ring_raw(date);
CREATE INDEX IF NOT EXISTS idx_o2ring_person ON o2ring_raw(person, date);
"""


def parse_wellue_o2ring(path: Path) -> list[dict]:
    """
    Parsed eine Wellue O2Ring CSV-Datei und gibt alle Rohzeilen zurück.
    
    Args:
        path: Pfad zur CSV-Datei
    
    Returns:
        Liste von Dicts mit Schlüsseln: ts, date, spo2, pulse, movement, o2_alarm, pr_alarm, warmup_flag
    """
    _cfg = _Cfg()
    
    with open(path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        header = next(reader)  # deutsche Kopfzeile überspringen
        
        rows = []
        first_ts = None
        
        for line in reader:
            if len(line) < 6:
                continue  # unvollständige Zeile überspringen
            
            # Zeitstring parsen (englische Monatsnamen trotz deutscher Kopfzeile)
            time_str = line[0].strip()
            try:
                naive_dt = datetime.strptime(time_str, "%H:%M:%S %b %d %Y")
            except ValueError as e:
                print(f"Warnung: Ungültiges Datumsformat in Zeile: {line[0]} - {e}")
                continue
            
            # Lokale Zeit nach UTC konvertieren
            local_tz = ZoneInfo(_cfg.home_timezone)
            # ZoneInfo objects are already timezone-aware, so we replace the timezone
            local_dt = naive_dt.replace(tzinfo=local_tz)
            utc_dt = local_dt.astimezone(timezone.utc)
            ts = utc_dt.isoformat()
            date = local_dt.strftime("%Y-%m-%d")
            
            # Erster Timestamp für Warmup-Flag Referenz
            if first_ts is None:
                first_ts = utc_dt
            
            # SpO2 und Puls parsen ('--' = fehlender Wert)
            spo2_val = int(line[1].strip()) if line[1].strip() != "--" else None
            pulse_val = int(line[2].strip()) if line[2].strip() != "--" else None
            
            # Bewegung und Alarmflags (immer numerisch)
            movement = int(line[3].strip())
            o2_alarm = int(line[4].strip())
            pr_alarm = int(line[5].strip())
            
            # Warmup-Flag berechnen (rein deskriptiv, kein Filter)
            warmup_flag = 1 if (utc_dt - first_ts).total_seconds() < WARMUP_SECONDS else 0
            
            rows.append({
                'ts': ts,
                'date': date,
                'spo2': spo2_val,
                'pulse': pulse_val,
                'movement': movement,
                'o2_alarm': o2_alarm,
                'pr_alarm': pr_alarm,
                'warmup_flag': warmup_flag
            })
    
    return rows


def aggregate_minute_averages(rows: list[dict]) -> dict:
    """
    Aggregiert SpO2 und Puls auf Minutenebene für measurements.

    Args:
        rows: Liste von Rohzeilen-Dicts

    Returns:
        Dict mit Minute (UTC-Key, ts[:16]) und je einem Dict mit 'spo2'-/'pulse'-
        Listen sowie 'date' (lokales Kalenderdatum der Zeilen dieser Minute —
        NICHT aus dem UTC-Key ableiten: bei Zeitzonen-Versatz kann das lokale
        Datum vom UTC-Datum abweichen, z. B. kurz nach Mitternacht lokal).
    """
    buckets = {}

    for row in rows:
        if row['spo2'] is not None or row['pulse'] is not None:
            minute_key = row['ts'][:16]  # YYYY-MM-DDTHH:MM (UTC)

            if minute_key not in buckets:
                buckets[minute_key] = {'spo2': [], 'pulse': [], 'date': row['date']}

            if row['spo2'] is not None:
                buckets[minute_key]['spo2'].append(row['spo2'])
            if row['pulse'] is not None:
                buckets[minute_key]['pulse'].append(row['pulse'])

    return buckets


def import_file(conn, path: Path, update_from: datetime = None) -> int:
    """
    Importiert eine Wellue O2Ring CSV-Datei in die Datenbank.
    
    Args:
        conn: Datenbankverbindung
        path: Pfad zur CSV-Datei
        update_from: Optional - nur Zeilen nach diesem Timestamp importieren
    
    Returns:
        Anzahl der importierten Zeilen
    """
    rows = parse_wellue_o2ring(path)
    if not rows:
        return 0
    
    # Filter für Update-Modus
    if update_from:
        rows = [r for r in rows if r['ts'] > update_from.isoformat()]
        if not rows:
            return 0
    
    # Rohdaten in o2ring_raw schreiben
    cursor = conn.cursor()
    inserted_count = 0
    
    for row in rows:
        try:
            cursor.execute("""
                INSERT OR IGNORE INTO o2ring_raw
                (ts, date, spo2, pulse, movement, o2_alarm, pr_alarm, warmup_flag, device_id, person)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                row['ts'],
                row['date'],
                row['spo2'],
                row['pulse'],
                row['movement'],
                row['o2_alarm'],
                row['pr_alarm'],
                row['warmup_flag'],
                DEVICE_O2RING,
                OWN_PERSON_ID
            ))
            inserted_count += cursor.rowcount
        except Exception as e:
            print(f"Fehler beim Einfügen in o2ring_raw: {e}")
    
    # Minuten-Aggregation für measurements
    buckets = aggregate_minute_averages(rows)
    measurements_count = 0

    for minute_key, values in buckets.items():
        # Lokales Kalenderdatum kommt aus dem Bucket selbst (siehe
        # aggregate_minute_averages) — NICHT von der zuletzt verarbeiteten
        # Rohzeile übernehmen (sonst bekämen alle Minuten vor Mitternacht
        # fälschlich das Datum der letzten Zeile der Datei) und NICHT aus dem
        # UTC-basierten minute_key ableiten (Zeitzonen-Versatz kann lokales
        # und UTC-Datum auseinanderfallen lassen, z. B. kurz nach Mitternacht
        # lokal aber noch am Vortag in UTC).
        bucket_date = values['date']

        # SpO2 Mittelwert
        if values['spo2']:
            spo2_avg = sum(values['spo2']) / len(values['spo2'])
            # Plausibilitätsfilter
            if 50 <= spo2_avg <= 100:
                cursor.execute("""
                    INSERT OR IGNORE INTO measurements
                    (ts, date, metric, value, unit, device_id, person, source_app)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    f"{minute_key}:00",  # Sekunden auf 00 setzen
                    bucket_date,
                    'spo2',
                    spo2_avg,
                    '%',
                    DEVICE_O2RING,
                    OWN_PERSON_ID,
                    'wellue_o2ring'
                ))
                measurements_count += 1

        # Puls Mittelwert
        if values['pulse']:
            pulse_avg = sum(values['pulse']) / len(values['pulse'])
            # Plausibilitätsfilter
            if pulse_avg > 20:
                cursor.execute("""
                    INSERT OR IGNORE INTO measurements
                    (ts, date, metric, value, unit, device_id, person, source_app)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    f"{minute_key}:00",  # Sekunden auf 00 setzen
                    bucket_date,
                    'heart_rate',
                    pulse_avg,
                    'bpm',
                    DEVICE_O2RING,
                    OWN_PERSON_ID,
                    'wellue_o2ring'
                ))
                measurements_count += 1
    
    conn.commit()
    return inserted_count


def move_to_processed(path: Path, suffix: str = None) -> None:
    """Verschiebt eine Datei nach erfolgreichem Import in das processed-Verzeichnis."""
    _cfg = _Cfg()
    processed_dir = _cfg.data_root / "_inbox" / "processed"
    processed_dir.mkdir(parents=True, exist_ok=True)
    
    if suffix:
        target = processed_dir / f"{path.stem}_{suffix}{path.suffix}"
    else:
        target = processed_dir / f"{path.stem}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{path.suffix}"
    
    path.rename(target)


def get_update_from(conn) -> datetime:
    """Ermittelt den letzten Timestamp aus o2ring_raw für --update-Modus."""
    cursor = conn.cursor()
    cursor.execute("SELECT MAX(ts) FROM o2ring_raw WHERE person=?", (OWN_PERSON_ID,))
    result = cursor.fetchone()
    if result and result[0]:
        return datetime.fromisoformat(result[0].replace('Z', '+00:00'))
    return None


def main():
    parser = argparse.ArgumentParser(description=t("Import Wellue O2Ring S data", "Import Wellue O2Ring S data"))
    parser.add_argument('--file', type=Path, help=t("Single CSV file to import", "Single CSV file to import"))
    parser.add_argument('--inbox', action='store_true', help=t("Process all O2Ring*.csv files in _inbox", "Process all O2Ring*.csv files in _inbox"))
    parser.add_argument('--update', action='store_true', help=t("Only import rows newer than last ts in o2ring_raw", "Only import rows newer than last ts in o2ring_raw"))
    add_lang_arg(parser)
    args = parser.parse_args()
    apply_lang_from_args(args)
    
    _cfg = _Cfg()
    INBOX_DIR = _cfg.data_root / "_inbox"
    
    conn = open_db()
    conn.executescript(_SCHEMA_SQL)
    
    total_imported = 0
    files_processed = []
    
    # Update-Modus: letzten Timestamp ermitteln
    update_from = get_update_from(conn) if args.update else None
    
    if args.file:
        files_processed.append(args.file)
    elif args.inbox:
        files_processed = list(INBOX_DIR.glob("O2Ring*.csv"))
    else:
        # Standard: alle CSV-Dateien im konfigurierten Inbox-Ordner
        files_processed = list(INBOX_DIR.glob("*.csv"))
    
    for path in files_processed:
        if not path.name.startswith('O2Ring') and not args.file:
            continue
        
        print(f"Verarbeite {path}...")
        count = import_file(conn, path, update_from)
        if count > 0:
            log_import(conn, 'wellue_o2ring', str(path), count)
            conn.commit()
            total_imported += count
            
            # Bei --inbox: nach processed verschieben
            if args.inbox:
                move_to_processed(path, suffix=datetime.now().strftime("%Y%m%d_%H%M%S"))
        else:
            print(f"Keine neuen Daten in {path}")
    
    conn.close()
    print(f"Import abgeschlossen. {total_imported} Zeilen importiert.")


if __name__ == '__main__':
    main()