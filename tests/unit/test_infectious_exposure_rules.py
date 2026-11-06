# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Tests for exposure rules in the infectious analyses and billed-diagnosis import.

@tier        unit
@purpose.de  Prüft Vorwärts-Geocoding von Reiseeinträgen, die regelbasierte
             Syndrom-Einstufung und die Auswertung der KBV-Kennzeichen.
@purpose.en  Checks forward geocoding of travel entries, the rule-based syndrome
             classification, and decoding of KBV markers.
@method.de   Netzwerkzugriffe werden ersetzt; alle Eingaben sind erfunden.
@method.en   Network access is replaced; all inputs are made up.
@reads       (keine)
@writes      (keine)
@limits.de   Keine echten Personen-, Reise- oder Labordaten
@limits.en   No real personal, travel or lab data
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))


def _ranked(**overrides):
    base = {"slug": "beispiel", "score": 10.0, "coverage_pct": 80.0, "n_matched": 8,
            "n_profil": 10, "lab_hints": [], "lab_ausstehend": [],
            "prior_tier": None, "prior_note": None}
    base.update(overrides)
    return base


@pytest.fixture
def forward_calls(monkeypatch):
    import analysis.infectious.analyse_pathogen_exposure as ape

    calls = []

    def _fake_forward(query, cache):
        calls.append(query)
        return {"lat": 1.5, "lon": 2.5}

    monkeypatch.setattr(ape, "_nominatim_forward", _fake_forward)
    monkeypatch.setattr(ape, "_nominatim", lambda lat, lon, cache: {})
    monkeypatch.setattr(ape, "_climate_zone", lambda *a, **k: None)
    return ape, calls


def test_country_only_stay_is_not_geocoded(forward_calls):
    ape, calls = forward_calls
    stay = ape._enrich_stay(ape.Stay("2020-01-01", "2020-01-05", country="Beispielland"), {})
    assert calls == []
    assert stay.lat is None


def test_city_stay_is_geocoded_with_most_specific_first(forward_calls):
    ape, calls = forward_calls
    stay = ape._enrich_stay(
        ape.Stay("2020-01-01", "2020-01-05", country="Beispielland", city="Musterstadt"), {})
    assert calls == ["Musterstadt, Beispielland"]
    assert stay.lat == 1.5


def test_confirmed_exposure_outranks_negative_lab():
    from analysis.infectious.analyse_postinfectious_diagnose import personalisierte_einordnung
    tier, _ = personalisierte_einordnung(
        _ranked(prior_tier="confirmed", prior_note="Beispiel", lab_hints=["✗ Marker negativ (2020-01-01)"]),
        0.5, 365)
    assert tier == "Hoch"


def test_negative_lab_with_open_tests_is_not_excluded():
    from analysis.infectious.analyse_postinfectious_diagnose import personalisierte_einordnung
    tier, text = personalisierte_einordnung(
        _ranked(lab_hints=["✗ Marker negativ (2020-01-01)"], lab_ausstehend=["Weiterer Test"]), 0.5, 365)
    assert tier == "Vollständige Testung ausstehend"
    assert "KEIN endgültiger Ausschluss" in text


def test_csf_note_makes_no_claim_about_the_person():
    from analysis.infectious.analyse_postinfectious_diagnose import personalisierte_einordnung
    _, text = personalisierte_einordnung(
        _ranked(slug="neuroborreliose", lab_hints=["✗ Marker negativ (2020-01-01)"],
                lab_ausstehend=["Weiterer Test"]), 0.5, 365)
    assert "Falls sie noch nicht erfolgt ist" in text
    assert "gab es bisher nicht" not in text


def test_few_symptom_days_exclude_the_score():
    from analysis.infectious.analyse_postinfectious_diagnose import personalisierte_einordnung
    tier, _ = personalisierte_einordnung(_ranked(), 0.5, 3)
    assert tier == "Unklar (zu wenig Daten)"


def test_unconfigured_country_has_no_prevalence(monkeypatch):
    import analysis.infectious.analyse_postinfectious_diagnose as apd
    monkeypatch.setitem(apd.SYNDROME_SERO, "beispiel", {"seroprevalence_de": 0.5})
    monkeypatch.setattr(type(apd._cfg), "country", property(lambda self: "US"))
    assert apd._sero_pct_for_slug("beispiel") is None
    monkeypatch.setattr(type(apd._cfg), "country", property(lambda self: "DE"))
    assert apd._sero_pct_for_slug("beispiel") == 0.5


@pytest.mark.parametrize("marker,expected", [
    (None, None),
    ("G", "gesichert"),
    ("V", "Verdacht auf"),
    ("A", "ausgeschlossen"),
    ("GR", "gesichert (rechts)"),
    ("ZL", "Zustand nach (links)"),
])
def test_kbv_marker_decoding(marker, expected):
    from importers.import_billed_diagnoses import _decode_kbv_marker
    assert _decode_kbv_marker(marker) == expected


def test_icd_regex_separates_code_and_marker():
    from importers.import_billed_diagnoses import ICD_CODE_RE
    match = ICD_CODE_RE.search("Zeile A00.0GR Text")
    assert match.group(1) == "A00.0"
    assert match.group(2) == "GR"
    assert ICD_CODE_RE.search("Zeile A00.0 Text").group(2) is None
