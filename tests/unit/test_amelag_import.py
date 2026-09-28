# SPDX-License-Identifier: GPL-3.0-or-later
"""
Unit test for import_amelag.py (RKI/UBA AMELAG wastewater surveillance).

Network calls are mocked (safe to run anywhere, including CI, per
tests/unit/README.md). Uses the real project SCHEMA so a future
wastewater_amelag column change would fail here instead of silently at
runtime.
"""

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

from utils.create_schema import SCHEMA
import importers.import_amelag as amelag

_NATIONAL_TSV = (
    "datum\tn\tanteil_bev\tviruslast\tviruslast_normalisiert\tvorhersage\t"
    "obere_schranke\tuntere_schranke\ttyp\n"
    "2026-07-01\t67\t0.25\t1773.85\t2169.02\t1751.27\t2113.59\t1451.07\tSARS-CoV-2\n"
    "2026-07-08\t64\t0.24\t2117.4\t1993.17\t1936.05\t2507.13\t1495.05\tSARS-CoV-2\n"
)

_SITES_TSV = (
    "standort\tbundesland\tdatum\tviruslast\tviruslast_normalisiert\tvorhersage\t"
    "obere_schranke\tuntere_schranke\teinwohner\tlaborwechsel\ttyp\tunter_bg\n"
    "Freising\tBY\t2026-07-06\t26800\t28800\t37151.13\t810534.45\t1702.83\t51617\tnein\tSARS-CoV-2\tnein\n"
    "Aachen\tNW\t2026-07-06\t250\t201.27\t249.99\t328.69\t190.14\t206424\tnein\tInfluenza A\tja\n"  # not BY, must be skipped
    "Freising\tBY\t2026-07-06\tNA\tNA\t10505.03\t84039.67\t1313.13\t51617\tnein\tInfluenza A\tNA\n"
)


def _fresh_conn():
    conn = sqlite3.connect(":memory:")
    conn.executescript(SCHEMA)
    return conn


def test_national_import_filters_by_window_and_stores_all_fields():
    conn = _fresh_conn()
    inserted = amelag.import_amelag_national_from_raw(conn, _NATIONAL_TSV, weeks_back=52)

    assert inserted == 2
    row = conn.execute(
        "SELECT level, site, virus, viral_load, population_share FROM wastewater_amelag "
        "WHERE date = '2026-07-08'"
    ).fetchone()
    assert row == ("national", None, "SARS-CoV-2", 2117.4, 0.24)


def test_national_import_is_idempotent():
    conn = _fresh_conn()
    amelag.import_amelag_national_from_raw(conn, _NATIONAL_TSV, weeks_back=52)
    second = amelag.import_amelag_national_from_raw(conn, _NATIONAL_TSV, weeks_back=52)
    assert second == 0


def test_sites_import_filters_to_selected_bundesland_only():
    conn = _fresh_conn()
    inserted = amelag.import_amelag_sites_from_raw(conn, _SITES_TSV, bundesland="BY", weeks_back=52)

    assert inserted == 2  # both Freising rows, Aachen (NW) excluded
    sites = conn.execute("SELECT DISTINCT site FROM wastewater_amelag").fetchall()
    assert sites == [("Freising",)]


def test_sites_import_handles_na_values_as_none():
    conn = _fresh_conn()
    amelag.import_amelag_sites_from_raw(conn, _SITES_TSV, bundesland="BY", weeks_back=52)

    row = conn.execute(
        "SELECT viral_load, below_detection_limit, population_covered FROM wastewater_amelag "
        "WHERE virus = 'Influenza A'"
    ).fetchone()
    assert row == (None, None, 51617)


def test_sites_import_parses_below_detection_limit_flag():
    conn = _fresh_conn()
    amelag.import_amelag_sites_from_raw(conn, _SITES_TSV, bundesland="BY", weeks_back=52)

    row = conn.execute(
        "SELECT below_detection_limit FROM wastewater_amelag WHERE virus = 'SARS-CoV-2'"
    ).fetchone()
    assert row == (0,)  # 'nein' -> 0


def test_import_amelag_combines_both_files(monkeypatch):
    monkeypatch.setattr(amelag, "_fetch_tsv", lambda url: (
        _NATIONAL_TSV if url == amelag._NATIONAL_URL else _SITES_TSV
    ))
    conn = _fresh_conn()

    total = amelag.import_amelag(conn, bundesland="BY", weeks_back=52)

    assert total == 4  # 2 national + 2 BY site rows


def test_default_bundesland_derived_from_home_coordinates(monkeypatch):
    """No hardcoded federal state — must come from the configured home
    coordinate (found dogfooding: the original default silently hardcoded
    Bavaria, which breaks for anyone else using the project)."""
    class FakeCfg:
        home_lat, home_lon = 51.23, 6.77  # Nordrhein-Westfalen centroid
    monkeypatch.setattr(amelag, "_Cfg", FakeCfg)

    assert amelag._default_bundesland() == "NW"


def test_default_bundesland_none_when_no_home_coordinate_configured(monkeypatch):
    class FakeCfg:
        home_lat, home_lon = None, None
    monkeypatch.setattr(amelag, "_Cfg", FakeCfg)

    assert amelag._default_bundesland() is None


def test_import_amelag_skips_sites_when_no_bundesland_available(monkeypatch):
    """Must degrade gracefully (national only) instead of crashing or
    silently defaulting to one specific state when nothing is configured."""
    monkeypatch.setattr(amelag, "_fetch_tsv", lambda url: (
        _NATIONAL_TSV if url == amelag._NATIONAL_URL else _SITES_TSV
    ))
    monkeypatch.setattr(amelag, "_default_bundesland", lambda: None)
    conn = _fresh_conn()

    total = amelag.import_amelag(conn, bundesland=None, weeks_back=52)

    assert total == 2  # national only, no site rows
    sites = conn.execute("SELECT COUNT(*) FROM wastewater_amelag WHERE level = 'site'").fetchone()[0]
    assert sites == 0
