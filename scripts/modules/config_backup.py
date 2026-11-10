# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
config_backup.py — Backup and chain-of-custody commit for local config files

@tier        infrastructure
@purpose.de  Sichert eine bestehende lokale Config-/History-Datei (JSON unter
             einem KYORO_CONFIG_DIR — je Patient-Instanz eigenständig) vor
             dem Überschreiben, damit ein fehlerhafter oder unbeabsichtigter
             Schreibvorgang (z.B. ein nicht sauber isolierter Testlauf) den
             vorherigen Stand nicht endgültig zerstört. Ergänzend: ein
             lokales (nie mit Remote verbundenes) Git-Repo je Instanz-
             Verzeichnis, damit jede Änderung an medizinisch relevanten
             Config-Dateien mit Commit-Nachricht nachvollziehbar bleibt —
             wer/warum, nicht nur ein anonymer Zeitstempel-Schnappschuss.
@purpose.en  Backs up an existing local config/history file (JSON under a
             KYORO_CONFIG_DIR — one per Kyoro instance) before it gets
             overwritten, so a buggy or unintended write (e.g. a test run
             whose isolation leaked) never permanently destroys the prior
             state. In addition: a local-only (never remote-connected) git
             repo per instance directory, so every change to a medically
             relevant config file stays traceable with a commit message —
             who/why, not just an anonymous timestamped snapshot.
@method.de   Kopiert die Datei (falls vorhanden) nach _backups/<name>.bak.<ISO-Timestamp>
             (eigener Unterordner, damit das Konfig-Verzeichnis nicht mit
             Backup-Dateien zumüllt), bevor sie überschrieben wird. No-op wenn
             die Datei noch nicht existiert (erster Schreibvorgang).
             `ensure_git_repo()` initialisiert ein Verzeichnis idempotent als
             lokales Git-Repo (kein Remote wird je konfiguriert).
             `commit_config_change()` staged und committet eine einzelne
             Datei; `commit_config_dir()` staged und committet ALLE
             Änderungen im Verzeichnis (`git add -A`) — Letzteres nutzt
             health_config.py automatisch bei jedem Modul-Import UND bei
             Prozessende (atexit), damit JEDE Änderung an einer Config-Datei
             erfasst wird, unabhängig davon, ob der schreibende Code
             `commit_config_change()` kennt oder sogar ein manueller Edit
             außerhalb von Python war. Beide Commit-Funktionen rufen
             `ensure_git_repo()` selbst auf (Selbstheilung für Instanzen,
             die vor dieser Funktion angelegt wurden) und sind bewusst
             fehlertolerant (fangen `CalledProcessError`/`FileNotFoundError`
             ab) — ein Git-Problem darf nie einen echten klinischen
             Schreibvorgang blockieren. Datenbanken, ihre Kopien, WAL/SHM- und
             *.sqlite-Dateien landen über `.git/info/exclude` nie im Archiv
             (ensure_git_repo() trägt die Ausschlüsse idempotent ein);
             `commit_config_dir()` schließt Dateien über 5 MB schon VOR dem
             Staging aus (ermittelt über `git status --porcelain -z`, das
             ungetrackte Dateien nicht hasht) und loggt nur ihre Namen, nie Inhalte.
@method.en   Copies the file (if present) to _backups/<name>.bak.<ISO timestamp>
             (a subdirectory, so the config directory itself doesn't fill up
             with backup files) before it gets overwritten. No-op if the file
             doesn't exist yet (first write).
             `ensure_git_repo()` idempotently initialises a directory as a
             local git repo (no remote is ever configured).
             `commit_config_change()` stages and commits a single file;
             `commit_config_dir()` stages and commits ANY change anywhere
             in the directory (`git add -A`) — health_config.py calls the
             latter automatically on every module import AND at process
             exit (atexit), so every change to a config file gets captured
             regardless of whether the writing code knows about
             commit_config_change() at all, or was even a manual edit
             outside Python. Both commit functions call ensure_git_repo()
             themselves (self-healing for instances created before this
             function existed) and are deliberately fault-tolerant (catch
             `CalledProcessError`/`FileNotFoundError`) — a git hiccup must
             never block an actual clinical write. Databases, their copies,
             WAL/SHM and *.sqlite files never land in the archive
             (`.git/info/exclude`, written idempotently by ensure_git_repo());
             commit_config_dir() excludes files above 5 MB BEFORE staging
             (paths come from `git status --porcelain -z`, which does not hash
             untracked files) and logs only their names, never contents.
@reads       Die zu sichernde Datei (falls vorhanden); .git-Verzeichnis-Status
@writes      _backups/<datei>.bak.<timestamp>; .git-Repo + Commits im selben Verzeichnis
@limits.de   Kein automatisches Aufräumen historischer Backups — wächst mit
             jedem Schreibvorgang. Bewusst so belassen (Sicherheit vor
             Speicherplatz bei diesen kleinen JSON-Dateien). Deckt nur die
             KYORO_CONFIG_DIR-Ebene ab (JSON-Dateien) — nicht die
             Datenbanken (health.db/medicine.db), dafür siehe die
             Audit-Trigger in utils/create_schema.py.

@relevance.de  Ermöglicht die Konfigurationsverwaltung, essentiell für die Systemeinstellungen
@relevance.en  Enables configuration management, essential for system settings
@limits.en   No automatic pruning of old backups — grows with every write.
             Deliberate tradeoff (safety over disk space for these small
             JSON files). Only covers the KYORO_CONFIG_DIR layer (JSON
             files) — not the databases (health.db/medicine.db), see the
             audit triggers in utils/create_schema.py for those.
@usage
    from modules.config_backup import backup_before_write, commit_config_change
    backup_before_write(HISTORY_FILE)
    HISTORY_FILE.write_text(...)
    commit_config_change(HISTORY_FILE, "family_history: add entry for Mutter")

    from modules.config_backup import ensure_git_repo, commit_config_dir
    ensure_git_repo(new_patient_config_dir)  # at instance creation time
    commit_config_dir(KYORO_CONFIG_DIR, "auto: external change detected")
"""

import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# Datenbanken, deren Kopien, WAL/SHM-Sidecars und SQLite-Dateien gehören nie
# in das Config-Archiv (siehe OpenSpec identity-store-encryption): Sie landen in
# .git/info/exclude, damit `git add -A` sie nicht staged.
_DB_EXCLUDE_PATTERNS = ("*.db", "*.db.*", "*-wal", "*-shm", "*.sqlite")

# Dateien über diesem Limit werden von commit_config_dir() übersprungen und nur
# mit Namen geloggt (nie Inhalte) — ein versehentlich abgelegtes 30-GB-DB-Backup
# darf den Config-Commit nicht aufblähen.
_SIZE_LIMIT_BYTES = 5 * 1024 * 1024


def _write_exclude_patterns(config_dir: Path) -> None:
    """Fehlende Datenbank-Ausschlüsse in .git/info/exclude eintragen (idempotent).
    Best-effort: ein Fehler darf den eigentlichen Schreibvorgang nie blockieren."""
    exclude = config_dir / ".git" / "info" / "exclude"
    try:
        existing = exclude.read_text(encoding="utf-8").splitlines() if exclude.exists() else []
        missing = [p for p in _DB_EXCLUDE_PATTERNS if p not in existing]
        if not missing:
            return
        exclude.parent.mkdir(parents=True, exist_ok=True)
        with open(exclude, "a", encoding="utf-8") as fh:
            if existing and existing[-1].strip():
                fh.write("\n")
            fh.write("\n".join(missing) + "\n")
    except OSError:
        pass


def _git(config_dir: Path, *args: str, **kwargs) -> subprocess.CompletedProcess:
    """Run git on `config_dir`'s own repo, never on whatever repo the caller
    is running in. git exports GIT_DIR/GIT_INDEX_FILE/GIT_WORK_TREE to hooks;
    health_config.py's import-time sweep runs inside the Kyoro pre-commit
    hook (via qa_check.py), and with those variables inherited, `git add -A`
    and `git commit` with cwd=config_dir staged the config directory into
    the Kyoro repo being committed instead. Strip every GIT_* variable and
    pin --git-dir/--work-tree explicitly."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    return subprocess.run(
        ["git", f"--git-dir={config_dir / '.git'}", f"--work-tree={config_dir}", *args],
        cwd=config_dir, env=env, **kwargs)


def backup_before_write(path: Path) -> None:
    """Copy `path` to a timestamped `.bak` file under a `_backups/`
    subdirectory of its parent, before it gets overwritten — kept out of
    the config directory itself so it doesn't clutter it alongside the
    live JSON files."""
    if not path.exists():
        return
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backups_dir = path.parent / "_backups"
    backups_dir.mkdir(parents=True, exist_ok=True)
    backup_path = backups_dir / f"{path.name}.bak.{stamp}"
    shutil.copy2(path, backup_path)


def ensure_git_repo(config_dir: Path) -> None:
    """Idempotently initialise `config_dir` as a local-only git repo (no
    remote is ever configured) and make sure the database exclusions are in
    .git/info/exclude — also for repos that predate this feature (self-healing
    on every call, not just on init). Best-effort — a git failure here must
    never block the caller's actual data write.

    Sets a fixed local (repo-scoped, not global) commit identity — this repo
    exists purely as a local change log for one config directory, not
    something a human signs commits in by hand, and a machine with no
    global user.name/user.email configured (e.g. a fresh CI runner) would
    otherwise make every commit silently fail."""
    if not (config_dir / ".git").exists():
        try:
            _git(config_dir, "init", "-q", check=True, capture_output=True)
            _git(config_dir, "branch", "-q", "-m", "main", capture_output=True)
            _git(config_dir, "config", "user.name", "Kyoro Config", capture_output=True)
            _git(config_dir, "config", "user.email", "kyoro-config@localhost",
                 capture_output=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            return
    _write_exclude_patterns(config_dir)


def _changed_paths(config_dir: Path) -> "list[str] | None":
    """All changed and new paths vs HEAD, via `git status --porcelain -z
    --untracked-files=all`. Unlike `git add -A`, git status does NOT read and
    hash untracked files — a huge stray file in the config dir is only stat'ed,
    never read. Returns None if git itself failed (caller falls back to the
    plain `git add -A` sweep). With -z, paths are NUL-separated and unquoted;
    rename/copy entries carry the original path as a second NUL-separated field."""
    try:
        out = _git(config_dir, "status", "--porcelain", "-z", "--untracked-files=all",
                   capture_output=True, text=True).stdout
    except (subprocess.CalledProcessError, FileNotFoundError, UnicodeDecodeError):
        return None
    paths: list[str] = []
    items = out.split("\0")
    i = 0
    while i < len(items):
        entry = items[i]
        i += 1
        if len(entry) < 4:
            continue
        status, name = entry[:2], entry[3:]
        paths.append(name)
        if status[0] in "RC":  # rename/copy: next field is the original path
            i += 1
    return paths


def _stage_dir_skipping_oversized(config_dir: Path) -> "list[str] | None":
    """Stage every changed/new path except files above _SIZE_LIMIT_BYTES, so
    git add never reads/hashes an oversized file at all. Returns the skipped
    names (only names are ever logged, never contents); deleted files have no
    file on disk and are always staged as deletions. Returns None if
    `git status` failed — the caller then falls back to the plain sweep."""
    changed = _changed_paths(config_dir)
    if changed is None:
        return None
    skipped: list[str] = []
    keep: list[str] = []
    for name in changed:
        try:
            path = config_dir / name
            if path.is_file() and path.stat().st_size > _SIZE_LIMIT_BYTES:
                skipped.append(name)
                continue
        except OSError:
            pass
        keep.append(name)
    if keep:
        _git(config_dir, "add", "-A", "--", *keep, capture_output=True)
    return skipped


def _unstage_oversized(config_dir: Path) -> list[str]:
    """Unstage files above _SIZE_LIMIT_BYTES and return their names (only the
    names are ever logged, never contents). The .git/info/exclude patterns
    already keep untracked databases out; this catches files that were staged
    anyway (e.g. tracked before the exclusions existed, or a large non-DB file)."""
    skipped: list[str] = []
    try:
        out = _git(config_dir, "diff", "--cached", "--name-only",
                   capture_output=True, text=True).stdout
        for name in out.splitlines():
            path = config_dir / name
            try:
                if path.is_file() and path.stat().st_size > _SIZE_LIMIT_BYTES:
                    _git(config_dir, "reset", "-q", "--", name, capture_output=True)
                    skipped.append(name)
            except OSError:
                pass
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    return skipped


def _stage_and_commit(config_dir: Path, add_args: list[str], message: str,
                      skip_large: bool = False) -> None:
    """Shared implementation for commit_config_change()/commit_config_dir():
    stage `add_args` (git add arguments) and commit with `message` if
    anything actually changed. Calls ensure_git_repo() itself. Best-effort —
    a git failure here must never block the caller's actual data write.

    With skip_large=True (the commit_config_dir() sweep), oversized files are
    excluded BEFORE staging: the changed paths come from `git status
    --porcelain -z --untracked-files=all`, which does not read/hash untracked
    files, and only the remaining paths are passed to `git add -A -- <paths>`.
    _unstage_oversized() still runs afterwards as a second safety net."""
    ensure_git_repo(config_dir)
    if not (config_dir / ".git").exists():
        return
    try:
        skipped: list[str] = []
        if skip_large:
            selective = _stage_dir_skipping_oversized(config_dir)
            if selective is None:
                # git status failed — fall back to the plain sweep
                _git(config_dir, "add", *add_args, capture_output=True)
                skipped = _unstage_oversized(config_dir)
            else:
                skipped = selective + _unstage_oversized(config_dir)
            if skipped:
                print(
                    f"[config_backup] Dateien über {_SIZE_LIMIT_BYTES // (1024 * 1024)} MB "
                    f"übersprungen (nur Namen): {', '.join(sorted(skipped))}",
                    file=sys.stderr,
                )
        else:
            _git(config_dir, "add", *add_args, capture_output=True)
        staged = _git(config_dir, "diff", "--cached", "--quiet")
        if staged.returncode == 0:
            return
        _git(config_dir, "commit", "-q", "-m", message, capture_output=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass


def commit_config_change(path: Path, message: str) -> None:
    """Stage and commit `path` (already written by the caller) in its
    enclosing config-directory git repo, with `message` stating who/why.
    No-op if there's nothing to commit (identical content) or if git isn't
    available."""
    _stage_and_commit(path.parent, ["--", path.name], message)


def commit_config_dir(config_dir: Path, message: str) -> None:
    """Stage and commit ANY uncommitted change anywhere in `config_dir` —
    not just one known file. Used by health_config.py's automatic import-
    time/exit-time sweep so a change gets captured regardless of which code
    path wrote it, or whether that path calls commit_config_change() at
    all (a direct file edit, a different tool, a future script that never
    heard of this module). No-op if there's nothing to commit.

    Databases, their copies, WAL/SHM files and *.sqlite files are never
    staged (.git/info/exclude, written idempotently by ensure_git_repo()).
    Files above the size limit are excluded BEFORE staging: the changed
    paths are taken from `git status --porcelain -z --untracked-files=all`
    (which does not read/hash untracked files, so a huge stray file is never
    hashed at all) and only the remaining paths are passed to
    `git add -A -- <paths>`. Only the skipped names are ever logged, never
    contents. _unstage_oversized() remains as a second safety net."""
    _stage_and_commit(config_dir, ["-A"], message, skip_large=True)
