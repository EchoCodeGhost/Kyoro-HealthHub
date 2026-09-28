#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Withings Health Mate GDPR-Export → health.db

@tier        infrastructure
@purpose.de  Importiert Blutdruck, Gewicht/Körperkomposition, Größe, manuell
             erfasstes SpO2, ECG-Wellenformen samt AFib-/Herzklappen-
             Intervall-Zusatzbefunden und Menstruations-/Ovulationsdaten aus
             dem Withings-Health-Mate-Datenexport (GDPR-Anfrage, ZIP mit
             vielen Einzel-CSVs) in health.db. Deckt nur Daten ab, die vom
             BPM Core, einer Withings-Waage oder manueller App-Eingabe
             stammen können — sleep.csv, activities.csv und alle raw_*
             Sensor-Zeitreihen sind bewusst ausgeschlossen (vermutlich
             Apple-Watch-Daten, siehe import_apple.py).
@purpose.en  Imports blood pressure, weight/body composition, height,
             manually logged SpO2, ECG waveforms with AFib/valvular/interval
             findings, and menstrual/ovulation data from the Withings Health
             Mate data export (GDPR request, ZIP with many individual CSVs)
             into health.db. Only covers data that can plausibly originate
             from the BPM Core, a Withings scale, or manual app entry —
             sleep.csv, activities.csv, and all raw_* sensor time series are
             deliberately excluded (likely Apple Watch data via the Apple
             Health pairing, see import_apple.py).
@method.de   Liest die benötigten CSV-Member direkt aus der ZIP (kein
             Entpacken auf Platte, vermeidet PII-Zusatzkopie). Blutdruck geht
             nach blood_pressure, Gewicht/Größe/SpO2 als EAV-Zeilen nach
             measurements, ECG-Wellenformen (signal.csv) nach ecg_sessions +
             ecg_samples, AFib-/Herzklappen-/Intervall-Zusatzbefunde sowie
             Menstruations-/Ovulationsdaten (beide aus other.csv) als
             EAV-Zeilen nach measurements — jeweils mit denselben
             Metric-Namen wie import_polar.py, damit quellenübergreifende
             Auswertungen funktionieren. Drei Geräte-Slugs trennen die
             physische Herkunft (BPM-Core/Waage/ungeklärt, siehe @writes und
             Plan Abschnitt 1). account.csv/user.csv/devices.csv
             (Klartext-PII: Name, E-Mail, MAC-Adresse, Standort des
             Gerätepairings) werden nicht gelesen.
@method.en   Reads the needed CSV members directly from the ZIP (no on-disk
             extraction, avoids an extra PII copy). Blood pressure goes to
             blood_pressure, weight/height/SpO2 as EAV rows to measurements,
             ECG waveforms (signal.csv) to ecg_sessions + ecg_samples,
             AFib/valvular/interval findings plus menstrual/ovulation data
             (both from other.csv) as EAV rows to measurements — using the
             same metric names as import_polar.py so cross-source analysis
             works. Three device slugs separate physical origin (BPM
             Core/scale/unclear, see @writes and plan section 1).
             account.csv/user.csv/devices.csv (plain-text PII: name, email,
             MAC address, device pairing location) are not read.
@reads       keine (schreibt in bereits bestehende Tabellen)
@writes      blood_pressure: ts TEXT, date TEXT, systolic INTEGER, diastolic INTEGER, pulse INTEGER, notes TEXT, person TEXT, source TEXT
@writes      measurements: ts TEXT, date TEXT, metric TEXT, value REAL, unit TEXT, device_id TEXT, person TEXT, source_app TEXT
@writes      ecg_sessions: datetime TEXT, classification TEXT, symptoms TEXT, sample_rate_hz INTEGER, lead TEXT, duration_s REAL, device_id TEXT, person TEXT, source TEXT
@writes      ecg_samples: session_dt TEXT, session_person TEXT, sample_index INTEGER, uv REAL
@writes      blood_glucose: ts TEXT, date TEXT, glucose_mgdl REAL, device_id TEXT, person TEXT, source TEXT
@limits.de   Importiert bewusst nicht: sleep.csv, activities.csv und alle 44
             raw_*-Sensor-Zeitreihen (vermutlich Apple-Watch-Daten, gehören
             zu import_apple.py mit einem frischen Apple-Health-Export, siehe
             Plan Abschnitt 1) sowie die tagesweisen aggregates_*.csv-Rollups
             derselben Quelle. AFib-/Herzklappen-/Intervall-Codes aus
             other.csv sind Withings' eigene Rohcodes ohne medizinische
             Interpretation im Importer, nur lose über gleichen Timestamp mit
             ecg_sessions korreliert (keine FK). Provenienz der einen
             Blutzucker-Zeile ist unklar (kein bekanntes Withings-CGM-Gerät).
@limits.en   Deliberately does not import: sleep.csv, activities.csv, and all
             44 raw_* sensor time series (likely Apple Watch data, belongs to
             import_apple.py with a fresh Apple Health export, see plan
             section 1) nor the daily aggregates_*.csv rollups of the same
             source. AFib/valvular/interval codes from other.csv are
             Withings' own raw codes without medical interpretation in the
             importer, only loosely correlated to ecg_sessions via matching
             timestamp (no FK). Provenance of the single blood glucose row is
             unclear (no known Withings CGM device).

@relevance.de  Schließt die bekannte Lücke beim Withings-Blutdruck-Import und ergänzt Gewichts-, ECG- und Zyklusdaten aus einer bislang ungenutzten Quelle
@relevance.en  Closes the known gap in Withings blood pressure import and adds weight, ECG, and cycle data from a previously unused source
@usage
    python3 import_withings.py
    python3 import_withings.py --file imports/withings/data_SAN_1788375097.zip
    python3 import_withings.py --update
    python3 import_withings.py --inbox
"""

import argparse
import csv
import io
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

# Erhöhe CSV-Feldlimit für große Withings ECG-Signal-Daten
csv.field_size_limit(1024 * 1024)  # 1MB Feldlimit

sys.path.insert(0, str(Path(__file__).parent.parent))
from health_config import Config as _Cfg, OWN_PERSON_ID
from modules.db import open_db
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from modules.base import log_import
from modules.identity_resolver import resolve_device

_cfg = _Cfg()
SOURCE = "withings"

# Geräte-Slugs für verschiedene Withings-Datenquellen
DEVICE_BPM = resolve_device("withings_bpm")        # BPM Core: Blutdruck, ECG, Zusatzbefunde
DEVICE_SCALE = resolve_device("withings_scale")    # Waage: Gewicht, Größe
DEVICE_GLUCOSE = resolve_device("withings_glucose_sync")  # Blutzucker (Provenienz unklar)

# Relevante Typen in other.csv für den Import
OTHER_TYPES_IMPORT = {
    "Atrial fibrillation result",
    "Valvular heart disease result", 
    "QRS interval duration",
    "PR interval duration",
    "QT interval duration",
    "Corrected QT interval duration",
    "Menstruation flow",
    "OVULATION_TEST_RESULTS"
}

# Mapping von other.csv-Typen zu Metric-Namen
OTHER_TYPE_TO_METRIC = {
    "Atrial fibrillation result": "ecg_afib_result",
    "Valvular heart disease result": "ecg_valvular_result",
    "QRS interval duration": "ecg_qrs_duration_ms",
    "PR interval duration": "ecg_pr_duration_ms",
    "QT interval duration": "ecg_qt_duration_ms",
    "Corrected QT interval duration": "ecg_qtc_duration_ms",
    "Menstruation flow": "menstrual_flow",
    "OVULATION_TEST_RESULTS": "ovulation_test_result"
}


def parse_withings_zip(zip_path: Path) -> dict:
    """Liest benötigte CSV-Member direkt aus der ZIP und gibt strukturierte Daten zurück.
    
    Returns:
        dict mit Keys: 'blood_pressure', 'measurements', 'ecg_sessions', 
                      'ecg_samples', 'blood_glucose'
    """
    result = {
        'blood_pressure': [],
        'measurements': [],
        'ecg_sessions': [],
        'ecg_samples': [],
        'blood_glucose': []
    }
    
    try:
        with zipfile.ZipFile(zip_path, 'r') as zf:
            # bp.csv - Blutdruckmessungen
            if 'bp.csv' in zf.namelist():
                _parse_bp_csv(zf, result)
            
            # weight.csv - Gewicht und Körperkomposition
            if 'weight.csv' in zf.namelist():
                _parse_weight_csv(zf, result)
            
            # height.csv - Körpergröße
            if 'height.csv' in zf.namelist():
                _parse_height_csv(zf, result)
            
            # manual_spo2.csv - Manuell erfasstes SpO2
            if 'manual_spo2.csv' in zf.namelist():
                _parse_manual_spo2_csv(zf, result)
            
            # signal.csv - ECG-Wellenformen
            if 'signal.csv' in zf.namelist():
                _parse_signal_csv(zf, result)
            
            # other.csv - Zusatzbefunde und Zyklusdaten
            if 'other.csv' in zf.namelist():
                _parse_other_csv(zf, result)
            
            # raw_blood_glucose_Blood Glucose.csv - Blutzucker
            if 'raw_blood_glucose_Blood Glucose.csv' in zf.namelist():
                _parse_blood_glucose_csv(zf, result)
    
    except zipfile.BadZipFile as e:
        # Datei ist kein gültiges ZIP - Fehlermeldung ausgeben
        print(t(f"Fehler: ZIP-Datei ungültig oder beschädigt: {e}",
                f"Error: Invalid or corrupted ZIP file: {e}"))
        return result
    
    return result


def _parse_bp_csv(zf, result):
    """Parsed bp.csv → blood_pressure Tabelle"""
    with io.TextIOWrapper(zf.open('bp.csv'), encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Datum parsen (naive lokale Zeit)
            date_str = row['Date'].strip()
            try:
                naive_dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
                localized_dt = naive_dt.replace(tzinfo=ZoneInfo(_cfg.home_timezone))
                utc_dt = localized_dt.astimezone(timezone.utc)
                ts = utc_dt.strftime("%Y-%m-%dT%H:%M:%S+00:00")
                date = utc_dt.strftime("%Y-%m-%d")
            except ValueError:
                continue
            
            systolic = _parse_int(row.get('Systole', ''))
            diastolic = _parse_int(row.get('Diastole', ''))
            
            if systolic is None or diastolic is None:
                continue
            
            pulse = _parse_int(row.get('Herzfrequenz', ''))
            notes = row.get('Kommentare', '').strip() or None
            
            result['blood_pressure'].append({
                'ts': ts,
                'date': date,
                'systolic': systolic,
                'diastolic': diastolic,
                'pulse': pulse,
                'notes': notes,
                'person': OWN_PERSON_ID,
                'source': SOURCE,
                'device_id': DEVICE_BPM
            })


def _parse_weight_csv(zf, result):
    """Parsed weight.csv → measurements Tabelle (EAV)"""
    with io.TextIOWrapper(zf.open('weight.csv'), encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            date_str = row['Date'].strip()
            try:
                naive_dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
                localized_dt = naive_dt.replace(tzinfo=ZoneInfo(_cfg.home_timezone))
                utc_dt = localized_dt.astimezone(timezone.utc)
                ts = utc_dt.strftime("%Y-%m-%dT%H:%M:%S+00:00")
                date = utc_dt.strftime("%Y-%m-%d")
            except ValueError:
                continue
            
            device_id = DEVICE_SCALE
            
            # Gewicht (kg)
            weight_kg = _parse_float(row.get('Gewicht (kg)', ''))
            if weight_kg is not None:
                result['measurements'].append({
                    'ts': ts, 'date': date, 'metric': 'weight_kg', 
                    'value': weight_kg, 'unit': 'kg', 
                    'device_id': device_id, 'person': OWN_PERSON_ID, 
                    'source_app': SOURCE
                })
            
            # Fettmasse (kg)
            fat_mass = _parse_float(row.get('Fettmasse (kg)', ''))
            if fat_mass is not None:
                result['measurements'].append({
                    'ts': ts, 'date': date, 'metric': 'body_fat_kg', 
                    'value': fat_mass, 'unit': 'kg', 
                    'device_id': device_id, 'person': OWN_PERSON_ID, 
                    'source_app': SOURCE
                })
            
            # Knochenmasse (kg)
            bone_mass = _parse_float(row.get('Knochenmasse (kg)', ''))
            if bone_mass is not None:
                result['measurements'].append({
                    'ts': ts, 'date': date, 'metric': 'bone_mass_kg', 
                    'value': bone_mass, 'unit': 'kg', 
                    'device_id': device_id, 'person': OWN_PERSON_ID, 
                    'source_app': SOURCE
                })
            
            # Muskelmasse (kg)
            muscle_mass = _parse_float(row.get('Muskelmasse (kg)', ''))
            if muscle_mass is not None:
                result['measurements'].append({
                    'ts': ts, 'date': date, 'metric': 'muscle_mass_kg', 
                    'value': muscle_mass, 'unit': 'kg', 
                    'device_id': device_id, 'person': OWN_PERSON_ID, 
                    'source_app': SOURCE
                })
            
            # Wasseranteil (kg)
            water_mass = _parse_float(row.get('Wasseranteil (kg)', ''))
            if water_mass is not None:
                result['measurements'].append({
                    'ts': ts, 'date': date, 'metric': 'water_mass_kg', 
                    'value': water_mass, 'unit': 'kg', 
                    'device_id': device_id, 'person': OWN_PERSON_ID, 
                    'source_app': SOURCE
                })


def _parse_height_csv(zf, result):
    """Parsed height.csv → measurements Tabelle (EAV)"""
    with io.TextIOWrapper(zf.open('height.csv'), encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            date_str = row['Datum'].strip()
            try:
                naive_dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
                localized_dt = naive_dt.replace(tzinfo=ZoneInfo(_cfg.home_timezone))
                utc_dt = localized_dt.astimezone(timezone.utc)
                ts = utc_dt.strftime("%Y-%m-%dT%H:%M:%S+00:00")
                date = utc_dt.strftime("%Y-%m-%d")
            except ValueError:
                continue
            
            # Größe von Metern zu cm konvertieren
            height_m = _parse_float(row.get('Grösse (m)', ''))
            if height_m is not None:
                height_cm = height_m * 100
                result['measurements'].append({
                    'ts': ts, 'date': date, 'metric': 'height_cm', 
                    'value': height_cm, 'unit': 'cm', 
                    'device_id': DEVICE_SCALE, 'person': OWN_PERSON_ID, 
                    'source_app': SOURCE
                })


def _parse_manual_spo2_csv(zf, result):
    """Parsed manual_spo2.csv → measurements Tabelle (EAV)"""
    with io.TextIOWrapper(zf.open('manual_spo2.csv'), encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            date_str = row['date'].strip()
            try:
                naive_dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
                localized_dt = naive_dt.replace(tzinfo=ZoneInfo(_cfg.home_timezone))
                utc_dt = localized_dt.astimezone(timezone.utc)
                ts = utc_dt.strftime("%Y-%m-%dT%H:%M:%S+00:00")
                date = utc_dt.strftime("%Y-%m-%d")
            except ValueError:
                continue
            
            spo2 = _parse_int(row.get('value', ''))
            if spo2 is not None:
                result['measurements'].append({
                    'ts': ts, 'date': date, 'metric': 'spo2', 
                    'value': spo2, 'unit': '%', 
                    'device_id': '',  # manuell in App erfasst - leerer String statt NULL für Deduplikation
                    'person': OWN_PERSON_ID, 
                    'source_app': SOURCE
                })


def _parse_signal_csv(zf, result):
    """Parsed signal.csv → ecg_sessions + ecg_samples Tabellen"""
    with io.TextIOWrapper(zf.open('signal.csv'), encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Datum parsen (ISO-8601 mit Offset)
            date_str = row['date'].strip()
            try:
                dt = datetime.fromisoformat(date_str)
                if dt.tzinfo is None:
                    # Fallback für naive Datumsangaben
                    dt = dt.replace(tzinfo=ZoneInfo(_cfg.home_timezone))
                    dt = dt.astimezone(timezone.utc)
                else:
                    dt = dt.astimezone(timezone.utc)
                ts = dt.strftime("%Y-%m-%dT%H:%M:%S+00:00")
            except ValueError:
                continue
            
            frequency = _parse_int(row.get('frequency', ''))
            duration = _parse_float(row.get('duration', ''))
            wearposition = row.get('wearposition', '').strip()
            signal_str = row.get('signal', '').strip()
            doctor_assessment = row.get('doctor_assessment', '').strip() or None
            doctor_name = row.get('doctor_name', '').strip() or None
            checkup_date = row.get('checkup_date', '').strip() or None
            
            if not signal_str:
                continue
            
            # ECG-Session erstellen
            classification = doctor_assessment
            symptoms = None
            if doctor_name or checkup_date:
                parts = []
                if doctor_name:
                    parts.append(f"Befundet von {doctor_name}")
                if checkup_date:
                    parts.append(f"am {checkup_date}")
                symptoms = ", ".join(parts)
            
            result['ecg_sessions'].append({
                'datetime': ts,
                'classification': classification,
                'symptoms': symptoms,
                'sample_rate_hz': frequency,
                'lead': 'lead_1',  # Withings BPM Core ist Einzelkanal-ECG
                'duration_s': duration,
                'device_id': DEVICE_BPM,
                'person': OWN_PERSON_ID,
                'source': SOURCE
            })
            
            # Samples parsen
            try:
                samples = [int(x) for x in signal_str.split(',') if x.strip()]
                session_index = len(result['ecg_sessions']) - 1
                for i, uv in enumerate(samples):
                    result['ecg_samples'].append({
                        'session_dt': ts,
                        'session_person': OWN_PERSON_ID,
                        'sample_index': i,
                        'uv': uv
                    })
            except ValueError:
                continue


def _parse_other_csv(zf, result):
    """Parsed other.csv → measurements Tabelle (EAV) für relevante Typen"""
    with io.TextIOWrapper(zf.open('other.csv'), encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            type_name = row.get('type', '').strip()
            if type_name not in OTHER_TYPES_IMPORT:
                continue
            
            date_str = row['date'].strip()
            try:
                naive_dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
                localized_dt = naive_dt.replace(tzinfo=ZoneInfo(_cfg.home_timezone))
                utc_dt = localized_dt.astimezone(timezone.utc)
                ts = utc_dt.strftime("%Y-%m-%dT%H:%M:%S+00:00")
                date = utc_dt.strftime("%Y-%m-%d")
            except ValueError:
                continue
            
            value_str = row.get('value', '').strip()
            if not value_str:
                continue
            
            metric = OTHER_TYPE_TO_METRIC.get(type_name)
            if not metric:
                continue
            
            # Für Menstruations- und Ovulationsdaten: device_id = '' (leerer String statt NULL für Deduplikation)
            # Für ECG-Zusatzbefunde: device_id = DEVICE_BPM
            if type_name in ("Menstruation flow", "OVULATION_TEST_RESULTS"):
                device_id = ''
            else:
                device_id = DEVICE_BPM
            
            try:
                value = float(value_str)
            except ValueError:
                continue
            
            result['measurements'].append({
                'ts': ts, 'date': date, 'metric': metric, 
                'value': value, 'unit': None, 
                'device_id': device_id, 'person': OWN_PERSON_ID, 
                'source_app': SOURCE
            })


def _parse_blood_glucose_csv(zf, result):
    """Parsed raw_blood_glucose_Blood Glucose.csv → blood_glucose Tabelle"""
    with io.TextIOWrapper(zf.open('raw_blood_glucose_Blood Glucose.csv'), encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            date_str = row['start'].strip()
            try:
                dt = datetime.fromisoformat(date_str)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=ZoneInfo(_cfg.home_timezone))
                    dt = dt.astimezone(timezone.utc)
                else:
                    dt = dt.astimezone(timezone.utc)
                ts = dt.strftime("%Y-%m-%dT%H:%M:%S+00:00")
                date = dt.strftime("%Y-%m-%d")
            except ValueError:
                continue
            
            value_str = row.get('value', '').strip()
            if not value_str:
                continue
            
            try:
                # Withings liefert Werte als Bracket-String wie "[110]" - Klammern entfernen
                value_str = value_str.strip('[]')
                glucose_mgdl = float(value_str)
            except (ValueError, IndexError):
                continue
            
            result['blood_glucose'].append({
                'ts': ts,
                'date': date,
                'glucose_mgdl': glucose_mgdl,
                'device_id': DEVICE_GLUCOSE,
                'person': OWN_PERSON_ID,
                'source': SOURCE
            })


def _parse_int(value: str) -> int | None:
    """Parsed Integer aus String, leere Strings → None"""
    if not value or not value.strip():
        return None
    try:
        return int(float(value.strip()))
    except ValueError:
        return None


def _parse_float(value: str) -> float | None:
    """Parsed Float aus String, leere Strings → None"""
    if not value or not value.strip():
        return None
    try:
        return float(value.strip().replace(',', '.'))
    except ValueError:
        return None


def get_update_cutoffs(conn) -> dict:
    """Holt die letzten Import-Daten für --update Modus"""
    cutoffs = {}
    
    # Blutdruck
    row = conn.execute(
        "SELECT MAX(date) FROM blood_pressure WHERE person=? AND source=?",
        (OWN_PERSON_ID, SOURCE)
    ).fetchone()
    cutoffs['blood_pressure'] = row[0] if row and row[0] else None
    
    # ECG-Sessions
    row = conn.execute(
        "SELECT MAX(datetime) FROM ecg_sessions WHERE person=? AND source=?",
        (OWN_PERSON_ID, SOURCE)
    ).fetchone()
    cutoffs['ecg_sessions'] = row[0] if row and row[0] else None
    
    # Blutzucker
    row = conn.execute(
        "SELECT MAX(date) FROM blood_glucose WHERE person=? AND source=?",
        (OWN_PERSON_ID, SOURCE)
    ).fetchone()
    cutoffs['blood_glucose'] = row[0] if row and row[0] else None
    
    # Measurements (verschiedene Metriken)
    metrics = [
        'weight_kg', 'height_cm', 'spo2', 'ecg_afib_result', 'ecg_valvular_result',
        'ecg_qrs_duration_ms', 'ecg_pr_duration_ms', 'ecg_qt_duration_ms',
        'ecg_qtc_duration_ms', 'menstrual_flow', 'ovulation_test_result',
        'body_fat_kg', 'bone_mass_kg', 'muscle_mass_kg', 'water_mass_kg'
    ]
    for metric in metrics:
        row = conn.execute(
            "SELECT MAX(date) FROM measurements WHERE person=? AND source_app=? AND metric=?",
            (OWN_PERSON_ID, SOURCE, metric)
        ).fetchone()
        cutoffs[f'measurements_{metric}'] = row[0] if row and row[0] else None
    
    return cutoffs


def import_file(conn, path: Path, update_from: dict | None = None) -> int:
    """Importiert eine Withings-ZIP-Datei in die Datenbank.
    
    Args:
        conn: Datenbankverbindung
        path: Pfad zur ZIP-Datei
        update_from: Optional dict mit Cutoff-Daten für --update Modus
    
    Returns:
        Anzahl der importierten Zeilen
    """
    parsed = parse_withings_zip(path)
    total_imported = 0
    cur = conn.cursor()
    
    # Blutdruck
    for row in parsed['blood_pressure']:
        if update_from and update_from.get('blood_pressure'):
            if row['date'] <= update_from['blood_pressure']:
                continue
        cur.execute(
            "INSERT OR IGNORE INTO blood_pressure "
            "(ts, date, systolic, diastolic, pulse, notes, person, source, device_id) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (row['ts'], row['date'], row['systolic'], row['diastolic'],
             row['pulse'], row['notes'], row['person'], row['source'], row['device_id'])
        )
        total_imported += cur.rowcount
    
    # Measurements (EAV)
    for row in parsed['measurements']:
        metric = row['metric']
        cutoff_key = f'measurements_{metric}'
        if update_from and update_from.get(cutoff_key):
            if row['date'] <= update_from[cutoff_key]:
                continue
        cur.execute(
            "INSERT OR IGNORE INTO measurements "
            "(ts, date, metric, value, unit, device_id, person, source_app) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (row['ts'], row['date'], row['metric'], row['value'],
             row['unit'], row['device_id'], row['person'], row['source_app'])
        )
        total_imported += cur.rowcount
    
    # ECG-Sessions
    for row in parsed['ecg_sessions']:
        if update_from and update_from.get('ecg_sessions'):
            if row['datetime'] <= update_from['ecg_sessions']:
                continue
        cur.execute(
            "INSERT OR IGNORE INTO ecg_sessions "
            "(datetime, classification, symptoms, sample_rate_hz, lead, duration_s, device_id, person, source) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (row['datetime'], row['classification'], row['symptoms'],
             row['sample_rate_hz'], row['lead'], row['duration_s'],
             row['device_id'], row['person'], row['source'])
        )
        total_imported += cur.rowcount
    
    # ECG-Samples
    for row in parsed['ecg_samples']:
        # ECG-Samples werden zusammen mit den Sessions importiert
        cur.execute(
            "INSERT OR IGNORE INTO ecg_samples "
            "(session_dt, session_person, sample_index, uv) "
            "VALUES (?,?,?,?)",
            (row['session_dt'], row['session_person'], row['sample_index'], row['uv'])
        )
        total_imported += cur.rowcount
    
    # Blutzucker
    for row in parsed['blood_glucose']:
        if update_from and update_from.get('blood_glucose'):
            if row['date'] <= update_from['blood_glucose']:
                continue
        cur.execute(
            "INSERT OR IGNORE INTO blood_glucose "
            "(ts, date, glucose_mgdl, device_id, person, source) "
            "VALUES (?,?,?,?,?,?)",
            (row['ts'], row['date'], row['glucose_mgdl'],
             row['device_id'], row['person'], row['source'])
        )
        total_imported += cur.rowcount
    
    conn.commit()
    return total_imported


def main():
    parser = argparse.ArgumentParser(description="Import Withings Health Mate GDPR export")
    parser.add_argument('--file', type=Path, help='Path to Withings ZIP file')
    parser.add_argument('--update', action='store_true', 
                        help='Only import data newer than last import')
    parser.add_argument('--inbox', action='store_true', 
                        help='Process files from imports/_inbox/')
    add_lang_arg(parser)
    args = parser.parse_args()
    apply_lang_from_args(args)
    
    inbox_dir = _cfg.data_root / "_inbox"
    processed_dir = inbox_dir / "processed"
    processed_dir.mkdir(parents=True, exist_ok=True)
    
    if args.inbox:
        # Verarbeite alle Dateien im Inbox-Verzeichnis
        import glob
        files = sorted(glob.glob(str(inbox_dir / "data_*.zip")))
        if not files:
            print(t(f"Keine Withings-ZIP-Dateien gefunden in {inbox_dir}",
                    f"No Withings ZIP files found in {inbox_dir}"))
            return

        total_count = 0
        with open_db() as conn:
            for file_path in files:
                count = import_file(conn, Path(file_path))
                total_count += count
                # Nach erfolgreichem Import verschieben
                try:
                    Path(file_path).rename(processed_dir / Path(file_path).name)
                except Exception as e:
                    print(t(f"Warnung: Konnte {file_path} nicht nach processed/ verschieben: {e}",
                            f"Warning: Could not move {file_path} to processed: {e}"))

                if count > 0:
                    log_import(conn, 'withings', str(file_path), count)

        print(t(f"{total_count} Zeilen aus {len(files)} Dateien importiert",
                f"Imported {total_count} rows from {len(files)} files"))
        return

    # Einzelne Datei oder neueste in withings_dir
    if args.file:
        file_path = args.file
    else:
        # Neueste ZIP-Datei in withings_dir finden
        files = sorted(_cfg.withings_dir.glob("data_*.zip"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not files:
            print(t(f"Keine Withings-ZIP-Dateien gefunden in {_cfg.withings_dir}",
                    f"No Withings ZIP files found in {_cfg.withings_dir}"))
            return
        file_path = files[0]

    if not file_path.exists():
        print(t(f"Datei nicht gefunden: {file_path}", f"File not found: {file_path}"))
        return

    with open_db() as conn:
        update_from = None
        if args.update:
            update_from = get_update_cutoffs(conn)

        count = import_file(conn, file_path, update_from)
        if count > 0:
            log_import(conn, 'withings', str(file_path), count)
        print(t(f"{count} Zeilen importiert aus {file_path}",
                f"Imported {count} rows from {file_path}"))


if __name__ == '__main__':
    main()