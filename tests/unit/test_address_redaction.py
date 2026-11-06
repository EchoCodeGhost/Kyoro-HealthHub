# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests für modules.address_redaction (nur synthetische Adressen)."""
import json

import pytest

from modules import address_redaction as ar


@pytest.fixture(autouse=True)
def _no_config(monkeypatch, tmp_path):
    monkeypatch.setattr(ar, "_config_path", lambda: tmp_path / "missing.json")


@pytest.mark.parametrize("text", [
    "Musterstraße 12, 12345 Musterstadt a.d. Donau",
    "MUSTERSTRASSE 12\n12345 MUSTERSTADT",
    "Am Mühlberg 5",
    "Bahnhofstr. 7a",
    "Dr.-Beispiel-Str. 3-5, D-80000 Beispielort",
    "Postfach 1234",
    "Eichelgartenweg 7",
])
def test_addresses_are_redacted(text):
    out = ar.redact_addresses(text)
    assert ar.PLACEHOLDER in out
    assert not any(ch.isdigit() for ch in out.replace("[ADRESSE-ENTFERNT]", ""))


@pytest.mark.parametrize("text", [
    "10000 Schritte", "Vitamin D 25 ng/ml", "Rückweg 3 Tage", "12345 mg", "Hauptweg 3 mg",
    "84000 Datenpunkte ausgewertet", "20000 Einträge",
    "Mittelwert 12345\n\nNÄCHSTER ABSCHNITT", "Im Mittel Nachts 2025",
    "_Bayern: 12345 Fälle_",
])
def test_quantities_are_kept(text):
    assert ar.redact_addresses(text) == text


def test_adjacent_spans_merge_to_one_placeholder():
    assert ar.redact_addresses("Musterstraße 12, 12345 Musterstadt") == ar.PLACEHOLDER


def test_configured_address_with_spelling_variants(monkeypatch, tmp_path):
    cfg = tmp_path / "health_config.json"
    cfg.write_text(json.dumps({"privacy_check": {"patient_addresses": ["Hauptmarkt 3, 99999 Beispielort"]}}))
    monkeypatch.setattr(ar, "_config_path", lambda: cfg)
    out = ar.redact_addresses("Wohnt am Hauptmarkt 3 in 99999 Beispielort.")
    assert "Hauptmarkt" not in out and "Beispielort" not in out


def test_empty_and_none():
    assert ar.redact_addresses("") == ""
    assert ar.redact_addresses(None) is None
