# SPDX-License-Identifier: GPL-3.0-or-later
"""
Unit-Tests für modules/pipeline_runner.py.

Hintergrund: compute_all.py leitete Kindprozess-Output früher direkt an das
ererbte stdout/stderr weiter (subprocess.run(cmd) ohne capture). Ein Script,
das mitten im Lauf abstürzte, hinterließ nur "beendet mit Code 1" — ganz ohne
Traceback, weil dessen block-gepufferte, ungeflushte Ausgabe verloren ging.
Diese Tests fixieren das erwartete Verhalten: Erfolg wird protokolliert,
Fehler bringen den vollen stdout plus die letzten stderr-Zeilen mit.
"""
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

from modules.pipeline_runner import run_pipeline_script  # noqa: E402


def _write_script(tmp_path: Path, body: str) -> Path:
    script = tmp_path / "fake_pipeline_script.py"
    script.write_text(body)
    return script


def test_success_reports_no_error(tmp_path, capsys):
    script = _write_script(tmp_path, "print('all good')\n")
    errors: list[str] = []

    run_pipeline_script("test", script, [sys.executable, str(script)], errors)

    assert errors == []
    out = capsys.readouterr().out
    assert "all good" in out
    assert "erfolgreich abgeschlossen" in out


def test_crash_is_captured_not_swallowed(tmp_path, capsys):
    script = _write_script(tmp_path, (
        "print('some output before the crash')\n"
        "raise RuntimeError('intentional test crash')\n"
    ))
    errors: list[str] = []

    run_pipeline_script("test", script, [sys.executable, str(script)], errors)

    assert errors == [script.name]
    captured = capsys.readouterr()
    # stdout printed by the child before it crashed must still show up
    assert "some output before the crash" in captured.out
    # the traceback must be visible somewhere, not silently discarded
    assert "RuntimeError" in captured.err
    assert "intentional test crash" in captured.err
    assert f"FEHLER: {script.name}" in captured.err or f"ERROR: {script.name}" in captured.err


def test_stderr_tail_is_limited_to_20_lines(tmp_path, capsys):
    body = "\n".join(f"import sys; print('line {i}', file=sys.stderr)" for i in range(40))
    body += "\nsys.exit(1)\n"
    script = _write_script(tmp_path, body)
    errors: list[str] = []

    run_pipeline_script("test", script, [sys.executable, str(script)], errors)

    err_lines = [ln for ln in capsys.readouterr().err.splitlines() if ln.strip().startswith("line ")]
    assert len(err_lines) == 20
    # must be the *last* 20, not the first 20
    assert "line 39" in err_lines[-1]
    assert "line 20" in err_lines[0]


def test_show_command_flag(tmp_path, capsys):
    script = _write_script(tmp_path, "print('ok')\n")
    errors: list[str] = []

    run_pipeline_script("test", script, [sys.executable, str(script), "--update"], errors,
                         show_command=True)

    out = capsys.readouterr().out
    assert "--update" in out


def test_log_compute_writes_script_git_commit_and_duration(tmp_path, monkeypatch):
    """compute_log muss rekonstruierbar machen, mit welchem Code-Stand ein
    Compute-Lauf ein Ergebnis erzeugt hat (s. @method in pipeline_runner.py)."""
    import modules.db as dbmod

    db_path = tmp_path / "fake_health.db"
    monkeypatch.setattr(dbmod, "open_db", lambda *a, **kw: sqlite3.connect(db_path))

    script = _write_script(tmp_path, "print('computed')\n")
    errors: list[str] = []

    run_pipeline_script("compute_all", script, [sys.executable, str(script)], errors,
                         log_compute=True)

    conn = sqlite3.connect(db_path)
    row = conn.execute(
        "SELECT script, git_commit, returncode, duration_s FROM compute_log"
    ).fetchone()
    conn.close()

    assert row is not None
    script_name, git_commit, returncode, duration_s = row
    assert script_name == script.name
    assert returncode == 0
    assert duration_s is not None and duration_s >= 0
    # git_commit is None only outside a git repo — this test runs inside the
    # Kyoro-HealthHub checkout, so it must resolve to a real commit hash.
    assert git_commit is not None and len(git_commit) == 40


def test_log_compute_records_nonzero_returncode_on_failure(tmp_path, monkeypatch):
    import modules.db as dbmod

    db_path = tmp_path / "fake_health.db"
    monkeypatch.setattr(dbmod, "open_db", lambda *a, **kw: sqlite3.connect(db_path))

    script = _write_script(tmp_path, "import sys; sys.exit(1)\n")
    errors: list[str] = []

    run_pipeline_script("compute_all", script, [sys.executable, str(script)], errors,
                         log_compute=True)

    conn = sqlite3.connect(db_path)
    returncode = conn.execute("SELECT returncode FROM compute_log").fetchone()[0]
    conn.close()

    assert returncode == 1
