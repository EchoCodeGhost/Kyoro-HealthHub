# SPDX-License-Identifier: GPL-3.0-or-later
"""
Unit test for utils/orthostatic_test.py's SpO2/blood-pressure extension and
local<->UTC conversion helpers.

Covers: compute_spo2, compute_bp, assess (new BP/SpO2 branches),
_local_to_utc/_utc_to_local, query_spo2, query_bp, query_ppi_beats.
Not covered: --auto-detect's interactive main() orchestration (input()-driven,
delegates the actual jump detection to compute_orthostatic_detection, which
has its own coverage) and the guided (non-evaluate) countdown flow.
"""

import sqlite3
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

from utils.create_schema import SCHEMA
import utils.orthostatic_test as ot


def _fresh_conn():
    conn = sqlite3.connect(":memory:")
    conn.executescript(SCHEMA)
    return conn


class FakeCfg:
    # Deliberately not this project's typical/likely real default (see
    # check_source_privacy.py's _SELF_EXCLUDE entry for this file) — any
    # DST-observing zone works to exercise _local_to_utc/_utc_to_local, this
    # one just avoids coinciding with a plausible real installation's zone.
    home_timezone = "America/New_York"


# ── _local_to_utc / _utc_to_local ────────────────────────────────────────────

def test_local_to_utc_summer_offset(monkeypatch):
    monkeypatch.setattr(ot, "_cfg", FakeCfg())
    # America/New_York is UTC-4 in July (EDT).
    local = datetime(2026, 7, 6, 10, 0, 0)
    assert ot._local_to_utc(local) == datetime(2026, 7, 6, 14, 0, 0)


def test_utc_to_local_summer_offset(monkeypatch):
    monkeypatch.setattr(ot, "_cfg", FakeCfg())
    utc = datetime(2026, 7, 6, 14, 0, 0)
    assert ot._utc_to_local(utc) == datetime(2026, 7, 6, 10, 0, 0)


def test_local_to_utc_and_back_round_trips(monkeypatch):
    monkeypatch.setattr(ot, "_cfg", FakeCfg())
    original = datetime(2026, 1, 15, 9, 30, 0)  # winter (EST, UTC-5)
    assert ot._utc_to_local(ot._local_to_utc(original)) == original


# ── compute_spo2 ──────────────────────────────────────────────────────────────

def test_compute_spo2_avg_and_min_per_phase():
    result = ot.compute_spo2([97.0, 96.0, 98.0], [94.0, 91.0, 93.0])
    assert result == {
        "spo2_supine_avg": 97.0,
        "spo2_supine_min": 96.0,
        "spo2_stand_avg": 92.7,
        "spo2_stand_min": 91.0,
    }


def test_compute_spo2_empty_lists_are_none():
    result = ot.compute_spo2([], [])
    assert result == {
        "spo2_supine_avg": None,
        "spo2_supine_min": None,
        "spo2_stand_avg": None,
        "spo2_stand_min": None,
    }


# ── compute_bp ────────────────────────────────────────────────────────────────

def test_compute_bp_avg_supine_min_standing_and_drop():
    bp_sup = [{"systolic": 120, "diastolic": 80, "pulse": 60},
              {"systolic": 118, "diastolic": 78, "pulse": 62}]
    bp_sta = [{"systolic": 95, "diastolic": 65, "pulse": 90},
              {"systolic": 90, "diastolic": 60, "pulse": 95}]

    result = ot.compute_bp(bp_sup, bp_sta)

    assert result["bp_supine_sys_avg"] == 119.0
    assert result["bp_supine_dia_avg"] == 79.0
    assert result["bp_stand_sys_min"] == 90
    assert result["bp_stand_dia_min"] == 60
    assert result["bp_drop_sys"] == 29.0
    assert result["bp_drop_dia"] == 19.0


def test_compute_bp_missing_phase_is_none():
    result = ot.compute_bp([], [{"systolic": 90, "diastolic": 60, "pulse": 90}])
    assert result["bp_supine_sys_avg"] is None
    assert result["bp_drop_sys"] is None  # can't compute a drop without a baseline


# ── assess ────────────────────────────────────────────────────────────────────

def test_assess_flags_orthostatic_hypotension():
    m = {"hr_delta": 10, "bp_drop_sys": 22, "bp_drop_dia": 5}
    result = ot.assess(m)
    assert "Hypotonie" in result or "hypotension" in result


def test_assess_no_hypotension_when_drop_below_threshold():
    m = {"hr_delta": 10, "bp_drop_sys": 10, "bp_drop_dia": 5}
    result = ot.assess(m)
    assert "Kein Hinweis auf orthostatische Hypotonie" in result or "No sign of orthostatic hypotension" in result


def test_assess_omits_bp_line_when_no_bp_data():
    m = {"hr_delta": 10}
    result = ot.assess(m)
    assert "Hypotonie" not in result and "hypotension" not in result


def test_assess_flags_low_spo2_while_standing():
    m = {"hr_delta": 10, "spo2_stand_min": 89}
    result = ot.assess(m)
    assert "89" in result


def test_assess_omits_spo2_line_above_threshold():
    m = {"hr_delta": 10, "spo2_stand_min": 96}
    result = ot.assess(m)
    assert "SpO2" not in result


def test_assess_still_reports_pots_criterion_unchanged():
    m = {"hr_delta": 32}
    result = ot.assess(m)
    assert "POTS" in result


# ── query_spo2 / query_bp / query_ppi_beats ─────────────────────────────────

def test_query_spo2_picks_device_with_most_readings_in_window():
    conn = _fresh_conn()
    for i in range(3):
        conn.execute("""
            INSERT INTO measurements (ts, date, metric, value, device_id, person)
            VALUES (?, '2026-07-06', 'spo2', 96.0, 'DEV-o2ring', 'PER-test')
        """, (f"2026-07-06T10:0{i}:00+00:00",))
    conn.execute("""
        INSERT INTO measurements (ts, date, metric, value, device_id, person)
        VALUES ('2026-07-06T10:00:30+00:00', '2026-07-06', 'spo2', 95.0, 'DEV-watch', 'PER-test')
    """)
    conn.commit()

    values, label, device_id = ot.query_spo2(
        conn, datetime(2026, 7, 6, 10, 0), datetime(2026, 7, 6, 10, 5), "PER-test")

    assert device_id == "DEV-o2ring"
    assert values == [96.0, 96.0, 96.0]


def test_query_spo2_no_device_in_window():
    conn = _fresh_conn()
    values, label, device_id = ot.query_spo2(
        conn, datetime(2026, 7, 6, 10, 0), datetime(2026, 7, 6, 10, 5), "PER-test")
    assert values == []
    assert device_id is None


def test_query_bp_returns_rows_with_timestamps():
    conn = _fresh_conn()
    conn.execute("""
        INSERT INTO blood_pressure (ts, date, systolic, diastolic, pulse, person)
        VALUES ('2026-07-06T10:02:00+00:00', '2026-07-06', 118, 76, 60, 'PER-test')
    """)
    conn.commit()

    rows = ot.query_bp(conn, datetime(2026, 7, 6, 10, 0), datetime(2026, 7, 6, 10, 5), "PER-test")

    assert rows == [{"ts": "2026-07-06T10:02:00+00:00", "systolic": 118, "diastolic": 76, "pulse": 60}]


def test_query_bp_excludes_rows_missing_systolic_or_diastolic():
    conn = _fresh_conn()
    conn.execute("""
        INSERT INTO blood_pressure (ts, date, systolic, diastolic, pulse, person)
        VALUES ('2026-07-06T10:02:00+00:00', '2026-07-06', NULL, 76, 60, 'PER-test')
    """)
    conn.commit()

    rows = ot.query_bp(conn, datetime(2026, 7, 6, 10, 0), datetime(2026, 7, 6, 10, 5), "PER-test")
    assert rows == []


def test_query_ppi_beats_filters_implausible_pulse_lengths():
    """detect_stand_jump() needs plausible RR intervals only — sensor noise
    below 300ms or above 2000ms must be filtered out here, same bounds as
    query_ppi()."""
    conn = _fresh_conn()
    for dt, ms in [
        ("2026-07-06T10:00:00.000", 800),
        ("2026-07-06T10:00:01.000", 50),     # implausible, filtered
        ("2026-07-06T10:00:02.000", 5000),   # implausible, filtered
    ]:
        conn.execute("""
            INSERT INTO ppi_raw (datetime, pulse_ms, device, source, person)
            VALUES (?, ?, 'DEV-h10', 'ecg_logger', 'PER-test')
        """, (dt, ms))
    conn.commit()

    beats, label, device_id = ot.query_ppi_beats(
        conn, datetime(2026, 7, 6, 10, 0), datetime(2026, 7, 6, 10, 5), "PER-test")

    assert len(beats) == 1
    assert beats[0][1] == 800
