# SPDX-License-Identifier: GPL-3.0-or-later
"""
Unit test for compute/compute_canonical.py::build_resting_hr.

Found dogfooding: build_resting_hr() used to include readiness_hr_resting
(an Oura readiness score, not a bpm value) and resting_hr (Polar's rarely
updated profile snapshot, not a daily measurement) as candidate sources —
both have since been renamed by import_oura.py/import_polar.py and are no
longer legitimate resting-HR candidates. hr_lowest (Oura's genuine nightly
HR minimum) takes resting_hr's place as a real daily measurement.
"""

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

from utils.create_schema import SCHEMA
import compute.compute_canonical as cc


def _fresh_conn():
    conn = sqlite3.connect(":memory:")
    conn.executescript(SCHEMA)
    cc.setup_tables(conn)
    return conn


def _insert_measurement(conn, ts, metric, value, source_app, person="PER-test"):
    conn.execute("""
        INSERT INTO measurements (ts, date, metric, value, unit, source_app, person)
        VALUES (?, ?, ?, ?, 'bpm', ?, ?)
    """, (ts, ts[:10], metric, value, source_app, person))


def test_hr_lowest_is_a_candidate_source():
    conn = _fresh_conn()
    _insert_measurement(conn, "2026-07-06T00:00:00+00:00", "hr_lowest", 48.0, "oura_app")
    conn.commit()

    n = cc.build_resting_hr(conn, "PER-test")

    assert n == 1
    row = conn.execute(f"SELECT value, source FROM {cc._CANONICAL_TABLE}").fetchone()
    assert row == (48.0, "oura_app")


def test_renamed_oura_readiness_score_no_longer_a_candidate():
    """readiness_hr_resting is a 0-100 readiness-contributor score, not a bpm
    value — must never surface as resting_heart_rate even if present."""
    conn = _fresh_conn()
    _insert_measurement(conn, "2026-07-06T00:00:00+00:00", "readiness_hr_resting", 72.0, "oura_app")
    conn.commit()

    n = cc.build_resting_hr(conn, "PER-test")

    assert n == 0


def test_renamed_polar_profile_snapshot_no_longer_a_candidate():
    """resting_hr under source_app='polar_connect' used to be Polar's rarely
    updated HR-zone profile field, not a daily measurement — must never
    surface as resting_heart_rate even if present under the old name."""
    conn = _fresh_conn()
    _insert_measurement(conn, "2026-07-06T00:00:00+00:00", "resting_hr", 58.0, "polar_connect")
    conn.commit()

    n = cc.build_resting_hr(conn, "PER-test")

    assert n == 0


def test_genuine_resting_heart_rate_metric_still_a_candidate():
    conn = _fresh_conn()
    _insert_measurement(conn, "2026-07-06T00:00:00+00:00", "resting_heart_rate", 60.0, "garmin_gdpr")
    conn.commit()

    n = cc.build_resting_hr(conn, "PER-test")

    assert n == 1
    row = conn.execute(f"SELECT value, source FROM {cc._CANONICAL_TABLE}").fetchone()
    assert row == (60.0, "garmin_gdpr")
