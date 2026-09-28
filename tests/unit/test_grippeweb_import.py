# SPDX-License-Identifier: GPL-3.0-or-later
"""
Unit test for fetch_grippeweb() (scripts/importers/import_outbreak_data.py).

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
    "Meldungen\tSaison\tErkrankung\tAltersgruppe\tRegion\tKalenderwoche\tInzidenz\n"
    "8852\t2025/26\tARE\t00+\tBundesweit\t2026-W27\t2900\n"
    "7598\t2025/26\tILI\t00+\tBundesweit\t2026-W27\t480\n"
    "1643\t2025/26\tARE\t0-14\tBundesweit\t2026-W27\t5000\n"  # age cohort, must be skipped
    "8852\t2025/26\tARE\t00+\tBundesweit\t2026-W28\t3261\n"
    "7598\t2025/26\tILI\t00+\tBundesweit\t2026-W28\t592\n"
)


def _fresh_conn():
    conn = sqlite3.connect(":memory:")
    conn.executescript(SCHEMA)
    return conn


def test_fetch_grippeweb_inserts_only_total_population_rows(monkeypatch):
    monkeypatch.setattr(outbreak, "_fetch_grippeweb_tsv", lambda: _SAMPLE_TSV)
    conn = _fresh_conn()

    inserted = outbreak.fetch_grippeweb(conn, weeks_back=52)

    assert inserted == 4  # 2 weeks x (ARE + ILI), age-cohort row excluded
    rows = conn.execute(
        "SELECT disease, syndrome_slug, date_start FROM outbreak_events "
        "WHERE source = 'rki_grippeweb' ORDER BY date_start, disease"
    ).fetchall()
    assert rows == [
        ("ARE", "generic", "2026-06-29"),
        ("ILI", "influenza", "2026-06-29"),
        ("ARE", "generic", "2026-07-06"),
        ("ILI", "influenza", "2026-07-06"),
    ]


def test_fetch_grippeweb_is_idempotent(monkeypatch):
    monkeypatch.setattr(outbreak, "_fetch_grippeweb_tsv", lambda: _SAMPLE_TSV)
    conn = _fresh_conn()

    outbreak.fetch_grippeweb(conn, weeks_back=52)
    second_run = outbreak.fetch_grippeweb(conn, weeks_back=52)

    assert second_run == 0
    total = conn.execute(
        "SELECT COUNT(*) FROM outbreak_events WHERE source = 'rki_grippeweb'"
    ).fetchone()[0]
    assert total == 4


def test_fetch_grippeweb_respects_weeks_back_window(monkeypatch):
    monkeypatch.setattr(outbreak, "_fetch_grippeweb_tsv", lambda: _SAMPLE_TSV)
    conn = _fresh_conn()

    inserted = outbreak.fetch_grippeweb(conn, weeks_back=1)

    assert inserted == 2  # only the most recent week (2026-W28)


def test_fetch_grippeweb_returns_zero_on_fetch_failure(monkeypatch):
    monkeypatch.setattr(outbreak, "_fetch_grippeweb_tsv", lambda: None)
    conn = _fresh_conn()

    assert outbreak.fetch_grippeweb(conn) == 0


def test_grippeweb_registered_as_default_source():
    assert "grippeweb" in outbreak._ALL_SOURCES_DEFAULT
    assert "grippeweb" in outbreak._FETCHERS
    assert outbreak._FETCHERS["grippeweb"][0] is outbreak.fetch_grippeweb
