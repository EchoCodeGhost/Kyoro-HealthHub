# SPDX-License-Identifier: GPL-3.0-or-later
"""
Unit tests for the non-interactive `add_*_noninteractive` append functions added
to the four personal-history management scripts for
openspec/changes/add-anamnese-findings-promotion task 1.5.

Covers both the happy path (entry written in the same shape the interactive
`cmd_add`-style commands would produce) and validation rejection (invalid
choice-list value / missing required field / unknown risk slug), per task 1.5.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

import utils.manage.personal.manage_family_history as manage_family_history
import utils.manage.personal.manage_travel_history as manage_travel_history
import utils.manage.personal.manage_exposure_history as manage_exposure_history
import utils.manage.personal.manage_known_risk_exposures as manage_known_risk_exposures


@pytest.fixture
def redirected_stores(tmp_path, monkeypatch):
    """Point each script's target file at a throwaway path so tests never touch real config."""
    monkeypatch.setattr(manage_family_history, "HISTORY_FILE", tmp_path / "family_history.json")
    monkeypatch.setattr(manage_travel_history, "TRAVEL_FILE", tmp_path / "travel_history.json")
    monkeypatch.setattr(manage_exposure_history, "EXPOSURE_FILE", tmp_path / "exposure_history.json")
    monkeypatch.setattr(manage_known_risk_exposures, "RISK_FILE", tmp_path / "known_risk_exposures.json")
    return tmp_path


def test_family_history_valid_entry(redirected_stores):
    manage_family_history.add_entry_noninteractive({
        "relative": "Mutter",
        "condition": "Brustkrebs",
        "status": "bestätigt",
        "age_onset": "55",
        "notes": "Diagnostiziert 2010",
    })
    data = json.loads((redirected_stores / "family_history.json").read_text())
    assert len(data) == 1
    assert data[0]["relative"] == "Mutter"
    assert data[0]["condition"] == "Brustkrebs"


def test_family_history_rejects_invalid_relative(redirected_stores):
    with pytest.raises(ValueError):
        manage_family_history.add_entry_noninteractive({
            "relative": "NichtInDerListe",
            "condition": "Test",
        })


def test_travel_history_valid_entry(redirected_stores):
    manage_travel_history.add_entry_noninteractive({
        "name": "Bangkok",
        "country": "Thailand",
        "date_from": "2023-05-15",
        "date_to": "2023-05-30",
    })
    data = json.loads((redirected_stores / "travel_history.json").read_text())
    assert len(data) == 1
    assert data[0]["name"] == "Bangkok"


def test_travel_history_rejects_missing_required_field(redirected_stores):
    with pytest.raises(ValueError):
        manage_travel_history.add_entry_noninteractive({
            "country": "Deutschland",
            "date_from": "2023-01-01",
        })


def test_exposure_history_animal_contact_valid_entry(redirected_stores):
    manage_exposure_history.add_animal_contact_noninteractive({
        "animal": "Rind",
        "exposure": "regelmäßig",
        "period": "2010-2020",
        "context": "Landwirtschaftlicher Betrieb",
    })
    data = json.loads((redirected_stores / "exposure_history.json").read_text())
    assert len(data["animal_contacts"]) == 1
    assert data["animal_contacts"][0]["animal"] == "Rind"


def test_exposure_history_animal_contact_rejects_invalid_animal(redirected_stores):
    with pytest.raises(ValueError):
        manage_exposure_history.add_animal_contact_noninteractive({
            "animal": "Drache",
            "exposure": "regelmäßig",
        })


def test_exposure_history_occupational_valid_entry(redirected_stores):
    manage_exposure_history.add_occupational_exposure_noninteractive({
        "occupation": "Labortechniker",
        "exposure": "Chemikalien und biologische Agenzien",
        "period": "2015-2025",
    })
    data = json.loads((redirected_stores / "exposure_history.json").read_text())
    assert len(data["occupational_exposures"]) == 1
    assert data["occupational_exposures"][0]["occupation"] == "Labortechniker"


def test_known_risk_exposures_valid_entry(redirected_stores):
    manage_known_risk_exposures.add_entry_noninteractive({
        "slug": "q_fieber",
        "description": "Regelmäßiger Kontakt mit Rindern und Schafen",
        "level": "high",
    })
    data = json.loads((redirected_stores / "known_risk_exposures.json").read_text())
    assert len(data) == 1
    assert data[0]["slug"] == "q_fieber"


def test_known_risk_exposures_rejects_unknown_slug(redirected_stores):
    with pytest.raises(ValueError):
        manage_known_risk_exposures.add_entry_noninteractive({
            "slug": "unbekannter_erreger",
            "description": "Test",
            "level": "medium",
        })
