# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Tests for the date and personal-note patterns in check_no_dates.py.

@tier        unit
@purpose.de  Prüft, dass deutsche Datumsformate, Umbrüche und persönliche Vermerke
             erkannt werden und legitime Zeilen nicht anschlagen.
@purpose.en  Checks that German date formats, wrapped lines and personal notes are
             detected, and that legitimate lines do not trigger.
@method.de   Echte scan_file()-Läufe auf temporären Dateien.
@method.en   Real scan_file() runs on temporary files.
@reads       temporäre Dateien im pytest-Verzeichnis
@writes      temporäre Dateien im pytest-Verzeichnis
@limits.de   Nur erfundene Zeilen
@limits.en   Made-up lines only
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "utils"))

import check_no_dates as cnd  # noqa: E402


def _findings(tmp_path, text):
    path = tmp_path / "sample.py"
    path.write_text(text, encoding="utf-8")
    return cnd.scan_file(path)


@pytest.mark.parametrize("line", [
    "# Fixed 2000-01-02",
    "# Fix 2000-01-02 im Parser",
    "# Fix 02.01.2000 im Parser",
    "# Ergänzt 02.01.2000 im Parser",
    "# Ergaenzt 02.01.2000 im Parser",
    "# Korrigiert 02.01.2000 -- vorherige Version",
    "# (Session 02.01.2000)",
    "# (Sitzung 2.1.2000)",
    "# s. Fund 02.01.2000",
    "# Stand 02.01.2000",
    "# seit 2.1.2000 anders",
    "# (Nutzerinnen-Anfrage 02.01.2000)",
    "# Nutzerinnen-Einwand zum Schwellwert",
    "# Vorgabe (Nutzerinnen-",
    "# bis die Nutzerin nachfragte",
    '# entfernt (Nutzerin: "egal")',
])
def test_flagged(tmp_path, line):
    assert _findings(tmp_path, line + "\n")


@pytest.mark.parametrize("line", [
    "# Parser fuer Daten wie 02.01.2000",
    'FORMAT_EXAMPLE = "02.01.2000 10:30:05"',
    "# Bibliothek 1.2.2000.4",
    "value = 12.34",
    "# die Nutzerin als Begriff fuer die Person mit den Daten",
    "# Stand 02.01.2000 der Quelle  # no-date-check: Stand der zitierten Quelle",
])
def test_not_flagged(tmp_path, line):
    assert not _findings(tmp_path, line + "\n")


def test_status_and_date_wrapped_across_lines(tmp_path):
    findings = _findings(tmp_path, "# Grenzwert angepasst -- gefixt\n# 02.01.2000 nach Pruefung\n")
    assert [f["line"] for f in findings] == [2]


def test_date_at_line_start_without_status_above_is_fine(tmp_path):
    assert not _findings(tmp_path, "# Beispielzeile aus einer Datei:\n# 02.01.2000 Messwert\n")
