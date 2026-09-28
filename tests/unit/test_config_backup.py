# SPDX-License-Identifier: GPL-3.0-or-later
"""
Regression test for modules/config_backup.py.

Background: a test run against a not-fully-isolated development script wrote
synthetic fixture data directly into real ~/.config/kyoro/*.json files,
permanently losing real data in one of them (no backup existed to recover
from). backup_before_write() closes that gap by making every save() in the
four personal-history management scripts back up the previous version first.

ensure_git_repo()/commit_config_change() add a second, complementary layer:
timestamped .bak snapshots show WHAT changed, but never WHO/WHY. Found while
setting up chain-of-custody tracking for the personal config directory (and,
per repo convention, every isolated per-clinic instance in the multi-tenant
feature) — a local-only git repo per instance gives a real commit history
instead.
"""

import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

from modules.config_backup import backup_before_write, ensure_git_repo, commit_config_change


def test_noop_when_file_does_not_exist_yet(tmp_path):
    target = tmp_path / "does_not_exist.json"
    backup_before_write(target)
    assert list(tmp_path.iterdir()) == []


def test_backs_up_existing_file_before_write(tmp_path):
    target = tmp_path / "family_history.json"
    target.write_text('[{"relative": "Mutter"}]', encoding="utf-8")

    backup_before_write(target)

    # Backups live in a _backups/ subdirectory, not alongside the live file —
    # keeps the config directory itself from filling up with .bak clutter.
    assert list(tmp_path.glob("family_history.json.bak.*")) == []
    backups = list((tmp_path / "_backups").glob("family_history.json.bak.*"))
    assert len(backups) == 1
    assert backups[0].read_text(encoding="utf-8") == '[{"relative": "Mutter"}]'
    # The original file itself must be untouched by the backup step.
    assert target.read_text(encoding="utf-8") == '[{"relative": "Mutter"}]'


def test_repeated_writes_accumulate_backups_not_overwrite(tmp_path):
    """A second bad write must not clobber the backup of the first."""
    target = tmp_path / "known_risk_exposures.json"
    target.write_text('[{"slug": "q_fieber"}]', encoding="utf-8")
    backup_before_write(target)

    time.sleep(1.1)  # ensure a distinct second-resolution timestamp
    target.write_text('[{"slug": "q_fieber"}, {"slug": "fsme"}]', encoding="utf-8")
    backup_before_write(target)

    backups = sorted((tmp_path / "_backups").glob("known_risk_exposures.json.bak.*"))
    assert len(backups) == 2
    contents = {b.read_text(encoding="utf-8") for b in backups}
    assert '[{"slug": "q_fieber"}]' in contents
    assert '[{"slug": "q_fieber"}, {"slug": "fsme"}]' in contents


def _git(tmp_path, *args):
    return subprocess.run(["git", *args], cwd=tmp_path, capture_output=True, text=True)


def test_ensure_git_repo_creates_local_only_repo(tmp_path):
    ensure_git_repo(tmp_path)

    assert (tmp_path / ".git").exists()
    # Never remote-connected — a local-only chain-of-custody log, not something
    # that could accidentally leak health data off the machine.
    remotes = _git(tmp_path, "remote").stdout.strip()
    assert remotes == ""


def test_ensure_git_repo_is_idempotent(tmp_path):
    ensure_git_repo(tmp_path)
    first_git_dir_mtime = (tmp_path / ".git" / "HEAD").stat().st_mtime

    ensure_git_repo(tmp_path)  # must not re-init or error on an existing repo

    assert (tmp_path / ".git" / "HEAD").stat().st_mtime == first_git_dir_mtime


def test_commit_config_change_creates_a_traceable_commit(tmp_path):
    target = tmp_path / "clinical_events.json"
    target.write_text('{"events": []}', encoding="utf-8")

    commit_config_change(target, "clinical_events: initial")

    log = _git(tmp_path, "log", "--oneline").stdout
    assert "clinical_events: initial" in log


def test_commit_config_change_self_heals_missing_repo(tmp_path):
    """A config directory that predates this feature (no .git yet) must not
    be skipped — commit_config_change() has to bootstrap it itself, not
    silently no-op, or every pre-existing clinic instance would stay
    unaudited forever."""
    target = tmp_path / "family_history.json"
    target.write_text("[]", encoding="utf-8")
    assert not (tmp_path / ".git").exists()

    commit_config_change(target, "family_history: initial")

    assert (tmp_path / ".git").exists()
    log = _git(tmp_path, "log", "--oneline").stdout
    assert "family_history: initial" in log


def test_commit_config_change_noop_when_nothing_changed(tmp_path):
    target = tmp_path / "travel_history.json"
    target.write_text("[]", encoding="utf-8")
    commit_config_change(target, "travel_history: first save")
    first_count = len(_git(tmp_path, "log", "--oneline").stdout.splitlines())

    # Same content written again — nothing actually changed.
    target.write_text("[]", encoding="utf-8")
    commit_config_change(target, "travel_history: no-op save")

    second_count = len(_git(tmp_path, "log", "--oneline").stdout.splitlines())
    assert second_count == first_count


def test_commit_config_change_only_touches_the_given_file(tmp_path):
    """Two different config files in the same instance directory — a commit
    for one must not accidentally sweep up unrelated uncommitted changes to
    the other into the same commit message."""
    a = tmp_path / "family_history.json"
    b = tmp_path / "travel_history.json"
    a.write_text("[]", encoding="utf-8")
    b.write_text("[]", encoding="utf-8")
    ensure_git_repo(tmp_path)

    # Only 'a' gets committed here...
    commit_config_change(a, "family_history: initial")
    # ...'b' is still untouched/unstaged at this point.
    status = _git(tmp_path, "status", "--porcelain").stdout
    assert "travel_history.json" in status

    log = _git(tmp_path, "log", "--oneline", "--", "travel_history.json").stdout
    assert log.strip() == ""
