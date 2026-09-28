#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Bearable CSV-Export → health.db

@tier        infrastructure
@purpose.de  Importiert umfassende Gesundheits- und Lebensstildaten aus Bearable
             CSV-Exporten in die health.db. Unterstützt Schlaf, Gesundheitsmessungen,
             Symptome, Stimmung, Energie, Müdigkeit, Schmerz, Ängste, Stress, Fokus,
             Übelkeit, Lebensstilfaktoren, Medikamente und Notizen.
@purpose.en  Imports comprehensive health and lifestyle data from Bearable CSV
             exports into health.db. Supports sleep, health measurements,
             symptoms, mood, energy, fatigue, pain, anxiety, stress, focus,
             nausea, lifestyle factors, medications, and notes.
@method.de   Liest CSV-Dateien aus imports/bearable/ oder einem expliziten Pfad.
             CSV-Format: 8 Spalten (Datum, formatiertes Datum, Wochentag, Tageszeit,
             Kategorie, Bewertung/Menge, Detail, Notizen). Mapping: Sleep →
             sessions + session_metrics, Health measurements → measurements,
             Symptoms → symptoms, Mood/Energy/etc. → measurements (<name>_score),
             Factors → bearable_factors, Medications → medications,
             Notes → bearable_notes.
@method.en   Reads CSV files from imports/bearable/ or an explicit path.
             CSV format: 8 columns (date, formatted date, weekday, time of day,
             category, rating/amount, detail, notes). Mapping: Sleep →
             sessions + session_metrics, Health measurements → measurements,
             Symptoms → symptoms, Mood/Energy/etc. → measurements (<name>_score),
             Factors → bearable_factors, Medications → medications,
             Notes → bearable_notes.
@reads       {imports/bearable/}*.csv (Bearable Export)
@writes      health.db (sessions, session_metrics, measurements, symptoms,
             bearable_factors, medications, bearable_notes, bearable_custom)
@limits.de   Keine Validierung der Bearable-Datenqualität. Keine medizinische
             Bewertung aus den Daten. Graceful Fallback für unbekannte Kategorien.
             run()/import_file() reichten person schon vorher korrekt durch;
             main() hatte aber kein --person-Flag (fest auf OWN_PERSON_ID) — jetzt
             ergaenzt.

@relevance.de  Ermöglicht den Import von Gesundheitsdaten, essentiell für die umfassende Datenanalyse
@relevance.en  Enables import of health data, essential for comprehensive data analysis
@limits.en   No validation of Bearable data quality. No medical evaluation from
             the data. Graceful fallback for unknown categories.
             run()/import_file() already threaded person through correctly, but
             main() had no --person flag (hardcoded to OWN_PERSON_ID) — now added.
@usage
    python3 import_bearable.py                  # alle CSVs in imports/bearable/
    python3 import_bearable.py --file path.csv  # einzelne Datei
    python3 import_bearable.py --rebuild        # bearable-Einträge löschen + neu
    python3 import_bearable.py --dry-run
    python3 import_bearable.py --update         # nur neue Einträge
    python3 import_bearable.py --person PER-xxxxxxxx
"""

import argparse
import csv
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).parent.parent))
from health_config import Config as _Cfg, OWN_PERSON_ID
from modules.db import open_db
from modules.base import ImportResult, resolve_timezone, log_import, resolve_person
from modules.i18n import t, add_lang_arg, apply_lang_from_args

_cfg    = _Cfg()
CSV_DIR = _cfg.data_root / "bearable"
CSV_DIR.mkdir(parents=True, exist_ok=True)

SOURCE = "bearable"
_DEV   = "bearable_app"

# ── Schema ────────────────────────────────────────────────────────────────────

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS bearable_factors (
    date        TEXT NOT NULL,
    factor      TEXT NOT NULL,
    sub_category TEXT,
    amount      REAL,
    amount_text TEXT,
    time_of_day TEXT,
    notes       TEXT,
    person      TEXT NOT NULL,
    PRIMARY KEY (date, factor, person)
);

CREATE TABLE IF NOT EXISTS bearable_notes (
    date        TEXT NOT NULL,
    time_of_day TEXT,
    content     TEXT NOT NULL,
    category    TEXT,
    person      TEXT NOT NULL,
    PRIMARY KEY (date, person, content)
);

CREATE TABLE IF NOT EXISTS bearable_custom (
    date        TEXT NOT NULL,
    category    TEXT NOT NULL,
    detail      TEXT,
    amount      TEXT,
    time_of_day TEXT,
    notes       TEXT,
    person      TEXT NOT NULL,
    PRIMARY KEY (date, category, detail, person)
);
"""


def _ensure_schema(conn) -> None:
    for stmt in _SCHEMA_SQL.strip().split(";"):
        s = stmt.strip()
        if s:
            conn.execute(s)
    conn.commit()


# ── Hilfsfunktionen ───────────────────────────────────────────────────────────

def _local_tz(conn, person: str) -> ZoneInfo:
    tz_name = resolve_timezone(conn, person)
    try:
        return ZoneInfo(tz_name)
    except Exception:
        return ZoneInfo("UTC")


def _to_utc(dt_local: datetime) -> str:
    return dt_local.astimezone(timezone.utc).isoformat()


def _parse_hhmm(s: str) -> tuple[int, int] | None:
    m = re.match(r"(\d{1,2}):(\d{2})", s.strip())
    if not m:
        return None
    return int(m.group(1)), int(m.group(2))


def _local_dt(date_str: str, hhmm: tuple[int, int], tz: ZoneInfo) -> datetime:
    from datetime import date as _d
    d = _d.fromisoformat(date_str)
    return datetime(d.year, d.month, d.day, hhmm[0], hhmm[1], tzinfo=tz)


def _safe_float(s: str) -> float | None:
    try:
        return float(s.strip()) if s.strip() else None
    except ValueError:
        return None


_TOD_HOURS = {
    "morning": 8, "afternoon": 14, "evening": 19,
    "night": 23, "late night": 2,
}


def _ts_from_date_tod(date_str: str, time_of_day: str, tz: ZoneInfo) -> str:
    h = _TOD_HOURS.get(time_of_day.lower().strip(), 0)
    hhmm = (h, 0)
    return _to_utc(_local_dt(date_str, hhmm, tz))


def _daily_ts(date_str: str, tz: ZoneInfo) -> str:
    return _ts_from_date_tod(date_str, "", tz)


# ── Sleep-Parser ──────────────────────────────────────────────────────────────

# "Asleep HH:MM - HH:MM. In bed HH:MM - HH:MM"
# "Asleep HH:MM - HH:MM"
_SLEEP_RE  = re.compile(
    r"Asleep\s+(\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2})"
    r"(?:\.?\s*In bed\s+(\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2}))?",
    re.IGNORECASE,
)
# "H:MM" or "HH:MM" duration
_DUR_RE = re.compile(r"^(\d+):(\d{2})$")


def _parse_duration(s: str) -> float | None:
    m = _DUR_RE.match(s.strip())
    if not m:
        return None
    return int(m.group(1)) + int(m.group(2)) / 60


def _sleep_dates(sleep_hhmm: tuple[int, int], wake_hhmm: tuple[int, int],
                 entry_date: str, tz: ZoneInfo) -> tuple[datetime, datetime]:
    """Berechnet sleep_start und sleep_end als UTC-Datetimes."""
    from datetime import date as _d, timedelta as _td
    d = _d.fromisoformat(entry_date)

    wake_dt = datetime(d.year, d.month, d.day, wake_hhmm[0], wake_hhmm[1], tzinfo=tz)

    # Einschlafen >= 12 Uhr: vorheriger Kalendertag
    if sleep_hhmm[0] >= 12:
        sleep_d = d - _td(days=1)
    else:
        sleep_d = d
    sleep_dt = datetime(sleep_d.year, sleep_d.month, sleep_d.day,
                        sleep_hhmm[0], sleep_hhmm[1], tzinfo=tz)

    # Sanity: wake muss nach sleep liegen
    if wake_dt <= sleep_dt:
        wake_dt += _td(days=1)

    return sleep_dt, wake_dt


def _handle_sleep(conn, row: dict, person: str, tz: ZoneInfo,
                  dry: bool, result: ImportResult) -> None:
    date_str    = row["date formatted"].strip()
    detail_text = row["detail"].strip()
    duration_s  = row["rating/amount"].strip()

    m = _SLEEP_RE.search(detail_text)
    if not m:
        result.rows_skipped += 1
        return

    sleep_hhmm = _parse_hhmm(m.group(1))
    wake_hhmm  = _parse_hhmm(m.group(2))
    inbed_start = _parse_hhmm(m.group(3)) if m.group(3) else None
    inbed_end   = _parse_hhmm(m.group(4)) if m.group(4) else None

    if not sleep_hhmm or not wake_hhmm:
        result.rows_skipped += 1
        return

    sleep_dt, wake_dt = _sleep_dates(sleep_hhmm, wake_hhmm, date_str, tz)
    ts_start = _to_utc(sleep_dt)
    ts_end   = _to_utc(wake_dt)
    duration = _parse_duration(duration_s)
    if duration is None:
        delta = wake_dt - sleep_dt
        duration = delta.total_seconds() / 3600

    session_id = f"bearable_sleep_{date_str}"

    if dry:
        result.rows_inserted += 1
        return

    conn.execute("""
        INSERT OR IGNORE INTO sessions
        (id, type, ts_start, ts_end, date, device_id, person, source_app)
        VALUES (?,?,?,?,?,?,?,?)
    """, (session_id, "sleep", ts_start, ts_end, date_str, _DEV, person, SOURCE))

    metrics: list[tuple] = [
        (session_id, "sleep_duration_h",    duration,   None, "h"),
        (session_id, "sleep_start_local",   None, f"{sleep_hhmm[0]:02d}:{sleep_hhmm[1]:02d}", None),
        (session_id, "sleep_end_local",     None, f"{wake_hhmm[0]:02d}:{wake_hhmm[1]:02d}",   None),
    ]
    if inbed_start:
        inbed_s_dt, inbed_e_dt = _sleep_dates(inbed_start, inbed_end or wake_hhmm,
                                               date_str, tz)
        inbed_h = (inbed_e_dt - inbed_s_dt).total_seconds() / 3600
        efficiency = round(duration / inbed_h * 100, 1) if inbed_h > 0 else None
        metrics += [
            (session_id, "inbed_start_local",   None,
             f"{inbed_start[0]:02d}:{inbed_start[1]:02d}", None),
            (session_id, "inbed_end_local",     None,
             f"{inbed_end[0]:02d}:{inbed_end[1]:02d}" if inbed_end else None, None),
            (session_id, "inbed_duration_h",    inbed_h, None, "h"),
            (session_id, "sleep_efficiency_pct", efficiency, None, "%"),
        ]
    conn.executemany("""
        INSERT OR IGNORE INTO session_metrics
        (session_id, metric, value, value_text, unit) VALUES (?,?,?,?,?)
    """, metrics)
    result.rows_inserted += 1


# ── Health-Measurements-Parser ────────────────────────────────────────────────

# Normalisierung: Detail-String → (metric_base, unit)
def _parse_detail_unit(detail: str) -> tuple[str, str | None]:
    """'Heart rate (bpm)' → ('heart rate', 'bpm')"""
    m = re.match(r"^(.+?)\s*\(([^)]+)\)\s*$", detail.strip())
    if m:
        return m.group(1).strip().lower(), m.group(2).strip()
    return detail.strip().lower(), None

# Direkte Metrik-Übersetzungen (Bearable-Name → DB-metric, bevorzugte Unit)
_MEAS_DIRECT: dict[str, tuple[str, str | None]] = {
    "step count":         ("steps",               "steps"),
    "weight":             ("body_weight",          "kg"),
    "blood oxygen":       ("spo2",                 "%"),
    "respiratory rate":   ("resp_rate",            "bpm"),
    "temperature":        ("body_temp_c",          "°C"),
    "hrv":                ("hrv_rmssd",            "ms"),
    "calories burned":    ("calories_active",      "kcal"),
    "distance":           ("distance_km",          "km"),
    "floors climbed":     ("floors_climbed",       None),
    "active minutes":     ("active_minutes",       "min"),
    "resting heart rate": ("hr_resting",           "bpm"),
    "sleep score":        ("sleep_score",          None),
    "mindfulness minutes":("mindfulness_minutes",  "min"),
    "stand hours":        ("stand_hours",          "h"),
    "vo2 max":            ("vo2_max",              "ml/kg/min"),
    "body fat":           ("body_fat_pct",         "%"),
    "bmi":                ("bmi",                  "kg/m²"),
    "menstrual flow":     ("menstrual_flow",       None),
}


def _handle_health_meas(conn, row: dict, person: str, tz: ZoneInfo,
                        dry: bool, result: ImportResult) -> None:
    date_str    = row["date formatted"].strip()
    detail_raw  = row["detail"].strip()
    amount_raw  = row["rating/amount"].strip()
    tod         = row.get("time of day", "").strip()
    ts          = _ts_from_date_tod(date_str, tod, tz)

    name, raw_unit = _parse_detail_unit(detail_raw)

    def _insert(metric: str, value: float, unit: str | None) -> None:
        if dry:
            return
        conn.execute("""
            INSERT OR IGNORE INTO measurements
            (ts, date, metric, value, unit, device_id, person, source_app)
            VALUES (?,?,?,?,?,?,?,?)
        """, (ts, date_str, metric, value, unit, _DEV, person, SOURCE))

    # Heart rate: "min/avg/max" oder einfach eine Zahl
    if name == "heart rate":
        parts = amount_raw.split("/")
        if len(parts) == 3:
            for metric, val_s in (
                ("hr_min", parts[0]),
                ("hr_avg", parts[1]),
                ("hr_max", parts[2]),
            ):
                v = _safe_float(val_s)
                if v is not None:
                    _insert(metric, v, "bpm")
                    if not dry:
                        result.rows_inserted += 1
        else:
            v = _safe_float(amount_raw)
            if v is not None:
                _insert("hr_avg", v, "bpm")
                if not dry:
                    result.rows_inserted += 1
        return

    # Blutdruck: "systolic/diastolic"
    if name in ("blood pressure", "bp"):
        parts = amount_raw.split("/")
        if len(parts) >= 2:
            sys_v = _safe_float(parts[0])
            dia_v = _safe_float(parts[1])
            if sys_v is not None:
                _insert("bp_systolic",  sys_v, "mmHg")
                if not dry: result.rows_inserted += 1
            if dia_v is not None:
                _insert("bp_diastolic", dia_v, "mmHg")
                if not dry: result.rows_inserted += 1
        return

    # Temperatur: °F → °C
    if name == "temperature":
        v = _safe_float(amount_raw)
        if v is not None:
            unit = raw_unit or "°C"
            if "f" in unit.lower():
                v = round((v - 32) * 5 / 9, 2)
                unit = "°C"
            _insert("body_temp_c", v, "°C")
            if not dry: result.rows_inserted += 1
        return

    # Blutzucker: mg/dL → mmol/L
    if name == "blood glucose":
        v = _safe_float(amount_raw)
        if v is not None:
            unit = raw_unit or "mmol/L"
            if "mg" in unit.lower():
                v = round(v / 18.0182, 2)
                unit = "mmol/L"
            _insert("blood_glucose_mmol", v, "mmol/L")
            if not dry: result.rows_inserted += 1
        return

    # Direkte 1:1 Metriken
    if name in _MEAS_DIRECT:
        metric, pref_unit = _MEAS_DIRECT[name]
        v = _safe_float(amount_raw)
        if v is not None:
            _insert(metric, v, pref_unit or raw_unit)
            if not dry: result.rows_inserted += 1
        return

    # Unbekannte Health Measurement: generisch ablegen
    v = _safe_float(amount_raw)
    if v is not None:
        sanitized = re.sub(r"[^a-z0-9_]", "_", name).strip("_")
        _insert(f"bearable_{sanitized}", v, raw_unit)
        if not dry: result.rows_inserted += 1
    else:
        result.rows_skipped += 1


# ── Score-Kategorien (Mood, Energy, …) ───────────────────────────────────────

_SCORE_CATS = {
    "mood":      "mood_score",
    "energy":    "energy_score",
    "fatigue":   "fatigue_score",
    "pain":      "pain_score",
    "anxiety":   "anxiety_score",
    "stress":    "stress_score",
    "focus":     "focus_score",
    "nausea":    "nausea_score",
    "dizziness": "dizziness_score",
    "appetite":  "appetite_score",
    "cognition": "cognition_score",
    "motivation":"motivation_score",
    "headache":  "headache_score",
    "brain fog": "brain_fog_score",
}


def _handle_score(conn, row: dict, person: str, tz: ZoneInfo,
                  category: str, dry: bool, result: ImportResult) -> None:
    date_str   = row["date formatted"].strip()
    amount_raw = row["rating/amount"].strip()
    tod        = row.get("time of day", "").strip()
    ts         = _ts_from_date_tod(date_str, tod, tz)
    metric     = _SCORE_CATS.get(category.lower(), f"{category.lower()}_score")

    v = _safe_float(amount_raw)
    if v is None:
        result.rows_skipped += 1
        return

    if dry:
        result.rows_inserted += 1
        return

    conn.execute("""
        INSERT OR IGNORE INTO measurements
        (ts, date, metric, value, unit, device_id, person, source_app)
        VALUES (?,?,?,?,NULL,?,?,?)
    """, (ts, date_str, metric, v, _DEV, person, SOURCE))
    result.rows_inserted += 1


# ── Symptome ──────────────────────────────────────────────────────────────────

def _handle_symptom(conn, row: dict, person: str,
                    dry: bool, result: ImportResult) -> None:
    date_str   = row["date formatted"].strip()
    symptom    = row["detail"].strip()
    amount_raw = row["rating/amount"].strip()

    if not symptom:
        result.rows_skipped += 1
        return

    v = _safe_float(amount_raw)
    value_text = amount_raw if v is None and amount_raw else None

    if dry:
        result.rows_inserted += 1
        return

    conn.execute("""
        INSERT OR IGNORE INTO symptoms
        (date, symptom, value_num, value_text, category, person, source)
        VALUES (?,?,?,?,'bearable',?,?)
    """, (date_str, symptom, v, value_text, person, SOURCE))
    result.rows_inserted += 1


# ── Faktoren ──────────────────────────────────────────────────────────────────

def _handle_factor(conn, row: dict, person: str, category: str,
                   dry: bool, result: ImportResult) -> None:
    date_str   = row["date formatted"].strip()
    detail     = row["detail"].strip()
    amount_raw = row["rating/amount"].strip()
    tod        = row.get("time of day", "").strip() or None
    notes      = row.get("notes", "").strip() or None

    factor = detail or category
    # Sub-Kategorie aus "Factors - Food" extrahieren
    sub = None
    if " - " in category:
        sub = category.split(" - ", 1)[1].strip()
    elif " - " in (detail or ""):
        parts = detail.split(" - ", 1)
        sub, factor = parts[0].strip(), parts[1].strip()

    v = _safe_float(amount_raw)
    v_text = amount_raw if v is None and amount_raw else None

    if dry:
        result.rows_inserted += 1
        return

    conn.execute("""
        INSERT OR IGNORE INTO bearable_factors
        (date, factor, sub_category, amount, amount_text, time_of_day, notes, person)
        VALUES (?,?,?,?,?,?,?,?)
    """, (date_str, factor, sub, v, v_text, tod, notes, person))
    result.rows_inserted += 1


# ── Medikamente ───────────────────────────────────────────────────────────────

def _handle_medication(conn, row: dict, person: str, tz: ZoneInfo,
                        dry: bool, result: ImportResult) -> None:
    date_str   = row["date formatted"].strip()
    drug_name  = row["detail"].strip()
    amount_raw = row["rating/amount"].strip()
    tod        = row.get("time of day", "").strip()
    notes      = row.get("notes", "").strip() or None
    ts         = _ts_from_date_tod(date_str, tod, tz)

    if not drug_name:
        result.rows_skipped += 1
        return

    # Dosis: "10 mg" → value=10, unit="mg"
    dose_v, dose_u = None, None
    dm = re.match(r"([\d.]+)\s*(\w+)?", amount_raw)
    if dm:
        dose_v = _safe_float(dm.group(1))
        dose_u = dm.group(2) if dm.group(2) else None

    if dry:
        result.rows_inserted += 1
        return

    conn.execute("""
        INSERT OR IGNORE INTO medications
        (ts, date, drug_name, dose_value, dose_unit, notes, person, source)
        VALUES (?,?,?,?,?,?,?,?)
    """, (ts, date_str, drug_name, dose_v, dose_u, notes, person, SOURCE))
    result.rows_inserted += 1


# ── Notizen ───────────────────────────────────────────────────────────────────

def _handle_note(conn, row: dict, person: str, category: str,
                  dry: bool, result: ImportResult) -> None:
    date_str = row["date formatted"].strip()
    tod      = row.get("time of day", "").strip() or None
    content  = (row.get("notes", "").strip()
                or row.get("detail", "").strip()
                or row.get("rating/amount", "").strip())

    if not content:
        result.rows_skipped += 1
        return

    if dry:
        result.rows_inserted += 1
        return

    conn.execute("""
        INSERT OR IGNORE INTO bearable_notes
        (date, time_of_day, content, category, person)
        VALUES (?,?,?,?,?)
    """, (date_str, tod, content, category, person))
    ctx_id = f"bearable:{date_str}:{category or ''}:{content[:40]}"
    conn.execute("""
        INSERT OR IGNORE INTO user_context
        (id, date, ts_start, ts_end, person, source, source_app, tag, note)
        VALUES (?,?,?,?,?,?,?,?,?)
    """, (ctx_id, date_str, None, None, person, "bearable", "bearable", category or None, content))
    result.rows_inserted += 1


# ── Fallback ──────────────────────────────────────────────────────────────────

def _handle_custom(conn, row: dict, person: str, category: str,
                    dry: bool, result: ImportResult) -> None:
    date_str   = row["date formatted"].strip()
    detail     = row["detail"].strip()
    amount_raw = row["rating/amount"].strip()
    tod        = row.get("time of day", "").strip() or None
    notes      = row.get("notes", "").strip() or None

    if dry:
        result.rows_inserted += 1
        return

    conn.execute("""
        INSERT OR IGNORE INTO bearable_custom
        (date, category, detail, amount, time_of_day, notes, person)
        VALUES (?,?,?,?,?,?,?)
    """, (date_str, category, detail, amount_raw or None, tod, notes, person))
    result.rows_inserted += 1


# ── Haupt-Dispatch ────────────────────────────────────────────────────────────

_FACTOR_PREFIXES = ("factors", "food", "drink", "exercise", "activity",
                    "environment", "social", "work", "sleep quality",
                    "treatment", "supplements")

_NOTE_CATS = ("notes", "journal", "diary", "note")


def _dispatch(conn, row: dict, person: str, tz: ZoneInfo,
               dry: bool, result: ImportResult) -> None:
    cat = row.get("category", "").strip()
    cat_l = cat.lower()

    if cat_l == "sleep":
        _handle_sleep(conn, row, person, tz, dry, result)

    elif cat_l == "health measurements":
        _handle_health_meas(conn, row, person, tz, dry, result)

    elif cat_l == "symptoms":
        _handle_symptom(conn, row, person, dry, result)

    elif cat_l in _SCORE_CATS:
        _handle_score(conn, row, person, tz, cat, dry, result)

    elif cat_l == "medications":
        _handle_medication(conn, row, person, tz, dry, result)

    elif any(cat_l.startswith(p) for p in _FACTOR_PREFIXES):
        _handle_factor(conn, row, person, cat, dry, result)

    elif cat_l in _NOTE_CATS:
        _handle_note(conn, row, person, cat, dry, result)

    else:
        # Letzter Ausweg: als Score versuchen wenn Wert numerisch 1–10
        v = _safe_float(row.get("rating/amount", ""))
        if v is not None and 0 < v <= 10 and not row.get("detail", "").strip():
            _handle_score(conn, row, person, tz, cat, dry, result)
        else:
            _handle_custom(conn, row, person, cat, dry, result)


# ── Datei-Import ──────────────────────────────────────────────────────────────

def import_file(conn, path: Path, person: str = OWN_PERSON_ID,
                dry: bool = False) -> ImportResult:
    result = ImportResult(source=f"bearable:{path.name}")
    tz     = _local_tz(conn, person)

    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        # Spaltennamen normalisieren (Bearable ändert manchmal Groß/Kleinschreibung)
        reader.fieldnames = [
            n.strip().lower() for n in (reader.fieldnames or [])
        ]
        for row in reader:
            # Leere Zeilen überspringen
            if not row.get("date formatted", "").strip():
                result.rows_skipped += 1
                continue
            try:
                _dispatch(conn, row, person, tz, dry, result)
            except Exception as e:
                result.errors.append(f"{row.get('date formatted','?')}: {e}")
                result.rows_skipped += 1

    if not dry:
        log_import(conn, 'bearable', str(path), result.rows_inserted, result.rows_skipped)
        conn.commit()
    return result


def run(conn, _data_path=None, lang: str = "de",
        person: str | None = None) -> ImportResult:
    person = person or OWN_PERSON_ID
    _ensure_schema(conn)
    total = ImportResult(source=SOURCE)

    for f in sorted(CSV_DIR.glob("bearable*.csv")):
        r = import_file(conn, f, person)
        total.rows_inserted += r.rows_inserted
        total.rows_skipped  += r.rows_skipped
        total.errors.extend(r.errors)

    return total


# ── Rebuild-Helfer ────────────────────────────────────────────────────────────

def _rebuild(conn, person: str) -> None:
    for tbl, col in [
        ("sessions",         "source_app"),
        ("session_metrics",  None),          # via session_id JOIN
        ("measurements",     "source_app"),
        ("symptoms",         "source"),
        ("medications",      "source"),
        ("bearable_factors", None),
        ("bearable_notes",   None),
        ("bearable_custom",  None),
    ]:
        if col:
            conn.execute(f"DELETE FROM {tbl} WHERE {col}=? AND person=?",
                         (SOURCE, person))
        elif tbl == "session_metrics":
            conn.execute("""
                DELETE FROM session_metrics WHERE session_id IN (
                    SELECT id FROM sessions WHERE source_app=? AND person=?
                )
            """, (SOURCE, person))
        else:
            conn.execute(f"DELETE FROM {tbl} WHERE person=?", (person,))
    conn.commit()
    print(t("Bearable-Daten gelöscht — vollständiger Neuaufbau.",
            "Bearable data cleared — full rebuild."))


# ── Hauptprogramm ─────────────────────────────────────────────────────────────

def main():
    """
    Hauptfunktion: Koordiniert den Import der Bearable-Daten.

    Command-Line-Argumente:
        --file: Einzelne CSV-Datei
        --rebuild: Bearable-Daten löschen und neu importieren
        --dry-run: Testlauf ohne Import
        --update: Nur neue Einträge
    """
    parser = argparse.ArgumentParser(
        description=t("Bearable CSV → health.db", "Bearable CSV → health.db"))
    parser.add_argument("--file",    metavar="PATH",
                        help=t("Einzelne CSV-Datei", "Single CSV file"))
    parser.add_argument("--rebuild", action="store_true",
                        help=t("Bearable-Daten löschen + neu", "Delete and reimport"))
    parser.add_argument("--dry-run", action="store_true",
                        help=t("Nur anzeigen, nichts schreiben", "Show only, no writes"))
    parser.add_argument("--update",  action="store_true",
                        help=t("Nur neue Einträge (Standard via INSERT OR IGNORE)",
                               "New entries only (default via INSERT OR IGNORE)"))
    parser.add_argument("--person", default=None, metavar="PERSON_ID",
                        help=t("Person-ID (Standard: eigene Person aus Config)",
                               "Person ID (default: own person from config)"))
    add_lang_arg(parser)
    args = parser.parse_args()
    apply_lang_from_args(args)

    dry = args.dry_run
    if dry:
        print(t("── Dry-run ──────────────────────────────────────────",
                "── Dry-run ──────────────────────────────────────────"))

    conn = open_db()
    conn.execute("PRAGMA journal_mode=WAL")
    _ensure_schema(conn)

    person = resolve_person(args.person)

    if args.rebuild and not dry:
        _rebuild(conn, person)

    files = [Path(args.file).expanduser()] if args.file \
            else sorted(CSV_DIR.glob("bearable*.csv"))

    if not files:
        print(t(f"Keine bearable*.csv in {CSV_DIR} — übersprungen.",
                f"No bearable*.csv in {CSV_DIR} — skipped."))
        sys.exit(0)

    total_ins = total_skip = 0
    for f in files:
        print(t(f"Importiere: {f.name}", f"Importing: {f.name}"))
        r = import_file(conn, f, person, dry=dry)
        total_ins  += r.rows_inserted
        total_skip += r.rows_skipped
        if r.errors:
            for e in r.errors[:5]:
                print(f"  Warnung: {e}", file=sys.stderr)
        print(f"  {r.rows_inserted} neu, {r.rows_skipped} übersprungen")

    print(t(f"\nGesamt: {total_ins} Einträge, {total_skip} übersprungen",
            f"\nTotal: {total_ins} entries, {total_skip} skipped"))

    if not dry:
        # Statistik
        for tbl, label in [
            ("sessions",         "Sleep-Sessions"),
            ("measurements",     "Messungen"),
            ("symptoms",         "Symptome"),
            ("medications",      "Medikamente"),
            ("bearable_factors", "Faktoren"),
            ("bearable_notes",   "Notizen"),
            ("bearable_custom",  "Sonstiges"),
        ]:
            try:
                n = conn.execute(
                    f"SELECT COUNT(*) FROM {tbl} WHERE "
                    f"{'source_app' if tbl in ('sessions','measurements') else 'source' if tbl in ('symptoms','medications') else 'person'}=?",
                    (SOURCE if tbl not in ('bearable_factors','bearable_notes','bearable_custom') else person,)
                ).fetchone()[0]
                if n:
                    print(f"  {label}: {n}")
            except Exception:
                pass

    conn.close()


if __name__ == "__main__":
    main()
