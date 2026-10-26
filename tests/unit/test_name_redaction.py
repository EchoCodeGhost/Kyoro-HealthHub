# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests für modules.name_redaction (nur erfundene Namen)."""
import json
import sqlite3

import pytest

from modules import name_redaction as nr


@pytest.fixture(autouse=True)
def _isolated(monkeypatch, tmp_path):
    monkeypatch.setattr(nr, "_config_path", lambda: tmp_path / "missing.json")
    monkeypatch.setattr(nr, "_identity_db_path", lambda: tmp_path / "missing.db")


@pytest.mark.parametrize("text,gone", [
    ("Sehr geehrte Frau Beispiel,", "Beispiel"),
    ("Dr. med. Muster-Beispiel, Kardiologie", "Muster"),
    ("Prof. Dr. Erika Mustermann", "Mustermann"),
    ("Patientin: Erika Mustermann", "Mustermann"),
    ("Name, Vorname: Mustermann, Erika", "Erika"),
    ("Herr Beispiel hat angerufen", "Beispiel"),
])
def test_titled_and_labelled_names(text, gone):
    out = nr.redact_names(text)
    assert nr.PLACEHOLDER in out and gone not in out


@pytest.mark.parametrize("text", ["CRP 1.2 mg/l", "Befund vom 01.02.2026", "Frau und Mann", "Name: "])
def test_no_false_positive(text):
    assert nr.redact_names(text) == text


def test_label_value_does_not_swallow_the_next_line():
    out = nr.redact_names("Name: Wert\nKlinische Ereignisse: keine")
    assert "Klinische Ereignisse" in out


def test_label_value_on_next_line_is_still_found():
    assert "Mustermann" not in nr.redact_names("Name:\nMustermann")


def test_extra_and_configured_and_identity_names(monkeypatch, tmp_path):
    out = nr.redact_names("Notiz zu erika und Mustermann.", extra_names=["Erika Mustermann"])
    assert "erika" not in out.lower() and "mustermann" not in out.lower()

    cfg = tmp_path / "cfg.json"
    cfg.write_text(json.dumps({"privacy_check": {"patient_names": ["Beispielfrau"]}}))
    monkeypatch.setattr(nr, "_config_path", lambda: cfg)
    assert "Beispielfrau" not in nr.redact_names("Brief an Beispielfrau")

    db = tmp_path / "identity.db"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE person_name_map (person_pseudo TEXT, name_real TEXT, alias1 TEXT, alias2 TEXT, alias3 TEXT)")
    con.execute("INSERT INTO person_name_map VALUES ('P1','Hans Testmann','Hansi',NULL,NULL)")
    con.commit(); con.close()
    monkeypatch.setattr(nr, "_identity_db_path", lambda: db)
    out = nr.redact_names("Hansi und Testmann waren da")
    assert "Hansi" not in out and "Testmann" not in out


def test_short_name_parts_ignored():
    assert nr.redact_names("Li geht", extra_names=["Li Wu"]) == "Li geht"


def test_empty_and_none():
    assert nr.redact_names("") == "" and nr.redact_names(None) is None
