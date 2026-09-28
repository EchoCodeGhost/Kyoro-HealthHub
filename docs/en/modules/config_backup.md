# config_backup.py — Backup and chain-of-custody commit for local config files

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/modules/config_backup.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Backs up an existing local config/history file (JSON under a KYORO_CONFIG_DIR — one per Kyoro instance) before it gets overwritten, so a buggy or unintended write (e.g. a test run whose isolation leaked) never permanently destroys the prior state. In addition: a local-only (never remote-connected) git repo per instance directory, so every change to a medically relevant config file stays traceable with a commit message — who/why, not just an anonymous timestamped snapshot.

## Relevance

Enables configuration management, essential for system settings

## Method

Copies the file (if present) to _backups/<name>.bak.<ISO timestamp> (a subdirectory, so the config directory itself doesn't fill up with backup files) before it gets overwritten. No-op if the file doesn't exist yet (first write). `ensure_git_repo()` idempotently initialises a directory as a local git repo (no remote is ever configured). `commit_config_change()` stages and commits a single file; `commit_config_dir()` stages and commits ANY change anywhere in the directory (`git add -A`) — health_config.py calls the latter automatically on every module import AND at process exit (atexit), so every change to a config file gets captured regardless of whether the writing code knows about commit_config_change() at all, or was even a manual edit outside Python. Both commit functions call ensure_git_repo() themselves (self-healing for instances created before this function existed) and are deliberately fault-tolerant (catch `CalledProcessError`/`FileNotFoundError`) — a git hiccup must never block an actual clinical write.

## Data flow

- **Reads:** `Die`, `zu`, `sichernde`, `Datei`, `(falls`, `vorhanden);`, `.git-Verzeichnis-Status`
- **Writes:** `_backups/<datei>.bak.<timestamp>; .git-Repo + Commits im selben Verzeichnis`

## Limitations

No automatic pruning of old backups — grows with every write. Deliberate tradeoff (safety over disk space for these small JSON files). Only covers the KYORO_CONFIG_DIR layer (JSON files) — not the databases (health.db/medicine.db), see the audit triggers in utils/create_schema.py for those.

## Usage

```bash
from modules.config_backup import backup_before_write, commit_config_change
backup_before_write(HISTORY_FILE)
HISTORY_FILE.write_text(...)
commit_config_change(HISTORY_FILE, "family_history: add entry for Mutter")
```
