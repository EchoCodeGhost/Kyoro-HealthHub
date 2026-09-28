#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Polar GDPR Export → health.db

@tier        infrastructure
@purpose.de  Importiert Daten aus Polar GDPR-Exporten (JSON-Dateien) in die health.db.
             Unterstützt Trainingsdaten, tägliche Aktivität, 24/7 Herzfrequenz,
             PPI-Daten, Fitness-Assessments, HRV-Daten, Schlafdetails und orthostatische Tests.
@purpose.en  Imports data from Polar GDPR exports (JSON files) into health.db.
             Supports training data, daily activity, 24/7 heart rate, PPI data,
             fitness assessments, HRV data, sleep details, and orthostatic tests.
@method.de   Liest JSON-Dateien aus dem Polar-Verzeichnis (Konfiguration: polar_dir).
             Jede Datei wird geparst und die Daten in die entsprechenden Tabellen
             geschrieben. Unterstützt mehrere Polar-Geräte aus der device_registry.
             Mapping: trainings → sessions + session_metrics, daily_activity →
             measurements, ppi → ppi_raw, nightly_hrv → polar_nightly_hrv, etc.
             --update/--from/--to filtern jetzt tatsächlich (jede Parse-Funktion
             bekommt date_from/date_to und überspringt Einträge außerhalb des
             Fensters) — vorher waren diese Flags reine No-op-Argumente, jeder
             Lauf hat immer den kompletten Bestand neu geparst (INSERT OR IGNORE
             hat das nur unsichtbar gemacht, nicht schneller). Alle Dateien
             werden trotzdem weiterhin geöffnet/geparst, um ihr eingebettetes
             Datum zu prüfen — kein Dateiname-basiertes Pre-Filtering, also kein
             I/O-Geschwindigkeitsgewinn, nur weniger unnötige DB-Schreibversuche.
             --update ermittelt date_from aus dem spätesten bereits importierten
             Datum über sessions/measurements/ppi_raw/polar_nightly_hrv/
             polar_sleep_hypnogram/polar_sleep_wake hinweg (nicht nur eine
             Tabelle — manche Datentypen landen nie in sessions).
@method.en   Reads JSON files from the Polar directory (config: polar_dir).
             Each file is parsed and data is written to the corresponding tables.
             Supports multiple Polar devices from the device registry.
             Mapping: trainings → sessions + session_metrics, daily_activity →
             measurements, ppi → ppi_raw, nightly_hrv → polar_nightly_hrv, etc.
             --update/--from/--to now actually filter (every parse function
             receives date_from/date_to and skips entries outside the window) —
             previously these flags were pure no-op arguments, every run always
             reparsed the entire archive (INSERT OR IGNORE just made that
             invisible, not faster). All files are still opened/parsed to check
             their embedded date — no filename-based pre-filtering, so no I/O
             speed gain, only fewer unnecessary DB write attempts. --update
             derives date_from from the latest already-imported date across
             sessions/measurements/ppi_raw/polar_nightly_hrv/
             polar_sleep_hypnogram/polar_sleep_wake (not just one table — some
             data types never end up in sessions).
@reads       {polar_dir}/*.json (Polar GDPR Export)
@writes      health.db (sessions, session_metrics, measurements, ppi_raw,
             assessments, polar_nightly_hrv, polar_sleep_hypnogram,
             polar_sleep_wake, polar_skin_contact, polar_hrv_spot)
@limits.de   Keine Validierung der Polar-Datenqualität. Abhängig von der
             Korrektheit des GDPR-Exports. Keine medizinische Interpretation.
             vo2max stammt aus physicalInformation.vo2Max — Polars eigenem
             täglichem Profil-Snapshot, keine tagesaktuelle Einzelmessung wie
             bei Apple/Garmin. Kann über Monate exakt denselben Wert
             wiederholen, wenn Polars Algorithmus mangels ausreichend
             strukturierter Trainingsdaten keine neue Schätzung berechnet
             (beobachtet: 2626 Werte 2017-2026, seit Ende Mai 2026 durchgängig
             18,0 — kein Kyoro-Bug, sondern Polar-seitiges Verhalten). Nicht
             unreflektiert mit anderen Geräten mitteln/vergleichen.
             --archive verschiebt ALLE *.json-Dateien im Verzeichnis nach
             originals/ — läuft deshalb NUR bei vollem Bestand (kein
             --update/--from/--to gesetzt), sonst übersprungen mit Hinweis.
             Sonst könnte eine wegen des Datumsfilters übersprungene, nie
             erfolgreich importierte Datei mit archiviert werden.

@relevance.de  Ermöglicht den Import von Herzfrequenz- und Aktivitätsdaten aus Polar-Geräten, essentiell für die kardiale Analyse
@relevance.en  Enables import of heart rate and activity data from Polar devices, essential for cardiac analysis
@limits.en   No validation of Polar data quality. Dependent on the correctness
             of the GDPR export. No medical interpretation.
             vo2max comes from physicalInformation.vo2Max — Polar's own daily
             profile snapshot, not a fresh per-day measurement like Apple/
             Garmin. Can repeat the exact same value for months when Polar's
             algorithm has too little structured training data to compute a
             new estimate (observed: 2626 values 2017-2026, stuck at exactly
             18.0 since late May 2026 — not a Kyoro bug, Polar-side behavior).
             Do not blend/average uncritically against other devices.
             --archive moves ALL *.json files in the directory to originals/ —
             therefore only runs on a full pass (no --update/--from/--to set),
             otherwise skipped with a notice. Otherwise a file skipped by the
             date filter and never successfully imported could get archived
             along with the rest.
@usage
    python import_polar.py
    python import_polar.py --update
    python import_polar.py --from 2026-08-01 --to 2026-08-31
    python import_polar.py --dir /pfad/zu/polar/daten
"""

import glob
import json
import re
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
import sys as _sys
_sys.path.insert(0, str(Path(__file__).parent.parent))
from health_config import Config as _Cfg, OWN_PERSON_ID
from modules.db import open_db
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from modules.base import log_import, resolve_timezone
_cfg = _Cfg()

POLAR_DIR = _cfg.polar_dir
POLAR_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH   = _cfg.db_path

PERSON = OWN_PERSON_ID
SOURCE = 'polar_connect'


def _in_range(date_s: str, date_from: str | None, date_to: str | None) -> bool:
    """True wenn date_s (YYYY-MM-DD) innerhalb [date_from, date_to] liegt (beide optional)."""
    if date_from and date_s < date_from:
        return False
    if date_to and date_s > date_to:
        return False
    return True


def _get_last_import(conn) -> str | None:
    """Letztes tatsächlich importiertes Datum für --update, über alle von
    diesem Importer beschriebenen Tabellen hinweg (nicht nur sessions —
    ppi_raw/measurements sind für manche Datentypen die einzige Quelle,
    s. gleichnamige Funktion in import_polar_accesslink.py für den Bug,
    den diese Mehrfachabfrage vermeidet)."""
    r = conn.execute("""
        SELECT MAX(d) FROM (
            SELECT MAX(date) AS d FROM sessions WHERE source_app=?
            UNION ALL
            SELECT MAX(date) AS d FROM measurements WHERE source_app=?
            UNION ALL
            SELECT MAX(datetime(datetime)) AS d FROM ppi_raw WHERE source=?
            UNION ALL
            SELECT MAX(date) AS d FROM polar_nightly_hrv
            UNION ALL
            SELECT MAX(date) AS d FROM polar_sleep_hypnogram
            UNION ALL
            SELECT MAX(date) AS d FROM polar_sleep_wake
        )
    """, (SOURCE, SOURCE, SOURCE)).fetchone()
    return r[0][:10] if r and r[0] else None

def _first_polar(*, sensor_type: str | None = None, model: str | None = None) -> str | None:
    """device_id des ersten passenden Polar-Geräts aus device_registry."""
    for d in _cfg.device_registry:
        if d.get("brand", "").lower() != "polar":
            continue
        if sensor_type and d.get("sensor_type") == sensor_type:
            return d.get("device_id")
        if model and model.lower() in d.get("model", "").lower():
            return d.get("device_id")
    return None

# Generic Polar fallback (kein Modell identifizierbar) — erstes Polar-Gerät aus Registry
DEVICE_POLAR = next(
    (d["device_id"] for d in _cfg.device_registry
     if d.get("brand", "").lower() == "polar" and d.get("device_id")),
    "polar",
)
DEVICE_H10 = _first_polar(sensor_type="chest_strap") or DEVICE_POLAR
DEVICE_H7  = _first_polar(model="H7") or DEVICE_POLAR
DEVICE_V3  = _first_polar(model="Vantage V3") or DEVICE_POLAR

# Polar wrist-device serials that recorded H7/H10 chest-strap RR intervals.
# Derived from device_registry (brand=Polar, sensor_type=optical_wrist*, serial set).
_H7_RECEIVER_SERIALS: set[str] = {
    d["serial"]
    for d in _cfg.device_registry
    if (d.get("brand", "").lower() == "polar"
        and d.get("sensor_type") in {"optical_wrist", "optical_wrist_gps"}
        and d.get("serial"))
}

# Serial → device_id mapping for all Polar devices (used in ppi_raw device tagging).
_POLAR_SERIAL_TO_DEVICE_ID: dict[str, str] = {
    d["serial"]: d["device_id"]
    for d in _cfg.device_registry
    if d.get("brand", "").lower() == "polar" and d.get("serial") and d.get("device_id")
}


def _extend_with_raw_hex_serials(serial_map: dict[str, str]) -> None:
    """Adds raw hex serial → device_id entries (from identity.db's
    device_serial_map) alongside the SN- pseudonym entries already in
    serial_map. Some Polar export file types (ppi_samples, training-session
    deviceId) use the raw hex serial instead of the SN- pseudonym used in
    registry.json — without this, those rows fell through to the raw hex
    value itself as a fallback device id, which a later pseudonymization
    pass then minted as a brand-new DEV-XXXXXXXX, duplicating the device
    under a second identity. In-place update, no-op if identity.db is absent.
    """
    from health_config import KYORO_CONFIG_DIR
    identity_db_path = KYORO_CONFIG_DIR / "identity.db"
    if not identity_db_path.exists():
        return
    conn = sqlite3.connect(identity_db_path)
    try:
        for pseudo_id, _device_id, serial_real, _created in conn.execute(
            "SELECT pseudo_id, device_id, serial_real, created_at FROM device_serial_map"
        ):
            if pseudo_id in serial_map and serial_real not in serial_map:
                serial_map[serial_real] = serial_map[pseudo_id]
    finally:
        conn.close()


_extend_with_raw_hex_serials(_POLAR_SERIAL_TO_DEVICE_ID)


def polar_serial_to_device_id_for_person(person: "str | None" = None) -> dict[str, str]:
    """Personen-bewusste Variante von _POLAR_SERIAL_TO_DEVICE_ID.

    Der Modul-Level-Dict _POLAR_SERIAL_TO_DEVICE_ID kommt aus der lokalen
    Config (_cfg.device_registry) — bewusst UNVERAENDERT gelassen, da er von
    der taeglichen Import-Pipeline genutzt wird und jede Aenderung daran ein
    Risiko fuer den produktiven Import waere. Fuer person=None (Default) wird
    exakt dieser bestehende Dict zurueckgegeben — kein Verhalten geaendert.

    Fuer ein explizites person baut diese Funktion stattdessen aus der
    devices-DB-Tabelle (die schon eine person-Spalte hat, s.
    CONTRIBUTING.md "Adding a New Device") eine Zuordnung NUR fuer die
    Geraete dieser Person — genutzt von den fix_polar_*_device_ids.py-
    Migrationsskripten, damit ihr --person-Flag echte Wirkung hat, nicht nur
    kosmetisch im Log steht (s. add-provenance-logging).
    """
    if person is None:
        return _POLAR_SERIAL_TO_DEVICE_ID
    conn = open_db()
    try:
        serial_map = {
            serial: device_id
            for serial, device_id in conn.execute(
                "SELECT serial, device_id FROM devices WHERE person=? AND serial IS NOT NULL",
                (person,),
            )
        }
    finally:
        conn.close()
    _extend_with_raw_hex_serials(serial_map)
    return serial_map

# Polar wrist devices sorted by date_from for timeline lookup.
_POLAR_WRIST_TIMELINE: list[dict] = sorted(
    [d for d in _cfg.device_registry
     if d.get("brand", "").lower() == "polar"
     and d.get("sensor_type") in {"optical_wrist", "optical_wrist_gps"}
     and d.get("device_id") and d.get("date_from")],
    key=lambda d: d["date_from"],
)

# Polar chest-strap devices sorted by date_from for timeline lookup — mirrors
# _POLAR_WRIST_TIMELINE. Without this, chest-strap RR intervals were tagged
# with a single hardcoded device_id (DEVICE_H7) regardless of date, ignoring
# any later chest-strap swap recorded in device_registry.
_POLAR_CHEST_STRAP_TIMELINE: list[dict] = sorted(
    [d for d in _cfg.device_registry
     if d.get("brand", "").lower() == "polar"
     and d.get("sensor_type") == "chest_strap"
     and d.get("device_id") and d.get("date_from")],
    key=lambda d: d["date_from"],
)


def _nearest_device_for_date(timeline: list[dict], date_str: str, fallback: str) -> str:
    """Gerät, das an date_str aktiv war; bei Lücken (kein Gerät exakt
    zustaendig) das zuletzt vor date_str registrierte Geraet statt eines
    beliebigen Listen-ersten Eintrags — aeltere Geraete bleiben oft
    sporadisch in Gebrauch, auch nachdem ein neueres Geraet primaer wurde,
    und ein zeitlich nahes Geraet ist eine bessere Vermutung als das
    zufaellig erste Element der Registry-Liste (das war z.B. das aelteste
    Geraet ueberhaupt, unabhaengig von date_str).
    """
    if not date_str or not timeline:
        return fallback
    best_before = None
    for d in reversed(timeline):
        if date_str >= d["date_from"]:
            until = d.get("date_to")
            if until is None or date_str <= until:
                return d["device_id"]
            if best_before is None:
                best_before = d["device_id"]
    return best_before or fallback


def _polar_device_for_date(date_str: str) -> str:
    """Gibt device_id des Polar-Wrist-Geräts zurück, das an date_str aktiv war.

    Nutzt date_from/date_to aus device_registry. Bei Luecken: naechstgelegenes
    Geraet vor date_str (s. _nearest_device_for_date). Letzter Fallback: DEVICE_POLAR.
    """
    return _nearest_device_for_date(_POLAR_WRIST_TIMELINE, date_str, DEVICE_POLAR)


def _polar_chest_strap_for_date(date_str: str) -> str:
    """Gibt device_id des Polar-Brustgurts zurück, der an date_str aktiv war.

    Nutzt date_from/date_to aus device_registry (sensor_type='chest_strap').
    Bei Luecken: naechstgelegenes Geraet vor date_str. Letzter Fallback: DEVICE_H10.
    """
    return _nearest_device_for_date(_POLAR_CHEST_STRAP_TIMELINE, date_str, DEVICE_H10)


# ── Database: only Custom-Tables (nicht im v2-Core) ────────────────────────
def setup_db(conn: sqlite3.Connection) -> None:
    for _tbl in ("polar_nightly_hrv", "polar_hrv_spot"):
        _row = conn.execute("SELECT type FROM sqlite_master WHERE name=?", (_tbl,)).fetchone()
        if _row and _row[0] == "view":
            conn.execute(f"DROP VIEW {_tbl}")
    conn.commit()
    conn.executescript("""
    -- Polar-spezifische Nacht-HRV (ANS Recharge) — kein generisches Mapping
    CREATE TABLE IF NOT EXISTS polar_nightly_hrv (
        date                    TEXT NOT NULL,
        person                  TEXT NOT NULL DEFAULT 'unknown',
        rmssd_ms                REAL,
        rri_ms                  REAL,
        respiration_ms          REAL,
        recovery_indicator      INTEGER,
        recovery_sublevel       INTEGER,
        ans_status              REAL,
        ans_rate                INTEGER,
        baseline_rri_ms         REAL,
        baseline_rri_sd         REAL,
        baseline_rmssd_ms       REAL,
        baseline_rmssd_sd       REAL,
        baseline_respiration_ms REAL,
        baseline_respiration_sd REAL,
        source                  TEXT DEFAULT 'polar',
        PRIMARY KEY (date, person)
    );

    -- HRV-Spot mit Pulse Arrival Time (Vantage V3)
    CREATE TABLE IF NOT EXISTS polar_hrv_spot (
        datetime         TEXT PRIMARY KEY,
        device           TEXT,
        hr_bpm           REAL,
        hrv_ms           REAL,
        hrv_level        TEXT,
        rri_ms           REAL,
        ptt_contract_ms  REAL,
        ptt_relax_ms     REAL,
        ptt_quality      REAL,
        source           TEXT DEFAULT 'polar_v3'
    );

    -- Hautkontakt-Events
    CREATE TABLE IF NOT EXISTS polar_skin_contact (
        datetime    TEXT,
        device      TEXT,
        contact     INTEGER,
        PRIMARY KEY (datetime, device)
    );
    CREATE INDEX IF NOT EXISTS idx_skin_contact_dt ON polar_skin_contact(datetime);

    -- polar_sleep_hypnogram ist bereits im v2-Schema
    CREATE TABLE IF NOT EXISTS polar_sleep_hypnogram (
        date        TEXT,
        offset_s    INTEGER,
        state       TEXT,
        sleep_start TEXT,
        PRIMARY KEY (date, offset_s)
    );
    CREATE INDEX IF NOT EXISTS idx_hypno_date ON polar_sleep_hypnogram(date);

    -- polar_sleep_wake ist bereits im v2-Schema
    CREATE TABLE IF NOT EXISTS polar_sleep_wake (
        date        TEXT,
        device      TEXT,
        millis_in_day INTEGER,
        state       TEXT,
        PRIMARY KEY (date, device, millis_in_day)
    );
    CREATE INDEX IF NOT EXISTS idx_sleep_wake_date ON polar_sleep_wake(date);
    """)
    conn.commit()

    # Migration: add person column to existing polar_nightly_hrv tables that predate B-05
    cols = {r[1] for r in conn.execute("PRAGMA table_info(polar_nightly_hrv)").fetchall()}
    if "person" not in cols:
        conn.execute("ALTER TABLE polar_nightly_hrv ADD COLUMN person TEXT NOT NULL DEFAULT 'unknown'")
        conn.execute("UPDATE polar_nightly_hrv SET person = ? WHERE person IN ('self', 'unknown')", (OWN_PERSON_ID,))
        conn.commit()


# ── Hilfsfunktionen ───────────────────────────────────────────────────────────
def parse_duration(iso: str) -> int:
    """ISO 8601 Dauer (PT3600S, PT1H30M) → seconds."""
    if not iso:
        return 0
    m = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+(?:\.\d+)?)S)?', iso)
    if not m:
        return 0
    h, mi, s = (float(x or 0) for x in m.groups())
    return int(h * 3600 + mi * 60 + s)


def training_session_identifier(d: dict, filepath) -> str:
    """Stabile Session-ID aus dem Trainings-JSON: identifier.id, sonst Dateiname.

    d.get('identifier') ist im Polar-Export ein Dict ({"id": "..."}), kein
    Skalar — eine reine scalar()/isinstance(str)-Prüfung liefert dafür immer
    None und fällt auf den Dateinamen zurück. Der Dateiname ändert sich aber
    bei jedem Re-Export/Re-Sync desselben Trainings, wodurch dieselbe
    physische Session bei jedem Sync als neue sessions-Zeile importiert wurde
    (s. scripts/migrations/dedupe_polar_training_sessions.py für die
    Bereinigung bereits importierter Duplikate).
    """
    raw = d.get('identifier')
    if isinstance(raw, dict):
        raw = raw.get('id')
    return raw or Path(filepath).stem


def _meas(conn, rows: list) -> None:
    if rows:
        conn.executemany(
            "INSERT OR IGNORE INTO measurements "
            "(ts, date, metric, value, value_text, unit, device_id, person, source_app) "
            "VALUES (?,?,?,?,?,?,?,?,?)", rows)


def _metrics(cur, session_id: str, pairs: list) -> None:
    for metric, value, value_text, unit in pairs:
        if value is None and value_text is None:
            continue
        cur.execute(
            "INSERT OR IGNORE INTO session_metrics(session_id, metric, value, value_text, unit) "
            "VALUES (?,?,?,?,?)",
            (session_id, metric, value, value_text, unit)
        )


SPORT_NAMES = {
    '1':'Laufen', '2':'Radfahren', '3':'Schwimmen', '4':'Skifahren',
    '5':'Reiten', '7':'Fußball', '9':'Aerobics', '10':'Fitness',
    '11':'Crosstrainer', '14':'Yoga', '15':'Turnen',
    '16':'Outdoorsport', '20':'Wandern', '22':'Rudern', '24':'Inlineskaten',
    '28':'Tanzen', '39':'Triathlon', '44':'Crosstraining', '57':'Pilates',
    '66':'Spazieren', '82':'SUP', '83':'Krafttraining', '96':'Meditation',
}


def _training_load(d: dict):
    """Liest training_load aus dem JSON: zuerst Top-Level (ältere API),
    dann trainingLoadReport.cardioLoad (Polar Flow ab ~2024, Vantage V3 / Loop).
    muscleLoad wird hier ignoriert (-1.0 = not available) — separat in
    _muscle_load() erfasst, nicht mit cardioLoad vermischt."""
    tl = d.get('trainingLoad')
    if tl is not None and isinstance(tl, (int, float)) and tl > 0:
        return tl
    report = d.get('trainingLoadReport') or {}
    cl = report.get('cardioLoad')
    if cl is not None and isinstance(cl, (int, float)) and cl > 0:
        return round(cl, 1)
    return None


def _muscle_load(d: dict):
    """Liest trainingLoadReport.muscleLoad (Polar Flow ab ~2024, Vantage V3 /
    Loop) — eigene Metrik, getrennt von cardioLoad/training_load, damit
    beide Belastungsdimensionen unabhängig beobachtbar bleiben. -1.0 =
    von Polar als 'not available' markiert, wird wie fehlend behandelt."""
    report = d.get('trainingLoadReport') or {}
    ml = report.get('muscleLoad')
    if ml is not None and isinstance(ml, (int, float)) and ml > 0:
        return round(ml, 1)
    return None


# Polar setzt dieses Feld bei geraeteseitig automatisch erkannten Aktivitaeten
# (z.B. Duschen, Hausarbeit — kein bewusst gestartetes Training). Betraf in der
# Praxis vor allem die Loop-Aera (Aktivitaets-Tracker mit Auto-Erkennung);
# Ignite 2/Vantage V3 als manuell gestartete Sportuhren zeigten das Feld nie.
AUTO_DETECTED_START_TRIGGER = "TRAINING_START_AUTOMATIC_TRAINING_DETECTION"


def is_polar_auto_detected(d: dict) -> bool:
    return d.get('startTrigger') == AUTO_DETECTED_START_TRIGGER


# ── Polar Workouts → sessions + session_metrics ──────────────────────────────
# 'training*.json' matcht auch training-target-*.json — geplante, aber laut
# eigenem 'done': false NIE durchgeführte Trainingsziele aus Polars
# Trainingstagebuch (kein stopTime, kein deviceId, kein trainingLoad). Die
# wurden bislang als echte Sessions importiert (s. dedupe_polar_training_sessions.py
# für die Bereinigung bereits importierter Phantom-Zeilen). Nur echte
# Aufzeichnungen tragen das Praefix 'training-session_'.
TRAINING_SESSION_GLOB = "training-session_*.json"


def import_polar_trainings(conn: sqlite3.Connection, polar_dir: Path = POLAR_DIR,
                            date_from: str | None = None, date_to: str | None = None) -> int:
    files = sorted(glob.glob(str(polar_dir / TRAINING_SESSION_GLOB)))
    cur   = conn.cursor()
    count = 0
    for f in files:
        try:
            d = json.load(open(f))
        except Exception:
            continue

        def scalar(v):
            return v if not isinstance(v, (dict, list)) else None

        sport    = d.get('sport', {})
        sport_id = str(sport.get('id', '') if isinstance(sport, dict) else '')
        sport_name = SPORT_NAMES.get(sport_id, f'Sport {sport_id}')
        identifier = training_session_identifier(d, f)
        sid = f"polar_training_{identifier}"

        start = scalar(d.get('startTime')) or ''
        stop  = scalar(d.get('stopTime'))
        date_s = start[:10] if start else ''
        if not date_s or not _in_range(date_s, date_from, date_to):
            continue

        # Trainings-JSON trägt die echte Geräte-Seriennummer direkt im Feld
        # 'deviceId' — nutzen statt der unsicheren Datums-Ratelogik, sobald
        # verfügbar (vorher wurde deviceId ignoriert).
        raw_serial = scalar(d.get('deviceId'))
        device_name = (_POLAR_SERIAL_TO_DEVICE_ID.get(raw_serial)
                       if raw_serial else None) or _polar_device_for_date(date_s)

        if cur.execute("SELECT 1 FROM sessions WHERE id=?", (sid,)).fetchone():
            continue

        cur.execute(
            "INSERT OR IGNORE INTO sessions "
            "(id, type, ts_start, ts_end, date, device_id, person, source_app, sport) "
            "VALUES (?, 'training', ?, ?, ?, ?, ?, ?, ?)",
            (sid, start, stop, date_s, device_name, PERSON, SOURCE, sport_name)
        )

        recovery_h = (int(d.get('recoveryTimeMillis') or 0)) / 3_600_000
        auto_detected = is_polar_auto_detected(d)
        # Automatisch erkannte Aktivitaeten bekommen KEINEN training_load —
        # sonst zaehlen Alltagsbewegungen (Duschen etc.) als "Sportwerte" in
        # tl_d/den PEM-Trigger. Die Session selbst bleibt erhalten (Audit-Trail,
        # auto_detected-Flag dokumentiert den Grund fuer das fehlende training_load).
        _metrics(cur, sid, [
            ("sport_name",    None,                          sport_name, None),
            ("sport_id",      None,                          sport_id,   None),
            ("duration_s",    (scalar(d.get('durationMillis')) or 0) // 1000, None, "s"),
            ("distance_m",    scalar(d.get('distanceMeters')),  None, "m"),
            ("calories",      scalar(d.get('calories')),         None, "kcal"),
            ("hr_avg",        scalar(d.get('hrAvg')),            None, "bpm"),
            ("hr_max",        scalar(d.get('hrMax')),            None, "bpm"),
            ("training_load", None if auto_detected else _training_load(d), None, None),
            ("muscle_load",   None if auto_detected else _muscle_load(d),   None, None),
            ("recovery_h",    round(recovery_h, 1) if recovery_h else None, None, "h"),
            ("carbo_pct",     scalar(d.get('carboPercentage')),  None, "%"),
            ("fat_pct",       scalar(d.get('fatPercentage')),    None, "%"),
            ("auto_detected", 1.0 if auto_detected else 0.0,     None, None),
        ])
        count += 1
    conn.commit()
    return count


# ── Backfill training_load für Sessions ohne Eintrag (Polar API-Umstieg 2024) ─
def backfill_training_load(conn: sqlite3.Connection, polar_dir: Path = POLAR_DIR) -> int:
    """Füllt fehlende training_load-Einträge in session_metrics für bereits importierte
    Polar-Sessions nach. Wird benötigt da INSERT OR IGNORE vorhandene Sessions überspringt."""
    files = sorted(glob.glob(str(polar_dir / TRAINING_SESSION_GLOB)))
    cur   = conn.cursor()
    count = 0
    for f in files:
        try:
            d = json.load(open(f))
        except Exception:
            continue
        identifier = training_session_identifier(d, f)
        sid = f"polar_training_{identifier}"
        load = _training_load(d)
        if load is None:
            continue
        exists = cur.execute("SELECT 1 FROM sessions WHERE id=?", (sid,)).fetchone()
        if not exists:
            continue
        already = cur.execute(
            "SELECT 1 FROM session_metrics WHERE session_id=? AND metric='training_load'", (sid,)
        ).fetchone()
        if already:
            continue
        cur.execute(
            "INSERT OR IGNORE INTO session_metrics (session_id, metric, value) VALUES (?,?,?)",
            (sid, 'training_load', load)
        )
        count += 1
    conn.commit()
    return count


# ── Backfill muscle_load für Sessions ohne Eintrag ────────────────────────────
def backfill_muscle_load(conn: sqlite3.Connection, polar_dir: Path = POLAR_DIR) -> int:
    """Analog zu backfill_training_load: füllt fehlende muscle_load-Einträge
    für bereits importierte Polar-Sessions nach (neue Metrik, s. _muscle_load())."""
    files = sorted(glob.glob(str(polar_dir / TRAINING_SESSION_GLOB)))
    cur   = conn.cursor()
    count = 0
    for f in files:
        try:
            d = json.load(open(f))
        except Exception:
            continue
        identifier = training_session_identifier(d, f)
        sid = f"polar_training_{identifier}"
        load = _muscle_load(d)
        if load is None:
            continue
        exists = cur.execute("SELECT 1 FROM sessions WHERE id=?", (sid,)).fetchone()
        if not exists:
            continue
        already = cur.execute(
            "SELECT 1 FROM session_metrics WHERE session_id=? AND metric='muscle_load'", (sid,)
        ).fetchone()
        if already:
            continue
        cur.execute(
            "INSERT OR IGNORE INTO session_metrics (session_id, metric, value) VALUES (?,?,?)",
            (sid, 'muscle_load', load)
        )
        count += 1
    conn.commit()
    return count


# ── Backfill sport für ältere Sessions (fehlende Spalte) ─────────────────────
def backfill_polar_sport(conn: sqlite3.Connection) -> int:
    cur = conn.cursor()
    # Pass 1: fill NULL sport from session_metrics sport_name
    cur.execute("""
        UPDATE sessions SET sport = (
            SELECT sm.value_text FROM session_metrics sm
            WHERE sm.session_id = sessions.id AND sm.metric = 'sport_name'
        )
        WHERE source_app = ? AND type = 'training' AND sport IS NULL
    """, (SOURCE,))
    n = cur.rowcount
    # Pass 2: remap "Sport <id>" placeholders for IDs now known in SPORT_NAMES
    for sport_id, name in SPORT_NAMES.items():
        cur.execute("""
            UPDATE sessions SET sport = ?
            WHERE source_app = ? AND type = 'training'
              AND sport = ? AND id IN (
                SELECT session_id FROM session_metrics
                WHERE metric='sport_id' AND value_text=?
              )
        """, (name, SOURCE, f'Sport {sport_id}', sport_id))
        if cur.rowcount:
            n += cur.rowcount
            # sync session_metrics too
            cur.execute("""
                UPDATE session_metrics SET value_text = ?
                WHERE metric = 'sport_name' AND value_text = ? AND session_id IN (
                    SELECT id FROM sessions WHERE source_app = ? AND type = 'training'
                )
            """, (name, f'Sport {sport_id}', SOURCE))
    conn.commit()
    return n


# ── Polar dayssaktivität → measurements ──────────────────────────────────────
def import_polar_activity(conn: sqlite3.Connection, polar_dir: Path = POLAR_DIR,
                           date_from: str | None = None, date_to: str | None = None) -> int:
    files = sorted(glob.glob(str(polar_dir / "activity-????-??-??.json")) +
                   glob.glob(str(polar_dir / "activity-????-??-??-*.json")))
    count = 0
    for f in files:
        try:
            d = json.load(open(f))
        except Exception:
            continue
        s    = d.get('summary', {})
        date = d.get('date', '')
        if not date or not _in_range(date, date_from, date_to):
            continue
        ts = f"{date}T00:00:00+00:00"
        levels = {lv['level']: parse_duration(lv['duration'])
                  for lv in s.get('activityLevels', [])}

        step_count = s.get('stepCount')
        samples_obj = d.get('samples', {})
        step_samples = samples_obj.get('steps', []) if isinstance(samples_obj, dict) else []
        if step_count is None and step_samples:
            step_count = sum(
                (e.get('value', 0) or 0)
                for e in step_samples if isinstance(e, dict)
            ) or None

        rows = []
        # Minutengenaue Schrittzahl zusätzlich zur Tagessumme, als eigene
        # Metrik ('steps_1min', nicht 'steps') -- sonst würden Tagessumme
        # und ~1440 Minutenwerte unter demselben Metriknamen vermischt und
        # jede Summenabfrage auf 'steps' würde doppelt zählen. Wird u. a.
        # von compute_orthostatic_detection.py als Bewegungs-Bestätigung im
        # engen Zeitfenster um einen HF-Sprung benötigt (Tagessumme allein
        # sagt nichts über einen einzelnen Zeitpunkt aus).
        for e in step_samples:
            if not isinstance(e, dict):
                continue
            local_time = e.get('localTime')
            val = e.get('value')
            if not local_time or val is None:
                continue
            ts = f"{date}T{local_time[:8]}"
            rows.append((ts, date, 'steps_1min', float(val), None, 'steps',
                         _polar_device_for_date(date), PERSON, SOURCE))
        for metric, val, unit in [
            ('steps',            step_count,                                       'steps'),
            ('distance_m',       s.get('stepsDistance'),                           'm'),
            ('calories',         s.get('calories'),                                'kcal'),
            ('sleep_quality',    round(s.get('sleepQuality', 0), 4) or None,       None),
            ('sleep_duration_s', parse_duration(s.get('sleepDuration', '')) or None, 's'),
            ('met_minutes',      round(s.get('dailyMetMinutes', 0), 2) or None,    'MET·min'),
            ('inactivity_alerts',s.get('inactivityAlertCount'),                    None),
            ('level_sleep_s',    levels.get('SLEEP') or None,                      's'),
            ('level_sedentary_s',levels.get('SEDENTARY') or None,                  's'),
            ('level_light_s',    levels.get('LIGHT') or None,                      's'),
            ('level_moderate_s', (levels.get('CONTINUOS_MODERATE', 0) +
                                  levels.get('INTERMITTENT_MODERATE', 0)) or None, 's'),
            ('level_vigorous_s', (levels.get('CONTINUOS_VIGOROUS', 0) +
                                  levels.get('INTERMITTENT_VIGOROUS', 0)) or None, 's'),
        ]:
            if val is not None:
                rows.append((ts, date, metric, float(val), None, unit, _polar_device_for_date(date), PERSON, SOURCE))

        # physicalInformation: Snapshot des Polar-Nutzerprofils zum Exportzeitpunkt
        # dieser Datei. sex/birthday sind statische Attribute (nicht Teil des
        # EAV-Zeitreihen-Schemas, Geburtsdatum lebt bereits in health_config.json)
        # und werden bewusst NICHT importiert. Die übrigen Werte ändern sich über
        # Jahre (Gewicht, VO2max, Ruhe-/Maximal-HF, Schwellen) und ergeben eine
        # grobe Verlaufskurve aus Polars eigenem Profil-Snapshot pro Tag.
        # restingHeartRate bewusst NICHT als 'resting_hr' importiert -- das ist
        # ein selten aktualisiertes Profil-Feld fuer Polars eigene HF-Zonen-
        # Berechnung, keine Tagesmessung, und wuerde unter dem generischen
        # Metriknamen mit echten Tagesmessungen (z.B. Garmin) vermischt.
        phys = d.get('physicalInformation', {})
        for metric, val, unit in [
            ('height_cm',            phys.get('height, cm'),        'cm'),
            ('weight_kg',            phys.get('weight, kg'),        'kg'),
            ('vo2max',               phys.get('vo2Max'),            'ml/kg/min'),
            ('hr_max',               phys.get('maximumHeartRate'),  'bpm'),
            ('polar_profile_resting_hr', phys.get('restingHeartRate'), 'bpm'),
            ('aerobic_threshold',    phys.get('aerobicThreshold'),  'bpm'),
            ('anaerobic_threshold',  phys.get('anaerobicThreshold'),'bpm'),
            ('sleep_goal_s',         parse_duration(phys.get('sleepGoal', '')) or None, 's'),
        ]:
            if val is not None:
                rows.append((ts, date, metric, float(val), None, unit, _polar_device_for_date(date), PERSON, SOURCE))

        _meas(conn, rows)
        count += 1
    conn.commit()
    return count


# ── Polar 24/7 Heart rate → measurements ───────────────────────────────────
def import_polar_247hr(conn: sqlite3.Connection, polar_dir: Path = POLAR_DIR,
                        date_from: str | None = None, date_to: str | None = None) -> int:
    files = sorted(glob.glob(str(polar_dir / "247ohr_*.json")))
    total = 0
    for f in files:
        try:
            d = json.load(open(f))
        except Exception:
            continue
        rows = []
        for day in d.get('deviceDays', []):
            date = day.get('date', '')
            if not date or not _in_range(date, date_from, date_to):
                continue
            # deviceId steckt pro Tag im JSON — echte Geräte-ID nutzen statt
            # der unsicheren Datums-Ratelogik (vorher
            # wurde deviceId hier ignoriert, wie schon bei den Trainings).
            raw_serial = day.get('deviceId')
            device_id = _POLAR_SERIAL_TO_DEVICE_ID.get(raw_serial) if raw_serial else None
            for s in day.get('samples', []):
                if isinstance(s, dict):
                    hr = s.get('heartRate') or s.get('value')
                    if not hr:
                        continue
                    if 'secondsFromDayStart' in s:
                        dt = datetime.strptime(date, '%Y-%m-%d') + \
                             timedelta(seconds=int(s['secondsFromDayStart']))
                        t = dt.strftime('%Y-%m-%dT%H:%M:%S')
                    else:
                        t = s.get('dateTime') or f"{date}T{s.get('time', '00:00:00')}"
                    dev = device_id or _polar_device_for_date(t[:10])
                    rows.append((t, t[:10], 'heart_rate', float(hr), None, 'bpm', dev, PERSON, SOURCE))
                elif isinstance(s, (list, tuple)) and len(s) >= 2:
                    t = str(s[0])
                    dev = device_id or _polar_device_for_date(t[:10])
                    rows.append((t, t[:10], 'heart_rate', float(s[1]), None, 'bpm', dev, PERSON, SOURCE))
        if rows:
            _meas(conn, rows)
            total += len(rows)
    conn.commit()
    return total


# ── Polar PPI → ppi_raw ───────────────────────────────────────────────────────
def import_polar_ppi(conn: sqlite3.Connection, polar_dir: Path = POLAR_DIR,
                      date_from: str | None = None, date_to: str | None = None) -> int:
    files = sorted(glob.glob(str(polar_dir / "ppi*.json")))
    total = 0
    for f in files:
        try:
            d = json.load(open(f))
        except Exception:
            continue
        rows = []
        entries = d if isinstance(d, list) else [d]
        for entry in entries:
            for dev in entry.get('devicePpiSamplesList', []):
                serial    = dev.get('deviceId', '')
                device_id = _POLAR_SERIAL_TO_DEVICE_ID.get(serial, serial or DEVICE_H10)
                for s in dev.get('ppiSamples', []):
                    dt = s.get('sampleDateTime', '')
                    ms = s.get('pulseLength')
                    if dt and ms and _in_range(dt[:10], date_from, date_to):
                        rows.append((dt, int(ms), device_id, SOURCE, PERSON))
        if rows:
            conn.executemany(
                "INSERT OR IGNORE INTO ppi_raw (datetime, pulse_ms, device, source, person) "
                "VALUES (?,?,?,?,?)", rows)
            total += len(rows)
    conn.commit()
    return total


# ── Polar chest-strap RR from training sessions → ppi_raw ────────────────────
def import_polar_rr_samples(conn: sqlite3.Connection, polar_dir: Path = POLAR_DIR,
                             date_from: str | None = None, date_to: str | None = None) -> int:
    """Import chest-strap beat-to-beat RR intervals from training-session rrSamples.

    Chest-strap RR is received via a paired wrist watch (M430 / Ignite 2 /
    Vantage V3 / ...), so the training file's own deviceId identifies the
    watch, not the strap. Which physical chest strap was worn is resolved by
    date via _polar_chest_strap_for_date() against device_registry's
    chest_strap entries — the export format never carries a strap serial.
    Timestamps are reconstructed as UTC from startTime + cumulative durationMillis.
    Deduplicates at file level (Polar exports each session twice).
    """
    files = sorted(glob.glob(str(polar_dir / "training-session_*.json")))
    seen  = set()
    total = 0

    for fn in files:
        try:
            d = json.load(open(fn))
        except Exception:
            continue

        start_str  = d.get('startTime', '')
        device_id  = d.get('deviceId', '')
        tz_offset  = int(d.get('timezoneOffsetMinutes', 0))

        if not start_str or not _in_range(start_str[:10], date_from, date_to):
            continue

        session_key = (start_str, device_id)
        if session_key in seen:
            continue
        seen.add(session_key)

        if device_id not in _H7_RECEIVER_SERIALS:
            continue

        try:
            local_dt = datetime.strptime(start_str, '%Y-%m-%dT%H:%M:%S')
        except ValueError:
            continue
        utc_dt = local_dt - timedelta(minutes=tz_offset)
        current_ms = int(utc_dt.replace(tzinfo=timezone.utc).timestamp() * 1000)
        strap_device_id = _polar_chest_strap_for_date(start_str[:10])

        rows = []
        for ex in d.get('exercises', []):
            rr_list = ex.get('samples', {}).get('rrSamples', [])
            for sample in rr_list:
                dur = sample.get('durationMillis')
                if not dur:
                    continue
                current_ms += int(dur)
                dt_str = datetime.fromtimestamp(
                    current_ms / 1000, tz=timezone.utc
                ).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3]
                rows.append((dt_str, int(dur), strap_device_id, SOURCE, PERSON))

        if rows:
            conn.executemany(
                "INSERT OR IGNORE INTO ppi_raw (datetime, pulse_ms, device, source, person) "
                "VALUES (?,?,?,?,?)", rows)
            total += len(rows)

    conn.commit()
    return total


# ── Polar Fitness tests → assessments ─────────────────────────────────────────
def import_polar_fitness(conn: sqlite3.Connection, polar_dir: Path = POLAR_DIR,
                          date_from: str | None = None, date_to: str | None = None) -> int:
    files = sorted(glob.glob(str(polar_dir / "fitness*.json")))
    rows  = []
    for f in files:
        try:
            d = json.load(open(f))
        except Exception:
            continue
        r     = d.get('fitnessTestResult', {})
        start = d.get('startTime', '')
        if not start or not r:
            continue
        date_s = start[:10]
        if not _in_range(date_s, date_from, date_to):
            continue
        details = json.dumps({
            'hr_max':        r.get('maximumHeartRate'),
            'hr_avg':        r.get('averageHeartRate'),
            'fitness_class': r.get('fitnessClass'),
        })
        rows.append((start, date_s, 'polar_fitness_test', r.get('ownIndex'), details, PERSON, SOURCE))
    conn.executemany(
        "INSERT OR IGNORE INTO assessments "
        "(ts, date, instrument, score, details, person, source) "
        "VALUES (?,?,?,?,?,?,?)", rows)
    conn.commit()
    return len(rows)


# ── Polar Night-HRV → polar_nightly_hrv (custom) ─────────────────────────────
def import_polar_nightly_hrv(conn: sqlite3.Connection, polar_dir: Path = POLAR_DIR,
                              date_from: str | None = None, date_to: str | None = None) -> int:
    files = [f for f in sorted(glob.glob(str(polar_dir / "nightly_recovery_*.json")))
             if 'blob' not in f]
    rows = []
    for f in files:
        try:
            entries = json.load(open(f))
        except Exception:
            continue
        for e in entries:
            night = e.get('night')
            if not night or not _in_range(night, date_from, date_to):
                continue
            rows.append((
                night,
                e.get('meanNightlyRecoveryRmssd'),
                e.get('meanNightlyRecoveryRri'),
                e.get('meanNightlyRecoveryRespirationInterval'),
                e.get('recoveryIndicator'),
                e.get('recoveryIndicatorSubLevel'),
                e.get('ansStatus'),
                e.get('ansRate'),
                e.get('meanBaselineRri'),
                e.get('sdBaselineRri'),
                e.get('meanBaselineRmssd'),
                e.get('sdBaselineRmssd'),
                e.get('meanBaselineRespirationInterval'),
                e.get('sdBaselineRespirationInterval'),
            ))
    conn.executemany("""INSERT OR IGNORE INTO polar_nightly_hrv
        (date, rmssd_ms, rri_ms, respiration_ms,
         recovery_indicator, recovery_sublevel, ans_status, ans_rate,
         baseline_rri_ms, baseline_rri_sd, baseline_rmssd_ms, baseline_rmssd_sd,
         baseline_respiration_ms, baseline_respiration_sd)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", rows)
    conn.commit()
    return len(rows)


# ── Polar Night-HRV Zeitreihe → measurements ─────────────────────────────────
def import_polar_nightly_hrv_series(conn: sqlite3.Connection, polar_dir: Path = POLAR_DIR,
                                     date_from: str | None = None, date_to: str | None = None) -> int:
    """startTime in nightly_recovery_blob_*.json ist naive lokale Zeit (kein
    Offset im Export) — wird über resolve_timezone() + ZoneInfo nach UTC
    konvertiert, analog zu import_blue_me.py::_local_to_utc()."""
    files = sorted(glob.glob(str(polar_dir / "nightly_recovery_blob_*.json")))
    tz_name = resolve_timezone(conn, PERSON)
    rows = []
    for f in files:
        try:
            entries = json.load(open(f))
        except Exception:
            continue
        for e in entries:
            for hrv in e.get('hrvData', []):
                start_str = hrv.get('startTime', '')
                if not start_str or not _in_range(start_str[:10], date_from, date_to):
                    continue
                interval_ms = hrv.get('samplingIntervalInMillis', 301000)
                try:
                    start_dt = datetime.fromisoformat(start_str)
                except ValueError:
                    continue
                # Ein Nacht-Slot bleibt an einem Ort — Timezone einmal pro
                # hrvData-Eintrag auflösen statt pro Sample (Performance).
                local_tz = resolve_timezone(conn, PERSON, default=tz_name,
                                             ts=start_dt.strftime('%Y-%m-%dT%H:%M:%S'))
                for i, val in enumerate(hrv.get('samples', [])):
                    if val is None:
                        continue
                    dt_local = start_dt + timedelta(milliseconds=i * interval_ms)
                    dt_utc = dt_local.replace(tzinfo=ZoneInfo(local_tz)).astimezone(ZoneInfo("UTC"))
                    ts = dt_utc.isoformat()
                    date = dt_local.date().isoformat()
                    rows.append((ts, date, 'hrv_rmssd', round(val, 2), None, 'ms', _polar_device_for_date(date), PERSON, SOURCE))
    _meas(conn, rows)
    conn.commit()
    return len(rows)


# ── Polar Sleepdetail + Score → sessions + session_metrics ──────────────────
def import_polar_sleep_detail(conn: sqlite3.Connection, polar_dir: Path = POLAR_DIR,
                               date_from: str | None = None, date_to: str | None = None) -> int:
    files = sorted(glob.glob(str(polar_dir / "sleep_result_*.json")))
    cur   = conn.cursor()
    count = 0
    for f in files:
        try:
            entries = json.load(open(f))
        except Exception:
            continue
        for e in entries:
            night = e.get('night')
            if not night or not _in_range(night, date_from, date_to):
                continue
            sid = f"polar_sleep_{night}"

            # Use actual sleep timestamps from hypnogram if available
            hyp      = e.get('sleepResult', {}).get('hypnogram', {})
            ts_start = hyp.get('sleepStart') or f"{night}T00:00:00+00:00"
            ts_end   = hyp.get('sleepEnd')
            rating   = hyp.get('rating')          # e.g. "SLEPT_WELL"

            cur.execute(
                "INSERT OR IGNORE INTO sessions "
                "(id, type, ts_start, ts_end, date, device_id, person, source_app) "
                "VALUES (?, 'sleep', ?, ?, ?, ?, ?, ?)",
                (sid, ts_start, ts_end, night, _polar_device_for_date(night), PERSON, SOURCE)
            )
            # Update ts_start/ts_end if the row already existed with midnight placeholder
            if ts_start and ts_start != f"{night}T00:00:00+00:00":
                cur.execute(
                    "UPDATE sessions SET ts_start=?, ts_end=? "
                    "WHERE id=? AND ts_start=?",
                    (ts_start, ts_end, sid, f"{night}T00:00:00+00:00")
                )

            ev    = e.get('evaluation', {})
            asleep_s  = parse_duration(ev.get('asleepDuration', ''))
            analysis  = ev.get('analysis', {}) if isinstance(ev.get('analysis'), dict) else {}
            efficiency   = analysis.get('efficiencyPercent')
            continuity   = analysis.get('continuityIndex')
            cont_class   = analysis.get('continuityClass')
            feedback_val = analysis.get('feedback')     # integer code e.g. 1110
            interruptions = ev.get('interruptions', {})
            n_int = interruptions.get('totalCount') if isinstance(interruptions, dict) else None
            phases = ev.get('phaseDurations', {}) or {}

            def phase_min(key):
                s = parse_duration(phases.get(key, '')) if phases else 0
                return s // 60 if s else None

            _metrics(cur, sid, [
                ("total_sleep_min",  asleep_s // 60 if asleep_s else None, None, "min"),
                ("efficiency_pct",   efficiency,     None, "%"),
                ("interruptions_n",  n_int,          None, None),
                ("sleep_type",       None, ev.get('sleepType'), None),
                ("rem_min",          phase_min('rem'),   None, "min"),
                ("deep_min",         phase_min('deep'),  None, "min"),
                ("light_min",        phase_min('light'), None, "min"),
                ("wake_min",         phase_min('wake'),  None, "min"),
                ("rem_pct",          phases.get('remPercentage'),  None, "%"),
                ("deep_pct",         phases.get('deepPercentage'), None, "%"),
                ("continuity_index", continuity,     None, None),
                ("continuity_class", cont_class,     None, None),
                ("sleep_rating",     None,  rating,       None),  # Schlafstatus
                ("sleep_feedback",   feedback_val,   None, None),  # Feedback-Code
            ])
            count += 1
    conn.commit()
    return count


def import_polar_sleep_score(conn: sqlite3.Connection, polar_dir: Path = POLAR_DIR,
                              date_from: str | None = None, date_to: str | None = None) -> int:
    files = sorted(glob.glob(str(polar_dir / "sleep_score_*.json")))
    cur   = conn.cursor()
    count = 0
    for f in files:
        try:
            entries = json.load(open(f))
        except Exception:
            continue
        for e in entries:
            night = e.get('night')
            if not night or not _in_range(night, date_from, date_to):
                continue
            sid = f"polar_sleep_{night}"
            r   = e.get('sleepScoreResult', {})
            _metrics(cur, sid, [
                ("sleep_score",      r.get('sleepScore'),      None, None),
                ("continuity_score", r.get('continuityScore'), None, None),
                ("efficiency_score", r.get('efficiencyScore'), None, None),
                ("rem_score",        r.get('remScore'),        None, None),
                ("deep_score",       r.get('n3Score'),         None, None),
            ])
            count += 1
    conn.commit()
    return count


# ── Polar Sleep-Hypnogramm → polar_sleep_hypnogram (v2) ─────────────────────
def import_polar_sleep_hypnogram(conn: sqlite3.Connection, polar_dir: Path = POLAR_DIR,
                                  date_from: str | None = None, date_to: str | None = None) -> int:
    files = sorted(glob.glob(str(polar_dir / "sleep_result_*.json")))
    rows = []
    for f in files:
        try:
            entries = json.load(open(f))
        except Exception:
            continue
        for e in entries:
            night = e.get('night')
            if not night or not _in_range(night, date_from, date_to):
                continue
            hyp = e.get('sleepResult', {}).get('hypnogram', {})
            sleep_start = hyp.get('sleepStart', '')
            for change in hyp.get('sleepStateChanges', []):
                offset_s = parse_duration(change.get('offsetFromStart', ''))
                state = change.get('state', '')
                if state:
                    rows.append((night, offset_s, state, sleep_start))
    conn.executemany(
        "INSERT OR IGNORE INTO polar_sleep_hypnogram "
        "(date, offset_s, state, sleep_start) VALUES (?,?,?,?)", rows)
    conn.commit()
    return len(rows)


# ── Polar Orthostatic-Tests → sessions + session_metrics ──────────────────────
def import_orthostatic_tests(conn: sqlite3.Connection, polar_dir: Path = POLAR_DIR,
                              date_from: str | None = None, date_to: str | None = None) -> int:
    files = sorted(glob.glob(str(polar_dir / "orthostatic-test-result-*.json")))
    cur   = conn.cursor()
    count = 0
    for f in files:
        try:
            d = json.load(open(f))
        except Exception:
            continue
        r     = d.get('orthostaticTestResult', {})
        start = d.get('startTime', '')
        if not start or not r or not _in_range(start[:10], date_from, date_to):
            continue

        sid      = f"polar_ortho_{start[:19]}"
        ts_start = start
        date_s   = start[:10]

        cur.execute(
            "INSERT OR IGNORE INTO sessions "
            "(id, type, ts_start, ts_end, date, device_id, person, source_app) "
            "VALUES (?, 'orthostatic', ?, NULL, ?, ?, ?, ?)",
            (sid, ts_start, date_s, _polar_device_for_date(date_s), PERSON, SOURCE)
        )

        def rri_to_hr(rri):
            return round(60000 / rri, 1) if rri else None

        hr_sup  = rri_to_hr(r.get('rrAvgSupine'))
        hr_min  = rri_to_hr(r.get('rrMinStandup'))
        hr_std  = rri_to_hr(r.get('rrAvgStand'))
        hr_d    = round(hr_std - hr_sup, 1) if (hr_std and hr_sup) else None
        rms_sup = r.get('rmssdSupine')
        rms_std = r.get('rmssdStand')
        rms_d   = round(rms_std - rms_sup, 1) if (rms_std is not None and rms_sup is not None) else None

        _metrics(cur, sid, [
            ("hr_supine",      hr_sup,  None, "bpm"),
            ("hr_standup_min", hr_min,  None, "bpm"),
            ("hr_stand",       hr_std,  None, "bpm"),
            ("hr_delta",       hr_d,    None, "bpm"),
            ("rmssd_supine",   rms_sup, None, "ms"),
            ("rmssd_stand",    rms_std, None, "ms"),
            ("rmssd_delta",    rms_d,   None, "ms"),
        ])
        count += 1
    conn.commit()
    return count


# ── Polar Generic Periods (Temperatur/SpO2/HRV-Spot) ─────────────────────────
def import_polar_generic_periods(conn: sqlite3.Connection, polar_dir: Path = POLAR_DIR,
                                  date_from: str | None = None, date_to: str | None = None):
    files = sorted(glob.glob(str(polar_dir / "generic-period*.json")))
    temp_rows = []
    spo2_rows = []
    spot_rows = []
    for f in files:
        try:
            d = json.load(open(f))
        except Exception:
            continue
        meta = d.get('meta', {})
        t    = meta.get('type')
        data = d.get('data', {})

        if t == 7:  # Hauttemperatur
            start_s    = int(meta['id']['startTimeSeconds'])
            file_date  = datetime.fromtimestamp(start_s, tz=timezone.utc).strftime('%Y-%m-%d')
            if not _in_range(file_date, date_from, date_to):
                continue
            sensor_loc = data.get('sensorLocation', '') or 'wrist'
            current_ms = start_s * 1000
            for s in data.get('temperatureMeasurementSamples', []):
                current_ms += int(s.get('recordingTimeDeltaMilliseconds', 0))
                temp = s.get('temperatureCelsius')
                if temp is not None:
                    dt = datetime.fromtimestamp(current_ms / 1000, tz=timezone.utc)
                    ts = dt.strftime('%Y-%m-%dT%H:%M:%S+00:00')
                    temp_rows.append((ts, ts[:10], 'skin_temperature', round(temp, 4), None, '°C',
                                      f'polar_{sensor_loc}', PERSON, SOURCE))

        elif t == 10:  # HRV-Spot + Pulse Arrival Time (Vantage V3)
            start_s = int(meta['id']['startTimeSeconds'])
            dt = datetime.fromtimestamp(start_s, tz=timezone.utc)
            ts = dt.strftime('%Y-%m-%dT%H:%M:%S+00:00')
            if not _in_range(ts[:10], date_from, date_to):
                continue
            hrv = data.get('heartRateVariabilityMs')
            spot_rows.append((
                ts,
                data.get('sourceDeviceId'),
                data.get('averageHeartRateBpm'),
                round(hrv, 4) if hrv is not None else None,
                data.get('heartRateVariabilityLevel'),
                data.get('rriMs'),
                data.get('pulseArrivalTimeAtContractionMs'),
                data.get('pulseArrivalTimeAtRelaxationMs'),
                data.get('pulseTransitTimeQualityIndex'),
            ))

        elif t == 11:  # SpO2
            test_ms = int(data.get('testTime', 0))
            dt = datetime.fromtimestamp(test_ms / 1000, tz=timezone.utc)
            ts = dt.strftime('%Y-%m-%dT%H:%M:%S+00:00')
            if not _in_range(ts[:10], date_from, date_to):
                continue
            hrv = data.get('heartRateVariabilityMs')
            spo2 = data.get('bloodOxygenPercent')
            hr   = data.get('averageHeartRateBpm')
            if spo2 is not None:
                spo2_rows.append((ts, ts[:10], 'spo2', float(spo2), None, '%',
                                  DEVICE_V3, PERSON, SOURCE))
            if hr is not None:
                spo2_rows.append((ts, ts[:10], 'heart_rate', float(hr), None, 'bpm',
                                  DEVICE_V3, PERSON, SOURCE))
            if hrv is not None:
                spo2_rows.append((ts, ts[:10], 'hrv_rmssd', round(hrv, 2), None, 'ms',
                                  DEVICE_V3, PERSON, SOURCE))

    _meas(conn, temp_rows)
    _meas(conn, spo2_rows)
    conn.executemany(
        "INSERT OR IGNORE INTO polar_hrv_spot "
        "(datetime, device, hr_bpm, hrv_ms, hrv_level, rri_ms, "
        "ptt_contract_ms, ptt_relax_ms, ptt_quality) VALUES (?,?,?,?,?,?,?,?,?)",
        spot_rows)
    conn.commit()
    return len(temp_rows), len(spo2_rows), len(spot_rows)


# ── Polar Sleep Wake → polar_sleep_wake (v2) ─────────────────────────────────
def import_polar_sleep_wake(conn: sqlite3.Connection, polar_dir: Path = POLAR_DIR,
                             person: str = PERSON,
                             date_from: str | None = None, date_to: str | None = None) -> int:
    files = sorted(glob.glob(str(polar_dir / "sleep_wake_*.json")))
    rows = []
    for f in files:
        try:
            entries = json.load(open(f))
        except Exception:
            continue
        for e in entries:
            night = e.get('night')
            if not night or not _in_range(night, date_from, date_to):
                continue
            for sw in e.get('sleepWake', []):
                device = sw.get('deviceId', '')
                for change in sw.get('sleepStateChanges', {}).get('sleepWakeStateChangeModels', []):
                    ms    = change.get('millisInDay')
                    state = change.get('state', '')
                    if ms is not None and state:
                        rows.append((night, device, ms, state, person))
    # Bestehende Zeilen aus der Zeit vor dieser person-Parametrisierung zuerst
    # nachziehen — muss vor dem INSERT laufen, sonst kollidiert ein frisch
    # eingefuegter Datenpunkt mit demselben (date, millis_in_day) fuer die
    # echte Person mit der spaeteren Migration der alten 'unknown'-Zeile
    # (PRIMARY KEY (date, millis_in_day, person)).
    conn.execute("UPDATE polar_sleep_wake SET person = ? WHERE person = 'unknown'", (person,))
    conn.executemany(
        "INSERT OR IGNORE INTO polar_sleep_wake (date, device, millis_in_day, state, person) "
        "VALUES (?,?,?,?,?)", rows)
    conn.commit()
    return len(rows)


# ── Polar Skin Contact → polar_skin_contact (custom) ─────────────────────────
def import_polar_skin_contact(conn: sqlite3.Connection, polar_dir: Path = POLAR_DIR,
                               date_from: str | None = None, date_to: str | None = None) -> int:
    files = sorted(glob.glob(str(polar_dir / "generic-period*.json")))
    rows = []
    for f in files:
        try:
            d = json.load(open(f))
        except Exception:
            continue
        if d.get('meta', {}).get('type') != 8:
            continue
        meta = d['meta']
        data = d.get('data', {})
        device  = data.get('sourceDeviceId', '')
        start_s = int(meta['id']['startTimeSeconds'])
        file_date = datetime.fromtimestamp(start_s, tz=timezone.utc).strftime('%Y-%m-%d')
        if not _in_range(file_date, date_from, date_to):
            continue
        current_ms = start_s * 1000
        for s in data.get('skinContactChanges', []):
            current_ms += int(s.get('recordingTimeDeltaMilliseconds', 0))
            contact = 1 if s.get('skinContact') else 0
            dt = datetime.fromtimestamp(current_ms / 1000, tz=timezone.utc)
            rows.append((dt.strftime('%Y-%m-%dT%H:%M:%S+00:00'), device, contact))
    conn.executemany(
        "INSERT OR IGNORE INTO polar_skin_contact (datetime, device, contact) VALUES (?,?,?)",
        rows)
    conn.commit()
    return len(rows)


# ── Hauptprogramm ─────────────────────────────────────────────────────────────
def main():
    """
    Hauptfunktion: Koordiniert den Import aller Polar-Daten.

    Command-Line-Argumente:
        --update: Nur neue Daten ergänzen
        --from: Startdatum (YYYY-MM-DD)
        --to: Enddatum (YYYY-MM-DD)
        --polar-dir: Polar-Datenverzeichnis
    """
    import argparse
    parser = argparse.ArgumentParser(description=t("Polar GDPR Export → health.db", "Polar GDPR Export → health.db"))
    parser.add_argument("--update",    action="store_true", help="Nur neue Daten ergänzen")
    parser.add_argument("--from",      dest="date_from", metavar="DATE")
    parser.add_argument("--to",        dest="date_to",   metavar="DATE")
    parser.add_argument("--polar-dir", metavar="DIR",    default=None,
                        help=f"Polar-Datenverzeichnis (Standard: {POLAR_DIR})")
    parser.add_argument("--archive", action="store_true",
                        help=t("Roh-JSON-Dateien nach erfolgreichem Import nach originals/ verschieben "
                               "(enthalten u.a. Geburtsdatum/Gewicht in physicalInformation) — Standard: aus",
                               "Move raw JSON files to originals/ after successful import "
                               "(contain e.g. birthdate/weight in physicalInformation) — default: off"))
    add_lang_arg(parser)

    args = parser.parse_args()
    apply_lang_from_args(args)

    polar_dir = Path(args.polar_dir) if args.polar_dir else POLAR_DIR

    conn = open_db()
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    setup_db(conn)

    # date_from bestimmen: --from hat Vorrang, dann --update (letztes Datum + 1 Tag),
    # sonst None (kompletter Bestand, unverändertes altes Verhalten). Vorher waren
    # --update/--from/--to reine No-op-Flags — jede Datei wurde bei jedem Lauf
    # komplett neu geparst. Jetzt wirklich wirksam, analog zu import_apple.py.
    date_from = args.date_from or None
    if not date_from and args.update:
        last = _get_last_import(conn)
        if last:
            date_from = (datetime.strptime(last, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
    date_to = args.date_to or None
    if date_from:
        print(t(f"Zeitraum: {date_from} → {date_to or 'heute'}",
                f"Period: {date_from} → {date_to or 'today'}"))

    failed_steps: list[str] = []

    print(t("\n── Polar-Daten ────────────────────────────────────────", "\n── Polar data ─────────────────────────────────────────"))
    for label, fn in [
        ("Trainingseinheiten",        lambda: import_polar_trainings(conn, polar_dir, date_from, date_to)),
        ("Tagesaktivität",            lambda: import_polar_activity(conn, polar_dir, date_from, date_to)),
        ("24/7-Herzfrequenz",         lambda: import_polar_247hr(conn, polar_dir, date_from, date_to)),
        ("PPI / HRV-Rohdaten",        lambda: import_polar_ppi(conn, polar_dir, date_from, date_to)),
        ("H7 RR aus Trainings",       lambda: import_polar_rr_samples(conn, polar_dir, date_from, date_to)),
        ("Fitnesstests",              lambda: import_polar_fitness(conn, polar_dir, date_from, date_to)),
        ("Nächtliche HRV (Gesamt)",   lambda: import_polar_nightly_hrv(conn, polar_dir, date_from, date_to)),
        ("Nächtliche HRV-Zeitreihe",  lambda: import_polar_nightly_hrv_series(conn, polar_dir, date_from, date_to)),
        ("Schlafdetail",              lambda: import_polar_sleep_detail(conn, polar_dir, date_from, date_to)),
        ("Schlaf-Score",              lambda: import_polar_sleep_score(conn, polar_dir, date_from, date_to)),
        ("Schlaf-Hypnogramm",         lambda: import_polar_sleep_hypnogram(conn, polar_dir, date_from, date_to)),
        ("Orthostase-Tests",          lambda: import_orthostatic_tests(conn, polar_dir, date_from, date_to)),
        ("Sleep-Wake (binär)",        lambda: import_polar_sleep_wake(conn, polar_dir, PERSON, date_from, date_to)),
        ("Hautkontakt-Events",        lambda: import_polar_skin_contact(conn, polar_dir, date_from, date_to)),
    ]:
        print(f"  {label} ...", end=" ", flush=True)
        try:
            n = fn()
            print(f"{n:,}")
        except Exception as e:
            print(t(f"Fehler: {e}", f"Error: {e}"))
            failed_steps.append(label)

    print(t("  Temperatur + SpO2 + HRV-Spot ...", "  Temperature + SpO2 + HRV-spot ..."), end=" ", flush=True)
    try:
        nt, ns, nh = import_polar_generic_periods(conn, polar_dir, date_from, date_to)
        print(f"Temp:{nt:,} SpO2:{ns} HRV-Spot:{nh}")
    except Exception as e:
        print(f"Fehler: {e}")
        failed_steps.append(t("Temperatur + SpO2 + HRV-Spot", "Temperature + SpO2 + HRV-spot"))

    print(t("  Sport-Typ Backfill ...", "  Sport-type backfill ..."), end=" ", flush=True)
    try:
        nb = backfill_polar_sport(conn)
        print(t(f"{nb} aktualisiert", f"{nb} updated"))
    except Exception as e:
        print(t(f"Fehler: {e}", f"Error: {e}"))

    print(t("  Training-Load Backfill (cardioLoad 2024+) ...",
            "  Training-load backfill (cardioLoad 2024+) ..."), end=" ", flush=True)
    try:
        nl = backfill_training_load(conn, polar_dir)
        print(t(f"{nl} ergänzt", f"{nl} filled"))
    except Exception as e:
        print(t(f"Fehler: {e}", f"Error: {e}"))

    print(t("  Muscle-Load Backfill (2024+) ...",
            "  Muscle-load backfill (2024+) ..."), end=" ", flush=True)
    try:
        nm = backfill_muscle_load(conn, polar_dir)
        print(t(f"{nm} ergänzt", f"{nm} filled"))
    except Exception as e:
        print(t(f"Fehler: {e}", f"Error: {e}"))

    print(t("\n── Übersicht ────────────────────────────────────────────", "\n── Overview ─────────────────────────────────────────────"))
    checks = [
        ("sessions (training)",   "SELECT COUNT(*), MIN(date), MAX(date) FROM sessions WHERE type='training' AND source_app=?", SOURCE),
        ("sessions (sleep)",      "SELECT COUNT(*), MIN(date), MAX(date) FROM sessions WHERE type='sleep' AND source_app=?", SOURCE),
        ("sessions (orthostatic)","SELECT COUNT(*), MIN(date), MAX(date) FROM sessions WHERE type='orthostatic' AND source_app=?", SOURCE),
        ("ppi_raw (H10/H7)",      "SELECT COUNT(*), MIN(datetime), MAX(datetime) FROM ppi_raw WHERE source=?", SOURCE),
        ("measurements",          "SELECT COUNT(*), MIN(date), MAX(date) FROM measurements WHERE source_app=?", SOURCE),
        ("polar_nightly_hrv",     "SELECT COUNT(*), MIN(date), MAX(date) FROM polar_nightly_hrv", None),
        ("polar_sleep_hypnogram", "SELECT COUNT(*), MIN(date), MAX(date) FROM polar_sleep_hypnogram", None),
        ("polar_sleep_wake",      "SELECT COUNT(*), MIN(date), MAX(date) FROM polar_sleep_wake", None),
        ("assessments",           "SELECT COUNT(*), MIN(date), MAX(date) FROM assessments WHERE source=?", SOURCE),
    ]
    for label, sql, param in checks:
        try:
            r = conn.execute(sql, (param,) if param else ()).fetchone()
            if r[0]:
                print(f"  {label:<28} {r[0]:>8,}  {r[1]} → {r[2]}")
        except Exception:
            pass

    log_import(conn, 'polar', str(POLAR_DIR), 0)
    conn.commit()
    conn.close()
    size = DB_PATH.stat().st_size / 1e6
    print(t(f"\nDatenbank: {DB_PATH} ({size:.0f} MB)", f"\nDatabase: {DB_PATH} ({size:.0f} MB)"))

    if args.archive:
        if date_from or date_to:
            # Nur bei vollem Bestand archivieren: --archive verschiebt ALLE
            # *.json-Dateien im Verzeichnis, unabhängig davon, ob sie durch
            # --update/--from/--to gerade tatsächlich verarbeitet wurden. Bei
            # aktivem Datumsfilter könnte das eine Datei archivieren, die
            # übersprungen und nie erfolgreich importiert wurde.
            print(t("  – Archivierung übersprungen: --update/--from/--to aktiv "
                    "(Archivierung nur bei vollem Bestand, sonst könnten "
                    "übersprungene, nie importierte Dateien mit verschoben werden)",
                    "  – Archiving skipped: --update/--from/--to active "
                    "(archiving only runs on a full pass, otherwise skipped, "
                    "never-imported files could get moved along)"))
        else:
            n = _archive_raw_files(polar_dir)
            print(t(f"{n} Rohdatei(en) nach {polar_dir / 'originals'} verschoben",
                    f"{n} raw file(s) moved to {polar_dir / 'originals'}"))

    if failed_steps:
        print(t(f"\n⚠ {len(failed_steps)} Schritt(e) fehlgeschlagen: {', '.join(failed_steps)}",
                f"\n⚠ {len(failed_steps)} step(s) failed: {', '.join(failed_steps)}"), file=_sys.stderr)
        _sys.exit(1)


def _archive_raw_files(polar_dir: Path) -> int:
    """Verschiebt alle *.json-Rohdateien nach polar_dir/originals/.

    Enthalten u.a. physicalInformation (Geburtsdatum, Gewicht, ...) im Klartext
    — sollen nicht unbegrenzt im aktiven Import-Verzeichnis liegen bleiben.
    Läuft erst ganz am Ende von main(), nachdem ALLE Import-Funktionen (die
    teils dieselben Dateimuster mehrfach lesen, z.B. generic-period*.json)
    durchgelaufen sind — verschieben mitten im Ablauf würde spätere Lesezugriffe
    auf bereits verschobene Dateien brechen.
    """
    import shutil
    originals_dir = polar_dir / "originals"
    originals_dir.mkdir(parents=True, exist_ok=True)
    moved = 0
    for f in polar_dir.glob("*.json"):
        dst = originals_dir / f.name
        if dst.exists():
            continue
        shutil.move(str(f), str(dst))
        moved += 1
    return moved


if __name__ == "__main__":
    main()
