# SPDX-License-Identifier: GPL-3.0-or-later
"""
Unit test for fetch_are_konsultationsinzidenz() (scripts/importers/import_outbreak_data.py).

Network call is mocked (this file lives in tests/unit/ — safe to run
anywhere, including CI, per tests/unit/README.md). Uses the real project
SCHEMA so a future outbreak_events column change would fail here instead of
silently at runtime.
"""

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

from utils.create_schema import SCHEMA
import importers.import_outbreak_data as outbreak

_SAMPLE_TSV = (
    "Saison\tKalenderwoche\tBundesland\tBundesland_ID\tAltersgruppe\tARE_Konsultationsinzidenz\n"
    "2025/26\t2026-W27\tBayern\t9\t00+\t564\n"
    "2025/26\t2026-W27\tBundesweit\t0\t00+\t610\n"
    "2025/26\t2026-W27\tBayern\t9\t0-4\t2200\n"  # age cohort, must be skipped
    "2025/26\t2026-W28\tBayern\t9\t00+\t624\n"
    "2025/26\t2026-W28\tBundesweit\t0\t00+\t640\n"
)


def _fresh_conn():
    conn = sqlite3.connect(":memory:")
    conn.executescript(SCHEMA)
    return conn


def test_fetch_are_konsultation_inserts_only_total_population_rows(monkeypatch):
    monkeypatch.setattr(outbreak, "_fetch_are_konsultationsinzidenz_tsv", lambda: _SAMPLE_TSV)
    conn = _fresh_conn()

    inserted = outbreak.fetch_are_konsultationsinzidenz(conn, weeks_back=52)

    assert inserted == 4  # 2 weeks x (Bayern + Bundesweit), age-cohort row excluded
    rows = conn.execute(
        "SELECT region, date_start FROM outbreak_events "
        "WHERE source = 'rki_are_konsultationsinzidenz' ORDER BY date_start, region"
    ).fetchall()
    assert rows == [
        ("Bayern", "2026-06-29"),
        ("Bundesweit", "2026-06-29"),
        ("Bayern", "2026-07-06"),
        ("Bundesweit", "2026-07-06"),
    ]


def test_fetch_are_konsultation_is_idempotent(monkeypatch):
    monkeypatch.setattr(outbreak, "_fetch_are_konsultationsinzidenz_tsv", lambda: _SAMPLE_TSV)
    conn = _fresh_conn()

    outbreak.fetch_are_konsultationsinzidenz(conn, weeks_back=52)
    second_run = outbreak.fetch_are_konsultationsinzidenz(conn, weeks_back=52)

    assert second_run == 0


def test_fetch_are_konsultation_returns_zero_on_fetch_failure(monkeypatch):
    monkeypatch.setattr(outbreak, "_fetch_are_konsultationsinzidenz_tsv", lambda: None)
    conn = _fresh_conn()

    assert outbreak.fetch_are_konsultationsinzidenz(conn) == 0


def test_are_konsultation_registered_as_default_source():
    assert "are_konsultation" in outbreak._ALL_SOURCES_DEFAULT
    assert "are_konsultation" in outbreak._FETCHERS
    assert outbreak._FETCHERS["are_konsultation"][0] is outbreak.fetch_are_konsultationsinzidenz


def test_both_full_history_sources_registered():
    assert {"grippeweb", "are_konsultation"} <= set(outbreak._FULL_HISTORY_CAPABLE)
