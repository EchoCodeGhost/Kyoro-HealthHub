# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Tests that the acute-course migration takes its list from config.

@tier        unit
@purpose.de  Prüft, dass die Migration ihre Kuren aus der Config liest und ohne
             Eintrag mit einer klaren Meldung abbricht.
@purpose.en  Checks that the migration reads its courses from config and exits
             with a clear message when there are none.
@method.de   Echter run()-Lauf gegen eine temporäre SQLite-Datei.
@method.en   Real run() against a temporary SQLite file.
@reads       temporäre Datenbank
@writes      temporäre Datenbank
@limits.de   Nur erfundene Einträge
@limits.en   Made-up entries only
"""

import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))


@pytest.fixture
def migration(monkeypatch, tmp_path):
    from migrations import curate_acute_medication_courses as m

    db = tmp_path / "medicine.db"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE medications (person TEXT, drug_name TEXT, date TEXT, is_chronic INT)")
    conn.executemany("INSERT INTO medications VALUES ('PER-test', ?, ?, 1)",
                     [("Beispielmittel", "2000-01-02"), ("Anderes Mittel", "2000-01-03")])
    conn.commit()
    conn.close()
    monkeypatch.setattr(m, "open_medicine_db", lambda: sqlite3.connect(db))
    monkeypatch.setattr(m, "resolve_person", lambda person: "PER-test")
    monkeypatch.setattr(m, "log_import", lambda *a, **k: None)
    return m, db


def _config(monkeypatch, m, courses):
    class _Cfg:
        acute_medication_courses = courses

    monkeypatch.setattr(m, "Config", _Cfg)


def test_listed_course_is_marked_and_others_stay(monkeypatch, migration):
    m, db = migration
    _config(monkeypatch, m, [{"drug": "Beispielmittel", "date": "2000-01-02"}])
    m.run()
    rows = dict(sqlite3.connect(db).execute("SELECT drug_name, is_chronic FROM medications"))
    assert rows == {"Beispielmittel": 0, "Anderes Mittel": 1}


def test_empty_config_exits_without_changes(monkeypatch, migration):
    m, db = migration
    _config(monkeypatch, m, [])
    with pytest.raises(SystemExit) as exc:
        m.run()
    assert "acute_medication_courses" in str(exc.value)
    assert sqlite3.connect(db).execute("SELECT SUM(is_chronic) FROM medications").fetchone()[0] == 2


def test_source_has_no_course_data():
    source = (Path(__file__).parent.parent.parent / "scripts/migrations/curate_acute_medication_courses.py").read_text(encoding="utf-8")
    assert "ACUTE_COURSES = [" not in source
