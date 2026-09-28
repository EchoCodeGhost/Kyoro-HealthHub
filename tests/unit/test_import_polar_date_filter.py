# SPDX-License-Identifier: GPL-3.0-or-later
"""
Unit test for importers/import_polar.py::_in_range and _get_last_import.

Found dogfooding: --update/--from/--to were pure no-op arguments — every run
always reparsed the entire archive (INSERT OR IGNORE just made the
redundant work invisible, not faster). This covers the date-window helper
and the multi-table --update watermark query that made the flags actually
effective.
"""

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

from utils.create_schema import SCHEMA
import importers.import_polar as ip


def _fresh_conn():
    conn = sqlite3.connect(":memory:")
    conn.executescript(SCHEMA)
    ip.setup_db(conn)
    return conn


# ── _in_range ────────────────────────────────────────────────────────────────

def test_in_range_no_bounds_always_true():
    assert ip._in_range("2026-07-06", None, None) is True


def test_in_range_below_date_from():
    assert ip._in_range("2026-07-05", "2026-07-06", None) is False


def test_in_range_above_date_to():
    assert ip._in_range("2026-07-07", None, "2026-07-06") is False


def test_in_range_within_bounds():
    assert ip._in_range("2026-07-06", "2026-07-01", "2026-07-10") is True


def test_in_range_boundary_dates_are_inclusive():
    assert ip._in_range("2026-07-01", "2026-07-01", "2026-07-10") is True
    assert ip._in_range("2026-07-10", "2026-07-01", "2026-07-10") is True


# ── _get_last_import ─────────────────────────────────────────────────────────

def test_get_last_import_none_when_nothing_imported():
    conn = _fresh_conn()
    assert ip._get_last_import(conn) is None


def test_get_last_import_picks_latest_across_measurements_and_sessions():
    """Some Polar data types (e.g. PPI/HRV) never produce a sessions row, so
    --update must not rely on sessions alone — a later date sitting only in
    measurements must win."""
    conn = _fresh_conn()
    conn.execute("""
        INSERT INTO sessions (id, type, ts_start, date, person, source_app)
        VALUES ('s1', 'sleep', '2026-07-05T00:00:00+00:00', '2026-07-05', 'PER-test', 'polar_connect')
    """)
    conn.execute("""
        INSERT INTO measurements (ts, date, metric, value, source_app, person)
        VALUES ('2026-07-08T00:00:00+00:00', '2026-07-08', 'steps', 500, 'polar_connect', 'PER-test')
    """)
    conn.commit()

    assert ip._get_last_import(conn) == "2026-07-08"


def test_get_last_import_finds_watermark_in_nightly_hrv_only():
    conn = _fresh_conn()
    conn.execute("""
        INSERT INTO polar_nightly_hrv (date, rmssd_ms, person)
        VALUES ('2026-07-09', 45.0, 'PER-test')
    """)
    conn.commit()

    assert ip._get_last_import(conn) == "2026-07-09"
