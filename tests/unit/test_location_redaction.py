# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests für modules.location_redaction (nur erfundene Orte und Koordinaten)."""
import json

import pytest

from modules import address_redaction as ar
from modules import location_redaction as lr


@pytest.fixture(autouse=True)
def _isolated(monkeypatch, tmp_path):
    monkeypatch.setattr(lr, "_config_path", lambda: tmp_path / "missing.json")
    monkeypatch.setattr(ar, "_config_path", lambda: tmp_path / "missing.json")


@pytest.mark.parametrize("text", [
    "48.13514, 11.58198", "N 48.13514 E 11.58198", "N 48.1351 E 11.5820",
    "48.1351° N, 11.5820° E", "48°08'06\"N 11°34'55\"E", "GPS: 48.1351, 11.5820",
    "Koordinaten 48,1351 / 11,5820", "-33.86882, 151.20929", "Lat 48.13514",
])
def test_coordinates_are_redacted(text):
    assert lr.redact_locations(text) == lr.COORD_PLACEHOLDER


@pytest.mark.parametrize("text", [
    "CRP 1.2 mg/l", "HRV 41.5 ms", "0.85 mg", "2026-10-20", "Wert 3.14.159",
    "Gewicht 70.25 kg, 71.30 kg", "Index 1.2345, 2.3456 gemessen", "1.2345 2.3456 mg",
    "95.12345, 11.12345", "12.345 Messpunkte",
])
def test_measurements_are_kept(text):
    assert lr.redact_locations(text) == text


def test_place_from_caller_is_removed_and_regions_stay():
    out = lr.redact_locations("Wohnt in Musterstadt, Urlaub auf Fuerteventura", extra_places=["Musterstadt"])
    assert out == f"Wohnt in {lr.PLACE_PLACEHOLDER}, Urlaub auf Fuerteventura"


def test_places_from_config_and_from_addresses(monkeypatch, tmp_path):
    cfg = tmp_path / "cfg.json"
    cfg.write_text(json.dumps({"privacy_check": {
        "patient_places": ["Beispielhausen"],
        "patient_addresses": ["Musterstraße 12, 12345 Musterstadt a.d. Donau"],
    }}))
    monkeypatch.setattr(lr, "_config_path", lambda: cfg)
    monkeypatch.setattr(ar, "_config_path", lambda: cfg)
    out = lr.redact_locations("Arbeit in Beispielhausen, Wohnort Musterstadt a.d. Donau")
    assert "Beispielhausen" not in out and "Musterstadt" not in out


def test_place_matching_is_whole_word_and_case_insensitive():
    out = lr.redact_locations("musterstadtteil und MUSTERSTADT", extra_places=["Musterstadt"])
    assert "musterstadtteil" in out and out.endswith(lr.PLACE_PLACEHOLDER)


def test_coordinate_wins_over_place_on_overlap():
    spans = lr.find_location_spans("48.13514, 11.58198", extra_places=["48"])
    assert [s.kind for s in spans] == ["coords"]


def test_empty_and_none():
    assert lr.redact_locations("") == "" and lr.redact_locations(None) is None
