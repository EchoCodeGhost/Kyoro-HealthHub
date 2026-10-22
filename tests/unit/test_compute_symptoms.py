# SPDX-License-Identifier: GPL-3.0-or-later
"""
compute/compute_symptoms.py: a changed mapping must not leave the old
canonical row behind.

Background: symptom_de is part of the primary key of symptoms_canonical, so
INSERT OR IGNORE added the new canonical name next to the old one when
symptom_map.json changed ("breast pain": "Brustschmerzen" ->
"Brustdrüsenschmerzen"). A full run now removes rows whose canonical name no
longer matches the mapping; --update leaves existing rows alone.
"""
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

import compute.compute_symptoms as cs  # noqa: E402


def _conn():
    c = sqlite3.connect(":memory:")
    c.execute("""CREATE TABLE symptoms (date TEXT, symptom TEXT, value_num REAL,
                 value_text TEXT, category TEXT, person TEXT, source TEXT)""")
    c.execute("INSERT INTO symptoms VALUES ('2026-07-01', 'Breast pain', 3, NULL, NULL, 'PER-test', 'app')")
    return c


def _names(c):
    return [r[0] for r in c.execute("SELECT symptom_de FROM symptoms_canonical")]


def test_full_run_replaces_row_of_changed_mapping(monkeypatch):
    c = _conn()
    monkeypatch.setattr(cs, "_load_map", lambda: {"breast pain": {"de": "Brustschmerzen"}})
    cs.compute(c)
    assert _names(c) == ["Brustschmerzen"]

    monkeypatch.setattr(cs, "_load_map", lambda: {"breast pain": {"de": "Brustdrüsenschmerzen"}})
    cs.compute(c)
    assert _names(c) == ["Brustdrüsenschmerzen"]


def test_update_run_keeps_existing_rows(monkeypatch):
    c = _conn()
    monkeypatch.setattr(cs, "_load_map", lambda: {"breast pain": {"de": "Brustschmerzen"}})
    cs.compute(c)
    monkeypatch.setattr(cs, "_load_map", lambda: {"breast pain": {"de": "Brustdrüsenschmerzen"}})
    cs.compute(c, update_only=True)
    assert _names(c) == ["Brustschmerzen"]
