# SPDX-License-Identifier: GPL-3.0-or-later
"""
Unit test for analyse_background_infection_activity.py.

Uses the real project SCHEMA in an in-memory DB so a future column change in
outbreak_events/wastewater_amelag/ed_syndromic_surveillance would fail here
instead of silently at runtime.
"""

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

from utils.create_schema import SCHEMA
import analysis.infectious.analyse_background_infection_activity as bia


def _fresh_conn():
    conn = sqlite3.connect(":memory:")
    conn.executescript(SCHEMA)
    return conn


def test_iso_week_formats_correctly():
    assert bia._iso_week("2026-07-06") == "2026-W28"


def test_shift_iso_week_moves_by_whole_weeks():
    assert bia._shift_iso_week("2026-W28", -1) == "2026-W27"
    assert bia._shift_iso_week("2026-W28", 0) == "2026-W28"


def test_home_bundesland_derived_from_config_not_hardcoded(monkeypatch):
    """Found dogfooding: must never hardcode a specific federal state — has
    to come from whatever the installation's own home coordinate is."""
    class FakeCfg:
        home_lat, home_lon = 51.23, 6.77  # Nordrhein-Westfalen
        data_start = None
        analyses_dir = Path("/tmp")

    monkeypatch.setattr(bia, "_cfg", FakeCfg())
    assert bia.home_bundesland() == ("Nordrhein-Westfalen", "NW")


def test_home_bundesland_none_without_home_coordinate(monkeypatch):
    class FakeCfg:
        home_lat, home_lon = None, None
        data_start = None
        analyses_dir = Path("/tmp")

    monkeypatch.setattr(bia, "_cfg", FakeCfg())
    assert bia.home_bundesland() == (None, None)


def test_load_grippeweb_extracts_incidence_from_title():
    conn = _fresh_conn()
    now = "2026-07-08T00:00:00+00:00"
    conn.execute("""
        INSERT INTO outbreak_events
        (source, disease, syndrome_slug, country, country_iso, region,
         date_reported, date_start, severity, title, fetched_at, person)
        VALUES ('rki_grippeweb', 'ARE', 'generic', 'Deutschland', 'DE', 'Bundesweit',
                '2026-07-06', '2026-07-06', 'high',
                'ARE (RKI GrippeWeb 2026-W28) — Bundesweit: 3261/100.000', ?, 'PER-test')
    """, (now,))
    conn.commit()

    series = bia.load_grippeweb(conn, "2026-01-01", "2026-12-31")

    assert series["2026-W28"]["grippeweb_are"] == 3261.0


def test_load_are_konsultation_includes_bundesweit_and_home_region(monkeypatch):
    class FakeCfg:
        home_lat, home_lon = 48.14, 11.58  # Bayern
        data_start = None
        analyses_dir = Path("/tmp")
    monkeypatch.setattr(bia, "_cfg", FakeCfg())

    conn = _fresh_conn()
    now = "2026-07-08T00:00:00+00:00"
    for region in ("Bundesweit", "Bayern", "Sachsen"):
        conn.execute("""
            INSERT INTO outbreak_events
            (source, disease, syndrome_slug, country, country_iso, region,
             date_reported, date_start, severity, title, fetched_at, person)
            VALUES ('rki_are_konsultationsinzidenz', 'ARE', 'generic', 'Deutschland', 'DE', ?,
                    '2026-07-06', '2026-07-06', 'medium',
                    ?, ?, 'PER-test')
        """, (region, f"ARE (RKI Konsultationsinzidenz 2026-W28) — {region}: 600/100.000", now))
    conn.commit()

    week_region = {"2026-W28": ("Bayern", "BY")}
    series = bia.load_are_konsultation(conn, "2026-01-01", "2026-12-31", week_region)

    week = series["2026-W28"]
    assert "are_konsultation_bundesweit" in week
    assert "are_konsultation_heimat" in week  # Bayern, not Sachsen
    assert len(week) == 2  # Sachsen must not leak in


def test_load_rki_survstat_includes_deutschland_and_home_region(monkeypatch):
    class FakeCfg:
        home_lat, home_lon = 48.14, 11.58  # Bayern
        data_start = None
        analyses_dir = Path("/tmp")
    monkeypatch.setattr(bia, "_cfg", FakeCfg())

    conn = _fresh_conn()
    now = "2026-07-22T00:00:00+00:00"
    for region in ("Deutschland", "Bayern", "Sachsen"):
        conn.execute("""
            INSERT INTO outbreak_events
            (source, disease, syndrome_slug, country, country_iso, region,
             date_reported, date_start, severity, title, fetched_at, person)
            VALUES ('rki_survstat', 'Borreliose', 'borreliose', 'Deutschland', 'DE', ?,
                    '2026-07-20', '2026-07-20', 'medium', ?, ?, 'PER-test')
        """, (region, f"Borreliose (RKI SurvStat 2026-W30) — {region}: 24 Fälle", now))
    conn.commit()

    week_region = {"2026-W30": ("Bayern", "BY")}
    series = bia.load_rki_survstat(conn, "2026-01-01", "2026-12-31", week_region)

    week = series["2026-W30"]
    assert "rki_survstat_bundesweit_borreliose" in week
    assert "rki_survstat_heimat_borreliose" in week  # Bayern, not Sachsen
    assert len(week) == 2  # Sachsen must not leak in


def test_rki_disease_key_slugifies_umlauts_and_punctuation():
    assert bia._rki_disease_key("FSME (Frühsommer-Meningoenzephalitis)") == \
        "fsme_fruehsommer_meningoenzephalitis"
    assert bia._rki_disease_key("Q-Fieber") == "q_fieber"


def test_load_amelag_splits_national_and_home_site(monkeypatch):
    class FakeCfg:
        home_lat, home_lon = 48.14, 11.58  # Bayern -> BY
        data_start = None
        analyses_dir = Path("/tmp")
    monkeypatch.setattr(bia, "_cfg", FakeCfg())

    conn = _fresh_conn()
    conn.execute("""
        INSERT INTO wastewater_amelag
        (date, level, site, bundesland, virus, viral_load_normalized, person)
        VALUES ('2026-07-06', 'national', NULL, NULL, 'SARS-CoV-2', 2000.0, 'PER-test')
    """)
    conn.execute("""
        INSERT INTO wastewater_amelag
        (date, level, site, bundesland, virus, viral_load_normalized, person)
        VALUES ('2026-07-06', 'site', 'Freising', 'BY', 'SARS-CoV-2', 3000.0, 'PER-test')
    """)
    conn.execute("""
        INSERT INTO wastewater_amelag
        (date, level, site, bundesland, virus, viral_load_normalized, person)
        VALUES ('2026-07-06', 'site', 'Aachen', 'NW', 'SARS-CoV-2', 9999.0, 'PER-test')
    """)
    conn.commit()

    week_region = {"2026-W28": ("Bayern", "BY")}
    series = bia.load_amelag(conn, "2026-01-01", "2026-12-31", week_region)

    week = series["2026-W28"]
    assert week["amelag_national_sars-cov-2"] == 2000.0
    assert week["amelag_heimat_sars-cov-2"] == 3000.0  # only Freising (BY), not Aachen (NW)


def test_load_ed_surveillance_averages_per_week():
    conn = _fresh_conn()
    conn.execute("""
        INSERT INTO ed_syndromic_surveillance
        (date, ed_type, age_group, syndrome, relative_cases, person)
        VALUES ('2026-07-06', 'all', '00+', 'ARI', 3.0, 'PER-test')
    """)
    conn.execute("""
        INSERT INTO ed_syndromic_surveillance
        (date, ed_type, age_group, syndrome, relative_cases, person)
        VALUES ('2026-07-07', 'all', '00+', 'ARI', 5.0, 'PER-test')
    """)
    conn.commit()

    series = bia.load_ed_surveillance(conn, "2026-01-01", "2026-12-31")

    assert series["2026-W28"]["notaufnahme_ari"] == 4.0


def test_load_symptom_burden_counts_and_averages_per_week():
    conn = _fresh_conn()
    conn.execute("INSERT INTO symptoms (date, symptom, value_num, person) VALUES "
                 "('2026-07-06', 'Fatigue', 3.0, 'PER-test')")
    conn.execute("INSERT INTO symptoms (date, symptom, value_num, person) VALUES "
                 "('2026-07-07', 'Pain', 5.0, 'PER-test')")
    conn.commit()

    series = bia.load_symptom_burden(conn, "2026-01-01", "2026-12-31", "PER-test")

    week = series["2026-W28"]
    assert week["symptom_count"] == 2
    assert week["symptom_severity"] == 4.0


def test_load_symptom_burden_excludes_zero_value_rows():
    """Found dogfooding: structured diary imports write every queried field as
    its own row even when nothing was present (value_num=0) — a day with an
    85-field questionnaire import isn't "85 symptoms", raw row-counting was
    measuring questionnaire size, not actual symptom burden."""
    conn = _fresh_conn()
    conn.execute("INSERT INTO symptoms (date, symptom, value_num, person) VALUES "
                 "('2026-07-06', 'Fatigue', 3.0, 'PER-test')")
    conn.execute("INSERT INTO symptoms (date, symptom, value_num, person) VALUES "
                 "('2026-07-06', 'Nasenspray', 0.0, 'PER-test')")
    conn.execute("INSERT INTO symptoms (date, symptom, value_num, person) VALUES "
                 "('2026-07-06', 'Arztbesuch', NULL, 'PER-test')")
    conn.commit()

    series = bia.load_symptom_burden(conn, "2026-01-01", "2026-12-31", "PER-test")

    assert series["2026-W28"]["symptom_count"] == 1
    assert series["2026-W28"]["symptom_severity"] == 3.0


def test_load_symptom_burden_excludes_non_symptom_categories():
    """Treatment/cycle-tracking/medication entries must not count as symptom
    burden — found dogfooding: years of pure cycle-tracking (womanlog) would
    otherwise dilute the actual symptom signal."""
    conn = _fresh_conn()
    conn.execute("INSERT INTO symptoms (date, symptom, value_num, category, person) VALUES "
                 "('2026-07-06', 'Fatigue', 3.0, 'symptom', 'PER-test')")
    conn.execute("INSERT INTO symptoms (date, symptom, value_num, category, person) VALUES "
                 "('2026-07-06', 'Cycle day', 5.0, 'womanlog', 'PER-test')")
    conn.execute("INSERT INTO symptoms (date, symptom, value_num, category, person) VALUES "
                 "('2026-07-06', 'Ibuprofen given', 1.0, 'behandlung', 'PER-test')")
    conn.commit()

    series = bia.load_symptom_burden(conn, "2026-01-01", "2026-12-31", "PER-test")

    assert series["2026-W28"]["symptom_count"] == 1
    assert series["2026-W28"]["symptom_severity"] == 3.0


def test_symptom_tracking_start_ignores_non_symptom_categories():
    """Must not use an old womanlog-only entry as the tracking start date —
    that's cycle tracking, not symptom tracking."""
    conn = _fresh_conn()
    conn.execute("INSERT INTO symptoms (date, symptom, value_num, category, person) VALUES "
                 "('2017-09-25', 'Cycle day', 1.0, 'womanlog', 'PER-test')")
    conn.execute("INSERT INTO symptoms (date, symptom, value_num, category, person) VALUES "
                 "('2026-05-15', 'Fatigue', 5.0, 'symptom', 'PER-test')")
    conn.commit()

    assert bia.symptom_tracking_start(conn, "PER-test") == "2026-05-15"


def test_infection_events_in_context_only_includes_exact_dated_events_with_data():
    background = {"2020-W05": {"grippeweb_are": 7241.0}}
    events = [
        {"date": "2020-02-01", "name": "Influenza A"},       # exact date, has data
        {"date": "2019-01", "name": "~ungefähres Datum"},    # not exact, must be skipped
        {"date": "2010-01-01", "name": "vor jeder Hintergrundserie"},  # exact but no data
    ]

    result = bia.infection_events_in_context(events, background)

    assert len(result) == 1
    assert result[0]["name"] == "Influenza A"
    assert result[0]["background"] == {"grippeweb_are": 7241.0}


def test_correlate_needs_minimum_overlap_to_report():
    """Fewer than 8 overlapping weeks -> no correlation reported (too noisy)."""
    background = {f"2026-W{i:02d}": {"x": float(i)} for i in range(1, 5)}
    symptoms = {f"2026-W{i:02d}": {"y": float(i)} for i in range(1, 5)}

    result = bia.correlate(background, symptoms, lag_weeks=0)

    assert result == {}
