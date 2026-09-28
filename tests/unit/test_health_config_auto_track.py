# SPDX-License-Identifier: GPL-3.0-or-later
"""
Regression test for health_config.py's _auto_track_config_changes() hook.

Background: config_backup.py's commit_config_change()/commit_config_dir()
only capture a change if the writing code explicitly calls them — a direct
file edit (a human, a text editor, a future script that's never heard of
config_backup.py) still leaves no trace. health_config.py is imported by
effectively every Kyoro script (per its own docstring), so wiring the sweep
there — once at import time, once at process exit via atexit — gives
chain-of-custody coverage without requiring every write path to cooperate.

These tests spawn real subprocesses with an isolated HOME rather than
calling the hook in-process, for two reasons: (1) the hook is itself
disabled whenever "pytest" is present in sys.modules (a deliberate guard,
tested separately below) so calling it directly from inside this suite
would always no-op, and (2) atexit behavior can only be observed by
actually letting a process exit.
"""

import json
import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = str(Path(__file__).parent.parent.parent / "scripts")


def _run_isolated(tmp_path, code: str) -> subprocess.CompletedProcess:
    config_dir = tmp_path / ".config" / "kyoro"
    config_dir.mkdir(parents=True)
    (config_dir / "health_config.json").write_text(
        json.dumps({"language": "de"}), encoding="utf-8")
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(Path(__file__).parent.parent.parent),
        env={"HOME": str(tmp_path), "PATH": "/usr/bin:/bin"},
        capture_output=True, text=True, timeout=30,
    )
    return result


def _git_log(config_dir: Path) -> str:
    return subprocess.run(
        ["git", "log", "--oneline"], cwd=config_dir,
        capture_output=True, text=True,
    ).stdout


def test_import_sweeps_pre_existing_uncommitted_changes(tmp_path):
    result = _run_isolated(tmp_path, f"""
import sys
sys.path.insert(0, {SCRIPTS_DIR!r})
import health_config
""")
    assert result.returncode == 0, result.stderr

    config_dir = tmp_path / ".config" / "kyoro"
    log = _git_log(config_dir)
    assert "pre-existing change detected" in log


def test_atexit_sweeps_a_write_made_during_the_run_without_cooperation(tmp_path):
    """A script that writes directly (never calls commit_config_change())
    must still get its change committed once the process exits."""
    result = _run_isolated(tmp_path, f"""
import sys
sys.path.insert(0, {SCRIPTS_DIR!r})
import health_config
(health_config.KYORO_CONFIG_DIR / "family_history.json").write_text(
    '[{{"relative": "Mutter"}}]', encoding="utf-8")
""")
    assert result.returncode == 0, result.stderr

    config_dir = tmp_path / ".config" / "kyoro"
    log = _git_log(config_dir)
    assert "change by" in log
    # Both the pre-run sweep and the exit-time sweep must have fired,
    # as two distinct, separately attributed commits.
    commit_lines = [line for line in log.splitlines() if line.strip()]
    assert len(commit_lines) >= 2


def test_noop_when_nothing_changed(tmp_path):
    """First run establishes a clean baseline; a second run that changes
    nothing must not create empty commits."""
    code = f"""
import sys
sys.path.insert(0, {SCRIPTS_DIR!r})
import health_config
"""
    first = _run_isolated(tmp_path, code)
    assert first.returncode == 0, first.stderr
    config_dir = tmp_path / ".config" / "kyoro"
    commits_after_first = len(_git_log(config_dir).strip().splitlines())

    subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(Path(__file__).parent.parent.parent),
        env={"HOME": str(tmp_path), "PATH": "/usr/bin:/bin"},
        capture_output=True, text=True, timeout=30,
    )
    commits_after_second = len(_git_log(config_dir).strip().splitlines())

    assert commits_after_second == commits_after_first


def test_disabled_under_pytest(tmp_path):
    """The guard this whole feature depends on: a documented past incident
    had a not-fully-isolated test write synthetic data into the real
    ~/.config/kyoro/*.json files. An automatic sweep firing on every test
    run would commit that class of leak into the user's real personal repo
    instead of it surfacing as a visible problem."""
    result = _run_isolated(tmp_path, f"""
import sys
sys.modules['pytest'] = sys  # anything truthy under the 'pytest' key
sys.path.insert(0, {SCRIPTS_DIR!r})
import health_config
""")
    assert result.returncode == 0, result.stderr

    config_dir = tmp_path / ".config" / "kyoro"
    assert not (config_dir / ".git").exists()
