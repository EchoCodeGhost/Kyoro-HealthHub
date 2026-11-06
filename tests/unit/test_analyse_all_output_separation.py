# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Tests that analyse_all keeps script output out of its run logs.

@tier        unit
@purpose.de  Prüft, dass Skriptausgabe nur in der Ausgabedatei landet und das Log
             nur Laufdaten enthält.
@purpose.en  Checks that script output only reaches the output file and that the
             log holds run metadata only.
@method.de   Echte Kindprozesse mit einem temporären Skript, echte Dateirechte.
@method.en   Real child processes with a temporary script, real file modes.
@reads       temporäre Dateien
@writes      temporäre Dateien
@limits.de   Nur erfundene Werte; analysis_log wird nicht beschrieben
@limits.en   Made-up values only; analysis_log is not written
"""

import os
import stat
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

import analyse_all
from modules import pipeline_runner

OUTPUT_MARKER = "AUSGABE-MARKER-4711"
ERROR_MARKER = "FEHLER-MARKER-4712"
ARGUMENT_VALUE = "1999-12-31"


@pytest.fixture
def child(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline_runner, "_log_analysis_run", lambda *a, **k: None)
    script = tmp_path / "analyse_dummy.py"
    script.write_text(
        "import sys\n"
        f"print('{OUTPUT_MARKER}', sys.argv[1:])\n"
        f"if '--fail' in sys.argv: raise RuntimeError('{ERROR_MARKER}')\n",
        encoding="utf-8",
    )
    return script, tmp_path / "run" / "analyse_dummy"


def _files(out_dir):
    return out_dir / "analyse_dummy.output.txt", out_dir / "analyse_dummy.log"


def _mode(path):
    return stat.S_IMODE(path.stat().st_mode)


def test_output_reaches_only_the_output_file(child):
    script, out_dir = child
    ok, _ = analyse_all.run_script(script, out_dir, ["--from", ARGUMENT_VALUE], False,
                                   plot_supported=False, skipped_flags=["--plot"])
    output, log = _files(out_dir)
    assert ok
    assert OUTPUT_MARKER in output.read_text(encoding="utf-8")
    text = log.read_text(encoding="utf-8")
    assert OUTPUT_MARKER not in text
    assert ARGUMENT_VALUE not in text
    assert "--plot" in text
    assert "EXIT: 0" in text


def test_traceback_stays_out_of_the_log(child):
    script, out_dir = child
    ok, _ = analyse_all.run_script(script, out_dir, ["--fail"], False, plot_supported=False)
    output, log = _files(out_dir)
    assert not ok
    assert ERROR_MARKER in output.read_text(encoding="utf-8")
    assert ERROR_MARKER not in log.read_text(encoding="utf-8")
    assert "EXIT: 1" in log.read_text(encoding="utf-8")


def test_repeat_run_tightens_existing_files(child):
    script, out_dir = child
    out_dir.mkdir(parents=True)
    for path in _files(out_dir):
        path.write_text("alt", encoding="utf-8")
        os.chmod(path, 0o664)
    analyse_all.run_script(script, out_dir, [], False, plot_supported=False)
    for path in _files(out_dir):
        assert _mode(path) == 0o600
        assert "alt" not in path.read_text(encoding="utf-8")


def _old_and_new_logs(root):
    old = root / "2000-01-01" / "analyse_x" / "analyse_x.log"
    new = root / "2000-01-02" / "analyse_x" / "analyse_x.log"
    other = root / "2000-01-01" / "analyse_x" / "anderes.log"
    for path, text in ((old, "beliebige Ausgabe\n"), (new, "SCRIPT: x.py\n"), (other, "beliebig\n")):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return old, new, other


def test_purge_without_confirmation_deletes_nothing(tmp_path, capsys):
    old, new, other = _old_and_new_logs(tmp_path)
    assert analyse_all.purge_old_logs(tmp_path, confirmed=False) == 0
    assert old.exists() and new.exists() and other.exists()
    assert ": 1" in capsys.readouterr().out


def test_purge_with_confirmation_deletes_only_old_format(tmp_path):
    old, new, other = _old_and_new_logs(tmp_path)
    assert analyse_all.purge_old_logs(tmp_path, confirmed=True) == 1
    assert not old.exists()
    assert new.exists() and other.exists()


def test_real_log_is_not_treated_as_old(child):
    script, out_dir = child
    analyse_all.run_script(script, out_dir, [], False, plot_supported=False)
    assert analyse_all._old_format_logs(out_dir.parent.parent) == []
