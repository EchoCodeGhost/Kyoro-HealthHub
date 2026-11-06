# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Tests that a lifetime window does not show its start date.

@tier        unit
@purpose.de  Prüft, dass das Startdatum eines Lebenszeit-Fensters nicht angezeigt
             wird und auch nicht aus den Quartalszeilen ablesbar ist.
@purpose.en  Checks that the start date of a lifetime window is not displayed and
             cannot be read from the quarter rows.
@method.de   Direkter Aufruf von Anzeigehilfe und Quartalsberechnung.
@method.en   Direct calls of the display helper and the quarter calculation.
@reads       keine
@writes      keine
@limits.de   Nur erfundene Werte
@limits.en   Made-up values only
"""

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

from analysis.infectious import analyse_postinfectious_diagnose as m

START = "1950-06-15"


def _data():
    return {"nhrv": {"2020-01-10": {"rmssd": 30.0}}, "activity": {}, "pem": {}}


def test_label_hides_start_only_in_lifetime_mode(monkeypatch):
    assert m._window_start_label(START) == START
    monkeypatch.setattr(m, "_LIFETIME_WINDOW", True)
    assert START not in m._window_start_label(START)


def test_trend_rows_start_at_first_data_in_lifetime_mode(monkeypatch):
    monkeypatch.setattr(m, "_LIFETIME_WINDOW", True)
    trend = m.compute_trend(_data(), START, "2020-06-01")
    assert trend[0]["start"] == "2020-01-10"


def test_trend_without_data_has_no_rows_in_lifetime_mode(monkeypatch):
    monkeypatch.setattr(m, "_LIFETIME_WINDOW", True)
    assert m.compute_trend({"nhrv": {}, "activity": {}, "pem": {}}, START, "2020-06-01") == []


def test_normal_window_keeps_its_start():
    assert m.compute_trend(_data(), "2020-01-01", "2020-02-01")[0]["start"] == "2020-01-01"


def _pathogen_module(monkeypatch):
    from analysis.infectious import analyse_pathogen_exposure as p

    class _Cfg:
        birthdate = START

    monkeypatch.setattr(p, "_cfg", _Cfg())
    return p


def test_stay_from_birth_hides_its_start(monkeypatch):
    p = _pathogen_module(monkeypatch)
    stay = SimpleNamespace(date_from=START, duration_d=100)
    assert p._starts_at_birth(stay)
    assert START not in p._stay_start_label(stay)


def test_later_stay_keeps_its_start(monkeypatch):
    p = _pathogen_module(monkeypatch)
    stay = SimpleNamespace(date_from="2020-01-10", duration_d=3)
    assert not p._starts_at_birth(stay)
    assert p._stay_start_label(stay) == "2020-01-10"
