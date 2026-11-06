#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Unit tests for patient_scrubbing module.

Uses a synthetic fake config (never the real user config) so this file
never contains or exercises any real personal data.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from modules.patient_scrubbing import scrub_patient_identity  # noqa: E402


class FakeConfig:
    def __init__(self, name="Erika Musterfrau", birthdate="1990-05-17"):
        self.name = name
        self.birthdate = birthdate


def test_full_name_removed():
    cfg = FakeConfig()
    text = "Patientin Erika Musterfrau wurde untersucht"
    result = scrub_patient_identity(text, cfg=cfg)
    assert "Musterfrau" not in result
    assert "Erika" not in result


def test_lastname_firstname_order_removed():
    cfg = FakeConfig()
    text = "Musterfrau, Erika - Diagnose"
    result = scrub_patient_identity(text, cfg=cfg)
    assert "Musterfrau" not in result


def test_lastname_firstname_no_comma_removed():
    cfg = FakeConfig()
    text = "Musterfrau Erika geb."
    result = scrub_patient_identity(text, cfg=cfg)
    assert "Musterfrau" not in result
    assert "Erika" not in result


def test_birthdate_iso_removed():
    cfg = FakeConfig()
    text = "geb. 1990-05-17 Versicherte"
    result = scrub_patient_identity(text, cfg=cfg)
    assert "1990-05-17" not in result


def test_birthdate_german_format_removed():
    cfg = FakeConfig()
    text = "geb. 17.05.1990"
    result = scrub_patient_identity(text, cfg=cfg)
    assert "17.05.1990" not in result


def test_birthdate_german_format_no_leading_zero_removed():
    cfg = FakeConfig(birthdate="1990-05-07")
    text = "geb. 7.5.1990"
    result = scrub_patient_identity(text, cfg=cfg)
    assert "7.5.1990" not in result


def test_age_pattern_removed_regardless_of_value():
    cfg = FakeConfig()
    for text in ["36 Jahre alt", "36 Jahre", "36 years old", "36 years"]:
        result = scrub_patient_identity(text, cfg=cfg)
        assert "36" not in result


def test_insurance_number_pattern_removed():
    cfg = FakeConfig()
    text = "Vers.-Nr. A123456789 Status"
    result = scrub_patient_identity(text, cfg=cfg)
    assert "A123456789" not in result


def test_insurance_number_pattern_with_space_removed():
    cfg = FakeConfig()
    text = "KV-Nummer A 123456789"
    result = scrub_patient_identity(text, cfg=cfg)
    assert "123456789" not in result


def test_plain_text_without_identity_passes_through():
    cfg = FakeConfig()
    text = "Rezidivierende depressive Störung, mittelgradig"
    result = scrub_patient_identity(text, cfg=cfg)
    assert result == text


def test_empty_text_returns_empty():
    cfg = FakeConfig()
    assert scrub_patient_identity("", cfg=cfg) == ""


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
