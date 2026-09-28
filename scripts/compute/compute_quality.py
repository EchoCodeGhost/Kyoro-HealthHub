#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Data-quality checks before AI analysis (v2 schema).

@tier        infrastructure
@purpose.de  Erkennt Anomalien in health.db, bevor ein LLM die Daten interpretiert,
             und schreibt Qualitäts-Flags. Reine Datenprüfung, keine klinische Aussage.
@purpose.en  Detects anomalies in health.db before an LLM interprets the data and
             writes quality flags. Pure data checking, no clinical claim.
@method.de   Scannt Messtabellen auf Ausreißer, Lücken, Duplikate und implausible
             Werte; Befunde werden mit Schweregrad in data_quality_flags abgelegt.
@method.en   Scans measurement tables for outliers, gaps, duplicates and implausible
             values; findings are stored with a severity in data_quality_flags.
@reads       measurements, blood_pressure, ppi_raw, polar_nightly_hrv, symptoms,
             devices
@writes      data_quality_flags
@limits.de   Heuristische Plausibilitätsprüfung, kein Ground-Truth-Abgleich. Kann
             echte Extremwerte fälschlich flaggen und subtile Fehler übersehen.

@relevance.de  Ermöglicht die Bewertung der Datenqualität, essentiell für die Datenvalidierung
@relevance.en  Enables data quality assessment, essential for data validation
@limits.en   Heuristic plausibility checking, no ground-truth comparison. May flag
             genuine extremes and miss subtle errors.
@usage
    python3 compute_quality.py
    python3 compute_quality.py --table heart_rate
    python3 compute_quality.py --severity critical
    python3 compute_quality.py --summary
"""

import argparse
import sqlite3
from collections import defaultdict
from datetime import date
from pathlib import Path
import sys as _sys
_sys.path.insert(0, str(Path(__file__).parent.parent))
from health_config import Config as _Cfg
from modules.db import open_db, DB_OPERATIONAL_ERRORS
from modules.i18n import t, add_lang_arg, apply_lang_from_args
_cfg = _Cfg()

DB_PATH = _cfg.db_path
TODAY   = date.today().isoformat()

DEVICE_TRANSITIONS: list[tuple[str, str]] = []

FlagRow = tuple


def setup_tables(conn: sqlite3.Connection, table_filter: str | None) -> str:
    """Returns the target table name to write flags into."""
    if table_filter:
        conn.execute("DELETE FROM data_quality_flags WHERE table_name = ?",
                     (table_filter,))
        conn.commit()
        return "data_quality_flags"
    # Full scan: write to staging table, swap atomically at the end
    conn.executescript("""
        DROP TABLE IF EXISTS data_quality_flags_new;
        CREATE TABLE data_quality_flags_new (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            table_name       TEXT NOT NULL,
            column_name      TEXT NOT NULL,
            datetime_or_date TEXT,
            value            REAL,
            flag_type        TEXT NOT NULL,
            severity         TEXT NOT NULL
                CHECK(severity IN ('info','warning','critical')),
            message          TEXT NOT NULL,
            resolved         INTEGER NOT NULL DEFAULT 0
        );
        CREATE UNIQUE INDEX IF NOT EXISTS idx_dqf_new_unique
            ON data_quality_flags_new(table_name, column_name,
                                      datetime_or_date, flag_type);
    """)
    conn.commit()
    print(t("Staging-Tabelle data_quality_flags_new erstellt.", "Staging table data_quality_flags_new created."))
    return "data_quality_flags_new"


def bulk_insert(conn: sqlite3.Connection, rows: list[FlagRow],
                target_table: str = "data_quality_flags") -> int:
    if not rows:
        return 0
    conn.executemany(f"""
        INSERT OR IGNORE INTO {target_table}
            (table_name, column_name, datetime_or_date, value, flag_type,
             severity, message)
        VALUES (?,?,?,?,?,?,?)
    """, rows)
    conn.commit()
    return len(rows)


# ── CRITICAL ──────────────────────────────────────────────────────────────────

# Ein Lauf unplausibler Messwerte, der binnen SENSOR_DROPOUT_MAX_RUN_S Sekunden
# endet und auf beiden Seiten von Werten umgeben ist, die selbst NICHT im
# "unmöglich"-Band liegen (per Lauf-Definition also bereits >=20 und <=300 bpm),
# ist ein optischer/Brustgurt-Signalverlust (Bewegungsartefakt, schlechter
# Hautkontakt), kein reales Vitalwert-Ereignis. Absichtlich KEIN zusätzliches
# Plausibilitätsfenster auf die Nachbarwerte (z.B. "mind. 40 bpm") — das würde
# echte Dropouts mit einer langsam abfallenden/wieder ansteigenden Flanke
# (z.B. 26→18→18→79 bpm) fälschlich als "critical" einstufen, obwohl 26 bpm
# selbst schon Teil desselben Signalverlusts ist, nur eben >=20 bpm.
# Schwelle empirisch aus den bislang beobachteten Dropouts abgeleitet (alle
# 1-8s lang) plus Sicherheitsmarge.
SENSOR_DROPOUT_MAX_RUN_S = 30


def check_hr_critical(conn: sqlite3.Connection) -> list[FlagRow]:
    """Physiologisch unmögliche HR-Werte, getrennt nach Sensor-Dropout-Muster
    (isolierter Ausreißer, beidseitig von plausiblen Werten umgeben) vs.
    echtem kritischen Befund (Ausreißer hält an oder hat keine plausible
    Umgebung — z. B. Aufzeichnungsfehler oder tatsächlich extreme HR)."""
    rows: list[FlagRow] = []
    dates = [d for (d,) in conn.execute("""
        SELECT DISTINCT date FROM heart_rate WHERE bpm < 20 OR bpm > 300
    """)]

    for d in dates:
        samples = conn.execute("""
            SELECT ts, bpm FROM heart_rate WHERE date = ? ORDER BY ts
        """, (d,)).fetchall()

        # Läufe aufeinanderfolgender implausibler Samples finden
        i = 0
        dropout_only = True
        while i < len(samples):
            _, v = samples[i]
            if not (v < 20 or v > 300):
                i += 1
                continue
            j = i
            while j < len(samples) and (samples[j][1] < 20 or samples[j][1] > 300):
                j += 1
            run_start_ts, run_end_ts = samples[i][0], samples[j - 1][0]
            duration_s = _seconds_between(run_start_ts, run_end_ts)
            before = samples[i - 1][1] if i > 0 else None
            after = samples[j][1] if j < len(samples) else None
            # before/after sind per Lauf-Definition bereits außerhalb des
            # "unmöglich"-Bands (20 <= v <= 300) — hier nur noch Existenz und
            # Kürze des Laufs prüfen.
            is_dropout = (
                duration_s <= SENSOR_DROPOUT_MAX_RUN_S
                and before is not None
                and after is not None
            )
            if not is_dropout:
                dropout_only = False
            i = j

        if dropout_only:
            rows.append(("heart_rate", "bpm", d, None,
                         "hr_sensor_dropout", "info",
                         "HR-Ausreißer als isolierter Sensor-Dropout erkannt "
                         "(kurzer Signalverlust, beidseitig plausible Werte) — kein Vitalwert-Befund"))
        else:
            mn = min(v for _, v in samples if v < 20 or v > 300)
            mx = max(v for _, v in samples if v < 20 or v > 300)
            v = mn if mn < 20 else mx
            rows.append(("heart_rate", "bpm", d, float(v),
                         "hr_impossible", "critical",
                         f"HR physiologisch unmöglich: min={mn}, max={mx} bpm"))
    return rows


def _seconds_between(ts_a: str, ts_b: str) -> float:
    from datetime import datetime
    fmt = "%Y-%m-%dT%H:%M:%S"
    a = datetime.strptime(ts_a[:19], fmt)
    b = datetime.strptime(ts_b[:19], fmt)
    return abs((b - a).total_seconds())


def check_spo2_critical(conn: sqlite3.Connection) -> list[FlagRow]:
    rows = []
    for d, v in conn.execute("""
        SELECT ts, value FROM measurements
        WHERE metric='spo2' AND (value < 50 OR value > 100)
    """):
        rows.append(("measurements(spo2)", "value", d, float(v),
                     "spo2_impossible", "critical",
                     f"SpO2 physiologisch unmöglich: {v}%"))
    for d, v in conn.execute("""
        SELECT ts, value FROM measurements
        WHERE metric='oxygen_saturation' AND (value < 0.50 OR value > 1.0)
    """):
        rows.append(("measurements(oxygen_saturation)", "value", d, round(v * 100, 1),
                     "spo2_impossible", "critical",
                     f"Apple SpO2 physiologisch unmöglich: {round(v*100,1)}%"))
    return rows


def check_ppi_critical(conn: sqlite3.Connection) -> list[FlagRow]:
    rows = []
    for d, mn, mx, n in conn.execute("""
        SELECT date(datetime), MIN(pulse_ms), MAX(pulse_ms), COUNT(*)
        FROM ppi_raw WHERE pulse_ms < 200 OR pulse_ms > 3000
        GROUP BY date(datetime)
    """):
        v = mn if mn < 200 else mx
        rows.append(("ppi_raw", "pulse_ms", d, float(v),
                     "ppi_impossible", "critical",
                     f"PPI physiologisch unmöglich: min={mn}ms, max={mx}ms, n={n}"))
    return rows


def check_hrv_critical(conn: sqlite3.Connection) -> list[FlagRow]:
    rows = []
    # Polar nightly HRV (custom table)
    for d, v in conn.execute(
        "SELECT date, rmssd_ms FROM polar_nightly_hrv "
        "WHERE rmssd_ms < 0 OR rmssd_ms > 500"
    ):
        rows.append(("polar_nightly_hrv", "rmssd_ms", d, float(v),
                     "hrv_impossible", "critical",
                     f"RMSSD physiologisch unmöglich: {v}ms"))
    # HRV als measurement (Garmin, Polar Spot, andere)
    for d, v in conn.execute("""
        SELECT ts, value FROM measurements
        WHERE metric IN ('hrv_rmssd','hrv_sdnn','hrv_avg_ms')
          AND (value < 0 OR value > 500)
    """):
        rows.append(("measurements(hrv)", "value", d, float(v),
                     "hrv_impossible", "critical",
                     f"HRV physiologisch unmöglich: {v}ms"))
    return rows


def check_bp_critical(conn: sqlite3.Connection) -> list[FlagRow]:
    rows = []
    for d, sys_v, dia_v in conn.execute("""
        SELECT ts, systolic, diastolic FROM blood_pressure
        WHERE systolic < 50 OR systolic > 250
           OR diastolic < 30 OR diastolic > 150
    """):
        if sys_v < 50 or sys_v > 250:
            rows.append(("blood_pressure", "systolic", d, float(sys_v),
                         "bp_systolic_impossible", "critical",
                         f"Systolischer Blood pressure unmöglich: {sys_v} mmHg"))
        if dia_v < 30 or dia_v > 150:
            rows.append(("blood_pressure", "diastolic", d, float(dia_v),
                         "bp_diastolic_impossible", "critical",
                         f"Diastolischer Blood pressure unmöglich: {dia_v} mmHg"))
    return rows


# ── WARNING ───────────────────────────────────────────────────────────────────

# Ein Tagesmittelwert aus einer stark unterdurchschnittlichen Anzahl Messungen
# (Uhr kaum getragen) ist statistisch unzuverlässig — er kann als Ausreißer
# erscheinen, obwohl er nur eine kurze, nicht repräsentative Ruhephase abbildet.
# Schwelle: mindestens 20% der im 30-Tage-Fenster üblichen Tagesabdeckung.
HR_ZSCORE_MIN_COVERAGE_FRACTION = 0.2


def check_hr_zscore(conn: sqlite3.Connection) -> list[FlagRow]:
    rows = []
    for d, avg_hr, win_avg, z, n, win_avg_n in conn.execute("""
        WITH daily AS (
            SELECT date d, AVG(bpm) avg_hr, COUNT(*) n
            FROM heart_rate WHERE bpm BETWEEN 20 AND 300
            GROUP BY date
        ),
        windowed AS (
            SELECT d, avg_hr, n,
                   AVG(avg_hr)         OVER w AS win_avg,
                   AVG(avg_hr*avg_hr)  OVER w AS win_sq_avg,
                   AVG(n)              OVER w AS win_avg_n
            FROM daily
            WINDOW w AS (ORDER BY d ROWS BETWEEN 30 PRECEDING AND CURRENT ROW)
        )
        SELECT d, avg_hr, win_avg,
               CASE WHEN (win_sq_avg - win_avg*win_avg) > 0
                    THEN ABS(avg_hr - win_avg) /
                         SQRT(win_sq_avg - win_avg*win_avg)
                    ELSE 0 END z_score,
               n, win_avg_n
        FROM windowed WHERE z_score > 4
    """):
        if n < HR_ZSCORE_MIN_COVERAGE_FRACTION * win_avg_n:
            rows.append(("heart_rate", "bpm", d, round(avg_hr, 1),
                         "hr_low_coverage_day", "info",
                         f"Tagesdurchschnitt statistisch unzuverlässig: nur {n} Messungen "
                         f"(Fenster-∅ {round(win_avg_n)}) — Wert kein verlässliches Signal"))
        else:
            rows.append(("heart_rate", "bpm", d, round(avg_hr, 1),
                         "hr_zscore_outlier", "warning",
                         f"Täglicher HR-∅ statistisch notable: {round(avg_hr,1)} bpm "
                         f"(z={round(z,2)}, Fenster-∅={round(win_avg,1)})"))
    return rows


def check_hrv_iqr(conn: sqlite3.Connection) -> list[FlagRow]:
    hrv = conn.execute(
        "SELECT date, rmssd_ms FROM polar_nightly_hrv "
        "WHERE rmssd_ms > 0 ORDER BY date"
    ).fetchall()
    flags = []
    for i, (d, v) in enumerate(hrv):
        win = [hrv[j][1] for j in range(max(0, i-15), min(len(hrv), i+16)) if j != i]
        if len(win) < 10:
            continue
        win.sort()
        q1 = win[len(win) // 4]
        q3 = win[3 * len(win) // 4]
        iqr = q3 - q1
        if iqr > 0 and (v < q1 - 3*iqr or v > q3 + 3*iqr):
            flags.append(("polar_nightly_hrv", "rmssd_ms", d, float(v),
                          "hrv_iqr_outlier", "warning",
                          f"RMSSD notable: {v}ms (Q1={q1}, Q3={q3}, IQR={iqr})"))
    return flags


def check_spo2_warning(conn: sqlite3.Connection) -> list[FlagRow]:
    rows = []
    for d, v in conn.execute("""
        SELECT ts, value FROM measurements
        WHERE metric='spo2' AND value < 85 AND value >= 50
    """):
        rows.append(("measurements(spo2)", "value", d, float(v),
                     "spo2_low", "warning",
                     f"SpO2 clinical niedrig: {v}% (<85%)"))
    for d, v in conn.execute("""
        SELECT ts, ROUND(value*100,1) FROM measurements
        WHERE metric='oxygen_saturation' AND value < 0.85 AND value >= 0.50
    """):
        rows.append(("measurements(oxygen_saturation)", "value", d, float(v),
                     "spo2_low", "warning",
                     f"Apple SpO2 clinical niedrig: {v}% (<85%)"))
    return rows


def check_ppi_runs(conn: sqlite3.Connection) -> list[FlagRow]:
    print(t("  Lade PPI-Daten für Run-Erkennung ...", "  Loading PPI data for run detection ..."), flush=True)
    raw = conn.execute(
        "SELECT date(datetime) d, pulse_ms FROM ppi_raw ORDER BY datetime"
    ).fetchall()
    day_ppis: dict = defaultdict(list)
    for d, pms in raw:
        day_ppis[d].append(pms)
    flags = []
    for day, ppis in sorted(day_ppis.items()):
        max_run = 1
        cur_val = ppis[0] if ppis else None
        cur_run = 1
        for p in ppis[1:]:
            if p == cur_val:
                cur_run += 1
                if cur_run > max_run:
                    max_run = cur_run
            else:
                cur_val = p
                cur_run = 1
        if max_run >= 10:
            flags.append(("ppi_raw", "pulse_ms", day, float(max_run),
                          "ppi_identical_run", "warning",
                          f"PPI: {max_run} aufeinanderfolgende identische Intervall "
                          f"— mögliches Sensor-Artefakt"))
    return flags


def check_training_duration(conn: sqlite3.Connection) -> list[FlagRow]:
    rows = []
    for d, dur, sport in conn.execute(
        "SELECT date, duration_s, sport FROM training "
        "WHERE duration_s > 43200"
    ):
        rows.append(("training", "duration_s", d, float(dur),
                     "training_too_long", "warning",
                     f"Workout >12h: {round(dur/3600,1)}h ({sport})"))
    return rows


def check_sleep_duration(conn: sqlite3.Connection) -> list[FlagRow]:
    rows = []
    for d, source, sleep_s in conn.execute("""
        SELECT date, source_app,
               COALESCE(total_sleep_s, total_sleep_min*60, time_asleep_s)
        FROM sleep
        WHERE COALESCE(total_sleep_s, total_sleep_min*60, time_asleep_s) > 50400
           OR COALESCE(total_sleep_s, total_sleep_min*60, time_asleep_s) < 0
    """):
        if sleep_s is None:
            continue
        rows.append(("sleep", "total_sleep_s", d, float(sleep_s),
                     "sleep_duration_invalid", "warning",
                     f"Sleepzeit unrealistisch ({source}): {round(sleep_s/3600,1)}h"))
    return rows


def check_symptom_scale(conn: sqlite3.Connection) -> list[FlagRow]:
    rows = []
    for d, sym, kat, v in conn.execute(
        "SELECT date, symptom, category, value_num FROM symptoms "
        "WHERE value_num < 0 OR value_num > 10"
    ):
        rows.append(("symptoms", "value_num", d, float(v),
                     "symptom_scale_invalid", "warning",
                     f"Symptomwert außerhalb 0–10: {sym} = {v} ({kat})"))
    for d, sym, kat, v in conn.execute(
        "SELECT date, symptom, category, value_num FROM symptoms "
        "WHERE category IN ('Behandlung','Balsoraum/GI') AND value_num > 1"
    ):
        rows.append(("symptoms", "value_num", d, float(v),
                     "symptom_scale_unexpected", "warning",
                     f"Binäres Symptom >1: {sym} = {v} ({kat})"))
    return rows


# ── INFO ──────────────────────────────────────────────────────────────────────
def check_hr_gaps(conn: sqlite3.Connection) -> list[FlagRow]:
    print(t("  Prüfe HR-Lücken ...", "  Checking HR gaps ..."), flush=True)
    rows = []
    for prev_d, d, gap in conn.execute("""
        WITH dates AS (
            SELECT DISTINCT date d FROM heart_rate ORDER BY d
        ),
        gaps AS (
            SELECT d,
                   LAG(d) OVER (ORDER BY d) prev_d,
                   CAST(julianday(d) - julianday(LAG(d) OVER (ORDER BY d))
                        AS INT) gap
            FROM dates
        )
        SELECT prev_d, d, gap FROM gaps WHERE gap > 7 ORDER BY gap DESC
    """):
        rows.append(("heart_rate", "date",
                     f"gap:{prev_d}/{d}", float(gap),
                     "data_gap", "info",
                     f"Datenlücke {gap} days: {prev_d} bis {d}"))
    return rows


def check_hrv_gaps(conn: sqlite3.Connection) -> list[FlagRow]:
    rows = []
    for prev_d, d, gap in conn.execute("""
        WITH gaps AS (
            SELECT date,
                   LAG(date) OVER (ORDER BY date) prev_date,
                   CAST(julianday(date) -
                        julianday(LAG(date) OVER (ORDER BY date)) AS INT) gap
            FROM polar_nightly_hrv
        )
        SELECT prev_date, date, gap FROM gaps
        WHERE gap > 14 ORDER BY gap DESC
    """):
        rows.append(("polar_nightly_hrv", "date",
                     f"gap:{prev_d}/{d}", float(gap),
                     "data_gap", "info",
                     f"HRV-Lücke {gap} Nights: {prev_d} bis {d}"))
    return rows


def check_measurement_duplicates(conn: sqlite3.Connection) -> list[FlagRow]:
    rows = []
    # Mehrere Devicee zur gleichen Zeit for gleiche Metrik
    for metric, ts, n_dev, devices in conn.execute("""
        SELECT metric, substr(ts,1,19) t,
               COUNT(DISTINCT device_id) n_dev,
               GROUP_CONCAT(DISTINCT device_id) devices
        FROM measurements
        WHERE metric IN ('heart_rate','hrv_sdnn','spo2','oxygen_saturation',
                         'resting_heart_rate')
        GROUP BY metric, substr(ts,1,19)
        HAVING n_dev > 1
        LIMIT 1000
    """):
        rows.append(("measurements", "value", ts, None,
                     "near_duplicate", "info",
                     f"Gleicher Messzeitpunkt from {n_dev} devices: "
                     f"{metric} @ {ts} ({devices})"))
    return rows


def check_future_timestamps(conn: sqlite3.Connection) -> list[FlagRow]:
    rows = []
    for tbl, col, expr in [
        ("measurements",  "ts",       "date"),
        ("ppi_raw",       "datetime", "date(datetime)"),
        ("polar_nightly_hrv", "date", "date"),
        ("sessions",      "ts_start", "date"),
    ]:
        try:
            for d, n in conn.execute(
                f"SELECT {expr}, COUNT(*) FROM {tbl} "
                f"WHERE {expr} > '{TODAY}' GROUP BY {expr}"
            ):
                rows.append((tbl, col, d, float(n), "future_timestamp", "info",
                             f"{n} entries with Datum in der Zukunft: {d}"))
        except DB_OPERATIONAL_ERRORS:
            pass
    return rows


def check_ppi_import_artifact(conn: sqlite3.Connection) -> list[FlagRow]:
    """Flag isolated PPI beats predating the configured data_start.

    Such points are typically epoch-timestamp artifacts from a test import
    rather than real beats. The cutoff comes from clinical.data_start so the
    check works for any user without baking in a personal date.
    """
    cutoff = _cfg.data_start or "1900-01-01"
    row = conn.execute(
        "SELECT date(datetime), COUNT(*) FROM ppi_raw "
        "WHERE date(datetime) < ? "
        "GROUP BY date(datetime) ORDER BY COUNT(*) DESC LIMIT 1",
        (cutoff,),
    ).fetchone()
    if row and row[1]:
        d, n = row
        return [("ppi_raw", "datetime", d, float(n),
                 "import_artifact", "info",
                 f"PPI {d}: {n} beats predating clinical.data_start "
                 f"({cutoff}) — likely a test-import artifact")]
    return []


def check_device_transitions(conn: sqlite3.Connection) -> list[FlagRow]:
    return [("_meta", "device", d, None, "device_transition", "info", msg)
            for d, msg in DEVICE_TRANSITIONS]


# ── Orchestrierung ────────────────────────────────────────────────────────────
ALL_CHECKS = [
    # critical
    (check_hr_critical,            "heart_rate"),
    (check_spo2_critical,          "measurements"),
    (check_ppi_critical,           "ppi_raw"),
    (check_hrv_critical,           "polar_nightly_hrv"),
    (check_bp_critical,            "blood_pressure"),
    # warning
    (check_hr_zscore,              "heart_rate"),
    (check_hrv_iqr,                "polar_nightly_hrv"),
    (check_spo2_warning,           "measurements"),
    (check_ppi_runs,               "ppi_raw"),
    (check_training_duration,      "training"),
    (check_sleep_duration,         "sleep"),
    (check_symptom_scale,          "symptoms"),
    # info
    (check_hr_gaps,                "heart_rate"),
    (check_hrv_gaps,               "polar_nightly_hrv"),
    (check_measurement_duplicates, "measurements"),
    (check_future_timestamps,      "measurements"),
    (check_ppi_import_artifact,    "ppi_raw"),
    (check_device_transitions,     "_meta"),
]


def run_checks(conn: sqlite3.Connection,
               table_filter: str | None,
               severity_filter: str | None,
               target_table: str = "data_quality_flags") -> int:
    total = 0
    for fn, tbl in ALL_CHECKS:
        if table_filter and tbl != table_filter:
            continue
        name = fn.__name__
        print(f"  {name} ...", flush=True)
        try:
            flags = fn(conn)
        except DB_OPERATIONAL_ERRORS as e:
            print(t(f"    ⚠ Tabelle/Spalte fehlt: {e}", f"    ⚠ Table/column missing: {e}"))
            continue
        if severity_filter:
            flags = [f for f in flags if f[5] == severity_filter]
        inserted = bulk_insert(conn, flags, target_table)
        total += len(flags)
        if flags:
            print(t(f"    → {len(flags)} Flags ({inserted} neu eingefügt)", f"    → {len(flags)} flags ({inserted} newly inserted)"))
    return total


def print_summary(conn: sqlite3.Connection) -> None:
    tables_exist = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' "
        "AND name='data_quality_flags'"
    ).fetchone()
    if not tables_exist:
        print(t("data_quality_flags existiert noch nicht. Bitte zuerst scannen.", "data_quality_flags does not exist yet. Please run scan first."))
        return

    print(t("\n── Qualitätszusammenfassung ───────────────────────────────────────", "\n── Quality summary ───────────────────────────────────────────────"))
    for sev, tbl, ft, n, unresolved in conn.execute("""
        SELECT severity, table_name, flag_type, COUNT(*) n,
               SUM(CASE WHEN resolved=0 THEN 1 ELSE 0 END) unresolved
        FROM data_quality_flags
        GROUP BY severity, table_name, flag_type
        ORDER BY
            CASE severity WHEN 'critical' THEN 0
                          WHEN 'warning'  THEN 1 ELSE 2 END,
            table_name, flag_type
    """):
        marker = ("CRITICAL" if sev == "critical"
                  else "WARN" if sev == "warning" else "INFO")
        print(f"  [{marker:<8}] {tbl:<28} {ft:<30} n={n} (offen: {unresolved})")

    print(t("\n── Offene Flags gesamt ────────────────────────────────────────────", "\n── Open flags total ──────────────────────────────────────────────"))
    for sev, n in conn.execute("""
        SELECT severity, COUNT(*) FROM data_quality_flags
        WHERE resolved = 0 GROUP BY severity
        ORDER BY CASE severity WHEN 'critical' THEN 0
                               WHEN 'warning'  THEN 1 ELSE 2 END
    """):
        print(f"  {sev.upper():<10}: {n}")


def main() -> None:
    parser = argparse.ArgumentParser(description=t("Datenqualitätsprüfung health.db", "Data quality scan health.db"))
    parser.add_argument("--table",    help="Only diese Table/View prüfen")
    parser.add_argument("--severity", choices=["critical", "warning", "info"])
    parser.add_argument("--summary",  action="store_true")
    add_lang_arg(parser)

    args = parser.parse_args()
    apply_lang_from_args(args)

    conn = open_db()
    import math as _math
    conn.create_function("SQRT", 1, lambda x: _math.sqrt(x) if x and x > 0 else 0.0)

    if args.summary:
        print_summary(conn)
        conn.close()
        return

    target_table = setup_tables(conn, table_filter=args.table)
    _tbl = args.table or t("alle", "all")
    _sev = args.severity or t("alle", "all")
    print(t(f"\nStarte Qualitätsscan (Tabelle: {_tbl}, Schwere: {_sev}) ...",
            f"\nStarting quality scan (table: {_tbl}, severity: {_sev}) ..."))

    total = run_checks(conn,
                       table_filter=args.table,
                       severity_filter=args.severity,
                       target_table=target_table)

    # Atomisch tauschen wenn Full-Scan
    if target_table == "data_quality_flags_new":
        conn.executescript("""
        BEGIN;
        DROP TABLE IF EXISTS data_quality_flags;
        ALTER TABLE data_quality_flags_new RENAME TO data_quality_flags;
        COMMIT;
        """)

    print(t(f"\n{total} Flags erkannt.", f"\n{total} flags detected."))
    print_summary(conn)
    print(t(f"\nDatenbank: {DB_PATH}", f"\nDatabase: {DB_PATH}"))
    conn.close()


if __name__ == "__main__":
    main()
