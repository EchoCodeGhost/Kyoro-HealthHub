# SPDX-License-Identifier: GPL-3.0-or-later
"""
Unit test for importers/import_polar_accesslink.py::_get_last_import.

Found dogfooding: devices without AccessLink sleep/nightly-recharge support
(e.g. Polar Loop, which gets a permanent 404 on those endpoints) never
produce a sessions row for this source, so checking sessions alone made
--update fall back to data_start every time and rescan everything, even
though import_activities() writes new measurements rows daily. Fixed by
taking the max across both tables.
"""

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

from utils.create_schema import SCHEMA
import importers.import_polar_accesslink as ipa


def _fresh_conn():
    conn = sqlite3.connect(":memory:")
    conn.executescript(SCHEMA)
    return conn


def test_last_import_none_when_nothing_imported():
    conn = _fresh_conn()
    assert ipa._get_last_import(conn) is None


def test_last_import_falls_back_to_measurements_without_sleep_sessions():
    """A device like Polar Loop with no AccessLink sleep support: only
    measurements rows exist, sessions stays empty for this source."""
    conn = _fresh_conn()
    conn.execute("""
        INSERT INTO measurements (ts, date, metric, value, source_app, person)
        VALUES ('2026-07-08T00:00:00+00:00', '2026-07-08', 'steps', 500, ?, 'PER-test')
    """, (ipa.SOURCE,))
    conn.commit()

    assert ipa._get_last_import(conn) == "2026-07-08"


def test_last_import_picks_the_later_of_sessions_and_measurements():
    conn = _fresh_conn()
    conn.execute("""
        INSERT INTO sessions (id, type, ts_start, date, person, source_app)
        VALUES ('s1', 'sleep', '2026-07-05T00:00:00+00:00', '2026-07-05', 'PER-test', ?)
    """, (ipa.SOURCE,))
    conn.execute("""
        INSERT INTO measurements (ts, date, metric, value, source_app, person)
        VALUES ('2026-07-09T00:00:00+00:00', '2026-07-09', 'steps', 500, ?, 'PER-test')
    """, (ipa.SOURCE,))
    conn.commit()

    assert ipa._get_last_import(conn) == "2026-07-09"


def test_last_import_ignores_other_sources(monkeypatch):
    conn = _fresh_conn()
    conn.execute("""
        INSERT INTO measurements (ts, date, metric, value, source_app, person)
        VALUES ('2026-07-09T00:00:00+00:00', '2026-07-09', 'steps', 500, 'garmin_gdpr', 'PER-test')
    """)
    conn.commit()

    assert ipa._get_last_import(conn) is None
