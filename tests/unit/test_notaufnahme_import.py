# SPDX-License-Identifier: GPL-3.0-or-later
"""
Unit test for import_notaufnahme.py (RKI emergency-department syndromic surveillance).

Network call is mocked (safe to run anywhere, including CI, per
tests/unit/README.md). Uses the real project SCHEMA so a future
ed_syndromic_surveillance column change would fail here instead of
silently at runtime.
"""

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

from utils.create_schema import SCHEMA
import importers.import_notaufnahme as notaufnahme

_SAMPLE_TSV = (
    "date\ted_type\tage_group\tsyndrome\trelative_cases\trelative_cases_7day_ma\t"
    "expected_value\texpected_lowerbound\texpected_upperbound\ted_count\n"
    "2026-07-19\tall\t00+\tARI\t3.9\t4.1\t5.19\t3.2\t7.2\t120\n"
    "2026-07-19\tall\t00+\tHEAT\t1.3\tNA\tNA\tNA\tNA\t120\n"
    "2026-07-19\tall\t0-4\tARI\t8.0\t7.5\t9.0\t6.0\t12.0\t120\n"  # age cohort, must be skipped
    "2026-07-19\tcentral\t00+\tARI\t3.5\t3.6\t5.0\t3.0\t7.0\t80\n"  # ed_type filtered out
    "2026-07-20\tall\t00+\tARI\t3.855\t4.0\t5.191\t3.2\t7.224\t121\n"
)


def _fresh_conn():
    conn = sqlite3.connect(":memory:")
    conn.executescript(SCHEMA)
    return conn


def test_import_filters_to_default_ed_type_and_age_group():
    conn = _fresh_conn()
    inserted = notaufnahme.import_notaufnahme_from_raw(conn, _SAMPLE_TSV, weeks_back=52)

    assert inserted == 3  # 2026-07-19 ARI+HEAT (ed_type=all,00+) + 2026-07-20 ARI
    rows = conn.execute(
        "SELECT date, syndrome, ed_type, age_group FROM ed_syndromic_surveillance "
        "ORDER BY date, syndrome"
    ).fetchall()
    assert rows == [
        ("2026-07-19", "ARI", "all", "00+"),
        ("2026-07-19", "HEAT", "all", "00+"),
        ("2026-07-20", "ARI", "all", "00+"),
    ]


def test_na_expected_values_stored_as_none():
    conn = _fresh_conn()
    notaufnahme.import_notaufnahme_from_raw(conn, _SAMPLE_TSV, weeks_back=52)

    row = conn.execute(
        "SELECT expected_value, expected_lowerbound, expected_upperbound "
        "FROM ed_syndromic_surveillance WHERE syndrome = 'HEAT'"
    ).fetchone()
    assert row == (None, None, None)


def test_import_is_idempotent():
    conn = _fresh_conn()
    notaufnahme.import_notaufnahme_from_raw(conn, _SAMPLE_TSV, weeks_back=52)
    second = notaufnahme.import_notaufnahme_from_raw(conn, _SAMPLE_TSV, weeks_back=52)
    assert second == 0


def test_custom_ed_type_and_age_group_selectable():
    conn = _fresh_conn()
    inserted = notaufnahme.import_notaufnahme_from_raw(
        conn, _SAMPLE_TSV, ed_type="central", age_group="00+", weeks_back=52
    )
    assert inserted == 1
    row = conn.execute("SELECT ed_type, relative_cases FROM ed_syndromic_surveillance").fetchone()
    assert row == ("central", 3.5)


def test_import_notaufnahme_returns_zero_on_fetch_failure(monkeypatch):
    monkeypatch.setattr(notaufnahme, "_fetch_tsv", lambda: None)
    conn = _fresh_conn()
    assert notaufnahme.import_notaufnahme(conn) == 0
