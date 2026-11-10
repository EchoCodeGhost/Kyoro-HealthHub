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

from modules.config_backup import (
    backup_before_write, commit_config_change, commit_config_dir, ensure_git_repo,
)


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


def test_sweep_inside_another_repos_hook_stays_in_config_repo(tmp_path, monkeypatch):
    """health_config.py's import-time sweep runs inside the Kyoro pre-commit
    hook (via qa_check.py). git exports GIT_DIR/GIT_INDEX_FILE/GIT_WORK_TREE
    to hooks; inherited, they made the sweep stage and commit the config
    directory into the Kyoro repo (a git worktree) being committed."""
    outer = tmp_path / "outer"
    outer.mkdir()
    _git(outer, "init", "-q")
    _git(outer, "config", "user.name", "Outer")
    _git(outer, "config", "user.email", "outer@localhost")
    (outer / "code.py").write_text("x = 1\n", encoding="utf-8")
    _git(outer, "add", "code.py")
    _git(outer, "commit", "-q", "-m", "outer: initial")

    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "health_config.json").write_text("{}", encoding="utf-8")

    # What git sets for a hook in the outer repo.
    monkeypatch.setenv("GIT_DIR", str(outer / ".git"))
    monkeypatch.setenv("GIT_INDEX_FILE", str(outer / ".git" / "index"))
    monkeypatch.setenv("GIT_WORK_TREE", str(outer))
    commit_config_dir(config_dir, "auto: sweep")
    for var in ("GIT_DIR", "GIT_INDEX_FILE", "GIT_WORK_TREE"):
        monkeypatch.delenv(var)

    outer_log = _git(outer, "log", "--oneline").stdout.strip().splitlines()
    assert outer_log == [outer_log[0]] and "outer: initial" in outer_log[0]
    assert _git(outer, "ls-files").stdout.split() == ["code.py"]
    assert _git(outer, "status", "--porcelain").stdout.strip() == ""

    config_log = _git(config_dir, "log", "--oneline").stdout
    assert "auto: sweep" in config_log
    assert "health_config.json" in _git(config_dir, "ls-files").stdout


# ── Ausschlüsse für Datenbanken + Größenlimit (identity-store-encryption) ──


def test_ensure_git_repo_writes_db_exclusions(tmp_path):
    ensure_git_repo(tmp_path)
    lines = (tmp_path / ".git" / "info" / "exclude").read_text(encoding="utf-8").splitlines()
    for pattern in ("*.db", "*.db.*", "*-wal", "*-shm", "*.sqlite"):
        assert pattern in lines


def test_ensure_git_repo_exclusions_are_idempotent_and_self_healing(tmp_path):
    ensure_git_repo(tmp_path)
    ensure_git_repo(tmp_path)  # second call must not duplicate patterns
    lines = (tmp_path / ".git" / "info" / "exclude").read_text(encoding="utf-8").splitlines()
    assert lines.count("*.db") == 1
    assert lines.count("*.db.*") == 1

    # A repo that predates the exclusions (created by hand, no exclude file)
    # gets them on the next ensure_git_repo() call.
    (tmp_path / ".git" / "info" / "exclude").unlink()
    ensure_git_repo(tmp_path)
    lines = (tmp_path / ".git" / "info" / "exclude").read_text(encoding="utf-8").splitlines()
    assert "*.db" in lines


def test_database_files_in_config_dir_are_not_staged(tmp_path):
    """A database backup dropped into the config folder must never be staged
    by the git add -A sweep — not the db itself, not copies, not WAL/SHM."""
    (tmp_path / "identity.db").write_bytes(b"SQLite format 3\x00" + b"x" * 64)
    (tmp_path / "health.db.before_x").write_bytes(b"SQLite format 3\x00" + b"y" * 64)
    (tmp_path / "health.db-wal").write_bytes(b"z" * 32)
    (tmp_path / "health.db-shm").write_bytes(b"z" * 32)
    (tmp_path / "extra.sqlite").write_bytes(b"SQLite format 3\x00" + b"w" * 32)
    (tmp_path / "health_config.json").write_text("{}", encoding="utf-8")

    commit_config_dir(tmp_path, "auto: sweep")

    staged = _git(tmp_path, "ls-files").stdout.split()
    assert "health_config.json" in staged  # normal JSON change is still committed
    for name in ("identity.db", "health.db.before_x", "health.db-wal",
                 "health.db-shm", "extra.sqlite"):
        assert name not in staged


def test_large_file_is_skipped_and_only_named_in_log(tmp_path, capsys):
    (tmp_path / "big_backup.json").write_bytes(b"0" * (5 * 1024 * 1024 + 1))
    (tmp_path / "small.json").write_text("{}", encoding="utf-8")

    commit_config_dir(tmp_path, "auto: sweep")

    staged = _git(tmp_path, "ls-files").stdout.split()
    assert "small.json" in staged
    assert "big_backup.json" not in staged
    err = capsys.readouterr().err
    assert "big_backup.json" in err  # named ...
    assert "0" * 100 not in err      # ... but never its contents


def test_file_exactly_at_size_limit_is_still_committed(tmp_path):
    target = tmp_path / "at_limit.json"
    target.write_bytes(b"0" * (5 * 1024 * 1024))
    commit_config_dir(tmp_path, "auto: sweep")
    assert "at_limit.json" in _git(tmp_path, "ls-files").stdout.split()


def test_oversized_file_is_never_passed_to_git_add(tmp_path, monkeypatch, capsys):
    """Oversized files must be excluded BEFORE staging: `git status
    --porcelain -z` does not hash untracked files, and no `git add` call may
    ever contain the oversized path."""
    import modules.config_backup as cb

    (tmp_path / "small.json").write_text("{}", encoding="utf-8")
    big = tmp_path / "huge.bin"
    with open(big, "wb") as fh:
        fh.truncate(6 * 1024 * 1024)  # sparse file: size counts, content is never read

    real_git = cb._git
    git_calls = []

    def recording_git(config_dir, *args, **kwargs):
        git_calls.append(args)
        return real_git(config_dir, *args, **kwargs)

    monkeypatch.setattr(cb, "_git", recording_git)

    commit_config_dir(tmp_path, "auto: sweep")

    add_calls = [c for c in git_calls if c and c[0] == "add"]
    assert add_calls, "expected at least one git add call"
    for c in add_calls:
        assert "huge.bin" not in c  # never handed to git add, so never hashed
    staged = _git(tmp_path, "ls-files").stdout.split()
    assert "small.json" in staged
    assert "huge.bin" not in staged
    err = capsys.readouterr().err
    assert "huge.bin" in err  # named in the log ...


def test_deleted_file_is_still_committed_as_deletion(tmp_path):
    """Selective staging via git status must keep staging deletions."""
    (tmp_path / "gone.json").write_text("{}", encoding="utf-8")
    commit_config_dir(tmp_path, "initial")
    assert "gone.json" in _git(tmp_path, "ls-files").stdout.split()

    (tmp_path / "gone.json").unlink()
    commit_config_dir(tmp_path, "auto: sweep")

    assert "gone.json" not in _git(tmp_path, "ls-files").stdout.split()
    log = _git(tmp_path, "log", "--oneline", "--", "gone.json").stdout
    assert "auto: sweep" in log  # the deletion is its own commit
