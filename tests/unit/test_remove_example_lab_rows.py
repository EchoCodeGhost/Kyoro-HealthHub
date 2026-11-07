# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Tests for removing rows of the example lab file.

@tier        unit
@purpose.de  Prüft, dass genau die Zeilen aus der Beispieldatei gelöscht werden, unabhängig vom
             Laborname, und ohne Bestätigung nichts.
@purpose.en  Checks that exactly the rows from the example file are deleted, regardless of the
             lab name, and nothing without confirmation.
@method.de   Echte temporäre SQLite-Datei und die echte Beispieldatei.
@method.en   Real temporary SQLite file and the real example file.
@reads       templates/labor.example.csv, temporäre Datei
@writes      temporäre Datei
@limits.de   SQLCipher-Dateien werden hier nicht getestet.
@limits.en   SQLCipher files are not tested here.
"""

import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

from migrations import remove_example_lab_rows as removal


@pytest.fixture
def conn(tmp_path, monkeypatch):
    monkeypatch.setattr(removal, "log_import", lambda *a, **k: None)
    conn = sqlite3.connect(tmp_path / "x.db")
    conn.execute("CREATE TABLE lab_manual (date TEXT, parameter TEXT, wert TEXT, labor TEXT)")
    conn.executemany("INSERT INTO lab_manual VALUES (?,?,?,?)", [
        ("2023-03-22", "HbA1c", "5.9", "Labor-00000000"),
        ("2023-03-22", "HbA1c", "6.0", "Labor-00000000"),
        ("2023-03-23", "HbA1c", "5.9", "Labor-00000000"),
    ])
    conn.commit()
    yield conn
    conn.close()


def test_example_file_is_read_without_comment_lines():
    rows = removal.load_example_rows()
    assert ("2023-03-22", "HbA1c", "5.9") in rows
    assert all(not row[0].startswith("#") for row in rows)


def test_only_exact_rows_are_deleted_whatever_the_lab_name(conn):
    assert removal.remove_rows(conn, removal.load_example_rows(), apply=True) == {"2023-03-22": 1}
    assert conn.execute("SELECT date, wert FROM lab_manual ORDER BY date, wert").fetchall() == [
        ("2023-03-22", "6.0"), ("2023-03-23", "5.9")]


def test_nothing_is_deleted_without_confirmation(conn):
    assert sum(removal.remove_rows(conn, removal.load_example_rows(), apply=False).values()) == 1
    assert conn.execute("SELECT count(*) FROM lab_manual").fetchone() == (3,)
