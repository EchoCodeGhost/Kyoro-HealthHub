# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests für modules.identifier_redaction (nur erfundene Nummern)."""
import pytest

from modules import identifier_redaction as ir


@pytest.mark.parametrize("text", [
    "Tel. 0171 1234567", "Telefon: 089/123456789", "Fax 030-1234567", "+49 171 1234567",
    "0049 89 123456", "(0171) 1234567", "01711234567", "Mobil: 0151 12 34 56 78",
    "0171 12 34 567",
])
def test_phone_numbers_are_redacted(text):
    assert ir.redact_identifiers(text) == ir.PHONE_PLACEHOLDER


@pytest.mark.parametrize("text", [
    "Versichertennummer: A123456789", "KV-Nr. A 123456789", "A123456789", "12 010190 A 123",
    "eGK-Nr: 1234 5678 9012", "Mitgliedsnummer 98765 4321",
])
def test_insurance_numbers_are_redacted(text):
    assert ir.redact_identifiers(text) == ir.INSURANCE_PLACEHOLDER


@pytest.mark.parametrize("text", [
    "CRP 1.2 mg/l", "2026-10-20", "20.10.2026", "Ruhepuls 58 bpm", "10000 Schritte",
    "0,85 mg", "05-100 mg", "12.345.678 Messpunkte", "HRV 41 ms, 0.5 s", "Bestellnummer 12345",
    "ICD A41.9", "08:30 Uhr", "Dosis 0 5 10 mg", "NCT01234567",
    "01.02.2026", "05.10.2025", "01-02-2026", "01/02/2026", "Befund vom 01.02.2026",
    "Zeitraum 06-01/06/30", "Clusterung 01-15/02-20", "_1234567 Schritte_",
])
def test_measurements_and_codes_are_kept(text):
    assert ir.redact_identifiers(text) == text


def test_label_and_number_in_a_sentence():
    out = ir.redact_identifiers("Bitte unter Tel. 0171 1234567 zurückrufen, danke.")
    assert out == f"Bitte unter {ir.PHONE_PLACEHOLDER} zurückrufen, danke."


def test_insurance_wins_over_phone_when_overlapping():
    out = ir.redact_identifiers("Versichertennummer: 0171 1234567")
    assert ir.INSURANCE_PLACEHOLDER in out and ir.PHONE_PLACEHOLDER not in out


def test_empty_and_none():
    assert ir.redact_identifiers("") == "" and ir.redact_identifiers(None) is None


@pytest.mark.parametrize("text", [
    "IBAN DE89 3704 0044 0532 0130 00", "DE89370400440532013000", "BIC: COBADEFFXXX",
    "Konto 532013000", "BLZ: 37040044", "Kontonummer: 532013000",
])
def test_bank_details_are_redacted(text):
    assert ir.BANK_PLACEHOLDER in ir.redact_identifiers(text)
    assert not any(ch.isdigit() for ch in ir.redact_identifiers(text).replace(ir.BANK_PLACEHOLDER, ""))


@pytest.mark.parametrize("text", [
    "Patientennummer: 4711234", "Fall-Nr. 20261234", "Auftragsnummer A-123456", "BSNR 123456789",
    "LANR: 123456789", "IK-Nr. 108018007", "Aktenzeichen 123/456", "patienten-nr 4711234",
    "Probe 1234567", "ID 123456789012",
])
def test_id_numbers_of_other_systems_are_redacted(text):
    out = ir.redact_identifiers(text)
    assert ir.NUMBER_PLACEHOLDER in out
    assert not any(ch.isdigit() for ch in out.replace(ir.NUMBER_PLACEHOLDER, ""))


@pytest.mark.parametrize("text", ["Durchwahl 123", "DW -4567", "Tel. 5678", "Ext. 12345"])
def test_short_extensions_are_redacted(text):
    assert ir.PHONE_PLACEHOLDER in ir.redact_identifiers(text)


@pytest.mark.parametrize("text", [
    "20261020", "1760000000", "1234567 Schritte", "84000 Datenpunkte", "Messwert 1234567.89",
    "DE12 abcd efgh ijkl", "Mobil 100 Schritte",
])
def test_long_numbers_with_unit_dates_timestamps_and_fake_ibans_are_kept(text):
    assert ir.redact_identifiers(text) == text


def test_iban_needs_valid_check_digits():
    # invalid check digits: not treated as bank details (digit groups may still match as a phone number)
    assert ir.BANK_PLACEHOLDER not in ir.redact_identifiers("DE00 3704 0044 0532 0130 00")
