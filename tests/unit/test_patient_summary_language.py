# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Tests for the language selection of the patient summary export.

@tier        unit
@purpose.de  Prüft, dass --language den Text des ODT-Dokuments umstellt und
             Einträge unverändert übernimmt.
@purpose.en  Checks that --language switches the ODT document's text and keeps
             entries unchanged.
@method.de   Echter Lauf von main() mit erfundenen Einträgen und In-Memory-DB; das
             erzeugte ODT wird wieder eingelesen.
@method.en   Real main() run with made-up entries and an in-memory DB; the written
             ODT is read back.
@reads       (keine)
@writes      temporäre ODT-Datei im pytest-Verzeichnis
@limits.de   Nur erfundene Einträge
@limits.en   Made-up entries only
"""

import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

pytest.importorskip("odf")


@pytest.fixture
def run_summary(monkeypatch, tmp_path):
    from exporters import generate_patient_summary as gps
    from modules import i18n

    previous = i18n.get_lang()
    data = {
        "medication_history.json": [{"name": "Beispielmittel", "dosis": "1 mg"}],
        "clinical_events.json": [{"date": "2020-01-01", "type": "surgery", "name": "Beispiel-OP"}],
        "family_history.json": [],
    }

    def _open():
        conn = sqlite3.connect(":memory:")
        conn.execute("CREATE TABLE medications (drug_name TEXT, is_chronic INT, person TEXT, source TEXT, date TEXT)")
        return conn

    class _Cfg:
        name = None
        birthdate = None

    monkeypatch.setattr(gps, "load_json_config", lambda name: data[name])
    monkeypatch.setattr(gps, "get_own_person_id", lambda: "PER-test")
    monkeypatch.setattr(gps, "Config", _Cfg)
    monkeypatch.setattr(gps, "open_medicine_db", _open)

    def _run(*flags):
        from odf import teletype
        from odf.opendocument import load
        from odf.text import H, P

        out = tmp_path / "summary.odt"
        monkeypatch.setattr(sys, "argv", ["generate_patient_summary.py", "--output", str(out), *flags])
        gps.main()
        doc = load(str(out))
        return "\n".join(teletype.extractText(e) for tag in (H, P) for e in doc.text.getElementsByType(tag))

    yield _run
    i18n.set_lang(previous)


def test_language_flag_english(run_summary):
    text = run_summary("--language", "en")
    assert "Patient summary" in text
    assert "Current medication" in text
    assert "Patientenübersicht" not in text
    assert "manuell ergänzen" not in text


def test_language_flag_german(run_summary):
    text = run_summary("--language", "de")
    assert "Patientenübersicht" in text
    assert "Aktuelle Medikation" in text
    assert "Current medication" not in text


def test_lang_alias_matches_project_convention(run_summary):
    assert "Patient summary" in run_summary("--lang", "en")


@pytest.mark.parametrize("language", ["de", "en"])
def test_entries_stay_unchanged(run_summary, language):
    text = run_summary("--language", language)
    assert "Beispielmittel 1 mg" in text
    assert "2020-01-01: Beispiel-OP" in text


def test_invalid_language_is_rejected(run_summary):
    with pytest.raises(SystemExit):
        run_summary("--language", "fr")
