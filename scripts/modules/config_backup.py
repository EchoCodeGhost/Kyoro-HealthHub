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
             Schreibvorgang blockieren.
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
             never block an actual clinical write.
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

import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path


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
    remote is ever configured). No-op if it already is one. Best-effort —
    a git failure here must never block the caller's actual data write.

    Sets a fixed local (repo-scoped, not global) commit identity — this repo
    exists purely as a local change log for one config directory, not
    something a human signs commits in by hand, and a machine with no
    global user.name/user.email configured (e.g. a fresh CI runner) would
    otherwise make every commit silently fail."""
    if (config_dir / ".git").exists():
        return
    try:
        subprocess.run(["git", "init", "-q"], cwd=config_dir,
                        check=True, capture_output=True)
        subprocess.run(["git", "branch", "-q", "-m", "main"], cwd=config_dir,
                        capture_output=True)
        subprocess.run(["git", "config", "user.name", "Kyoro Config"],
                        cwd=config_dir, capture_output=True)
        subprocess.run(["git", "config", "user.email", "kyoro-config@localhost"],
                        cwd=config_dir, capture_output=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass


def _stage_and_commit(config_dir: Path, add_args: list[str], message: str) -> None:
    """Shared implementation for commit_config_change()/commit_config_dir():
    stage `add_args` (git add arguments) and commit with `message` if
    anything actually changed. Calls ensure_git_repo() itself. Best-effort —
    a git failure here must never block the caller's actual data write."""
    ensure_git_repo(config_dir)
    if not (config_dir / ".git").exists():
        return
    try:
        subprocess.run(["git", "add", *add_args], cwd=config_dir, capture_output=True)
        staged = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=config_dir)
        if staged.returncode == 0:
            return
        subprocess.run(["git", "commit", "-q", "-m", message], cwd=config_dir,
                        capture_output=True)
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
    heard of this module). No-op if there's nothing to commit."""
    _stage_and_commit(config_dir, ["-A"], message)
