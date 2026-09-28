# SPDX-License-Identifier: GPL-3.0-or-later
"""
Unit test for migrations/fix_resting_hr_mislabeled_metrics.py.

Uses the real project SCHEMA in an in-memory DB so a future column change in
measurements would fail here instead of silently at runtime.
"""

import itertools
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

from utils.create_schema import SCHEMA
import migrations.fix_resting_hr_mislabeled_metrics as mig


_db_counter = itertools.count()


def _fresh_conn():
    """Named shared-cache in-memory DB, unique per test.

    The migration's own conn.close() call at the end of main() must not tear
    down the database out from under this test's assertions, so the test
    keeps its own connection to the same shared-cache DB open throughout
    while the migration gets a separate connection object it's free to
    close. A unique name per call keeps tests from leaking state into
    each other via a shared cache.
    """
    uri = f"file:fix_resting_hr_test_{next(_db_counter)}?mode=memory&cache=shared"
    conn = sqlite3.connect(uri, uri=True)
    conn.executescript(SCHEMA)
    return conn, uri


def _insert_measurement(conn, ts, metric, value, unit, source_app, person="PER-test"):
    conn.execute("""
        INSERT INTO measurements (ts, date, metric, value, unit, source_app, person)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (ts, ts[:10], metric, value, unit, source_app, person))


def _seed(conn):
    # Oura readiness contributor score, mislabeled as bpm — should be renamed.
    _insert_measurement(conn, "2026-07-06T00:00:00+00:00", "readiness_hr_resting", 72.0, "bpm", "oura_app")
    # Polar profile snapshot, generic name identical to real daily measurements — should be renamed.
    _insert_measurement(conn, "2026-07-06T00:00:00+00:00", "resting_hr", 58.0, "bpm", "polar_connect")
    # Genuine Garmin daily resting HR under the same generic name — must NOT be touched.
    _insert_measurement(conn, "2026-07-06T00:00:00+00:00", "resting_hr", 55.0, "bpm", "garmin_gdpr")
    conn.commit()


def _run_migration(uri, monkeypatch, dry_run=False):
    monkeypatch.setattr(mig, "open_db", lambda: sqlite3.connect(uri, uri=True))
    argv = ["fix_resting_hr_mislabeled_metrics.py"]
    if dry_run:
        argv.append("--dry-run")
    monkeypatch.setattr(sys, "argv", argv)
    try:
        mig.main()
    except SystemExit as e:
        assert e.code == 0


def test_renames_oura_readiness_contributor_and_clears_unit(monkeypatch):
    conn, uri = _fresh_conn()
    _seed(conn)

    _run_migration(uri, monkeypatch)

    row = conn.execute(
        "SELECT metric, unit FROM measurements WHERE source_app='oura_app'"
    ).fetchone()
    assert row == ("readiness_contrib_resting_hr", None)
    assert conn.execute(
        "SELECT COUNT(*) FROM measurements WHERE metric='readiness_hr_resting'"
    ).fetchone()[0] == 0


def test_renames_polar_profile_snapshot_and_keeps_bpm_unit(monkeypatch):
    conn, uri = _fresh_conn()
    _seed(conn)

    _run_migration(uri, monkeypatch)

    row = conn.execute(
        "SELECT metric, unit, value FROM measurements WHERE source_app='polar_connect'"
    ).fetchone()
    assert row == ("polar_profile_resting_hr", "bpm", 58.0)


def test_garmin_resting_hr_untouched(monkeypatch):
    """Found dogfooding: the migration must only rename Polar's mislabeled
    profile-snapshot value — Garmin's genuine daily resting-HR measurements
    share the same generic 'resting_hr' metric name and must survive."""
    conn, uri = _fresh_conn()
    _seed(conn)

    _run_migration(uri, monkeypatch)

    row = conn.execute(
        "SELECT metric, unit, value FROM measurements WHERE source_app='garmin_gdpr'"
    ).fetchone()
    assert row == ("resting_hr", "bpm", 55.0)


def test_dry_run_changes_nothing(monkeypatch):
    conn, uri = _fresh_conn()
    _seed(conn)

    _run_migration(uri, monkeypatch, dry_run=True)

    assert conn.execute(
        "SELECT COUNT(*) FROM measurements WHERE metric='readiness_hr_resting'"
    ).fetchone()[0] == 1
    assert conn.execute(
        "SELECT COUNT(*) FROM measurements WHERE metric='resting_hr' AND source_app='polar_connect'"
    ).fetchone()[0] == 1


def test_idempotent_second_run_is_noop(monkeypatch):
    conn, uri = _fresh_conn()
    _seed(conn)

    _run_migration(uri, monkeypatch)
    _run_migration(uri, monkeypatch)  # re-run after already renamed

    assert conn.execute(
        "SELECT COUNT(*) FROM measurements"
    ).fetchone()[0] == 3
    assert conn.execute(
        "SELECT metric FROM measurements WHERE source_app='oura_app'"
    ).fetchone()[0] == "readiness_contrib_resting_hr"


def test_logs_import(monkeypatch):
    conn, uri = _fresh_conn()
    _seed(conn)

    _run_migration(uri, monkeypatch)

    n = conn.execute(
        "SELECT COUNT(*) FROM import_log WHERE source='fix_resting_hr_mislabeled_metrics'"
    ).fetchone()[0]
    assert n == 2  # one row per RENAMES entry that actually matched
