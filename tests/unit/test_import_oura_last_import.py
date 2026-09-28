# SPDX-License-Identifier: GPL-3.0-or-later
"""
Unit test for importers/import_oura.py::get_last_import.

Found dogfooding: import_sleep() writes a sessions row for every day even
when Oura's daily_sleep endpoint returns no real HRV/sleep data for it
(schema change stopped returning raw values, only scores) — checking
sessions.date alone made a day look "done" before import_sleep_sessions()
(which pulls the actual HRV data from the /sleep endpoint) ever processed
it, since both functions share the same start/end window. Fixed by
checking the real HRV data state (measurements) instead of sessions.
"""

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

from utils.create_schema import SCHEMA
import importers.import_oura as io


def _fresh_conn():
    conn = sqlite3.connect(":memory:")
    conn.executescript(SCHEMA)
    return conn


def test_none_when_nothing_imported():
    conn = _fresh_conn()
    assert io.get_last_import(conn) is None


def test_ignores_session_only_days_with_no_real_hrv_data():
    """A sessions row exists (written unconditionally by import_sleep()) but
    no hrv_rmssd measurement — must NOT count as imported."""
    conn = _fresh_conn()
    conn.execute("""
        INSERT INTO sessions (id, type, ts_start, date, person, source_app)
        VALUES ('s1', 'sleep', '2026-07-08T00:00:00+00:00', '2026-07-08', 'PER-test', 'oura_app')
    """)
    conn.commit()

    assert io.get_last_import(conn) is None


def test_picks_latest_date_with_real_hrv_data():
    conn = _fresh_conn()
    conn.execute("""
        INSERT INTO measurements (ts, date, metric, value, source_app, person)
        VALUES ('2026-07-06T00:00:00+00:00', '2026-07-06', 'hrv_rmssd', 42.0, 'oura_app', 'PER-test')
    """)
    conn.execute("""
        INSERT INTO measurements (ts, date, metric, value, source_app, person)
        VALUES ('2026-07-09T00:00:00+00:00', '2026-07-09', 'hrv_rmssd', 39.0, 'oura_app', 'PER-test')
    """)
    conn.commit()

    assert io.get_last_import(conn) == "2026-07-09"


def test_ignores_other_sources_hrv_data():
    conn = _fresh_conn()
    conn.execute("""
        INSERT INTO measurements (ts, date, metric, value, source_app, person)
        VALUES ('2026-07-09T00:00:00+00:00', '2026-07-09', 'hrv_rmssd', 39.0, 'polar_connect', 'PER-test')
    """)
    conn.commit()

    assert io.get_last_import(conn) is None
