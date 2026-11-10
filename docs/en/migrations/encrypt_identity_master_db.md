# encrypt_identity_master_db.py — identity.db / master.db nach SQLCipher migrieren

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/migrations/encrypt_identity_master_db.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Encrypts a so-far unencrypted identity.db or master.db with SQLCipher using the same key as health.db — with a backup outside the config folder, a byte-exact copy check, conversion via sqlcipher_export, verification by row counts per table and PRAGMA integrity_check, and atomic replacement only with --yes.

## Relevance

Closes the gap that the pseudonym mappings and the central instance registry lay around in plaintext

## Method

Per target file: (1) abort if the file is already encrypted (no 'SQLite format 3' header) or no key is configured; (2) copy it into the backup folder (default ~/kyoro-backups/<timestamp>/, folder 700, file 600, existing -wal/-shm sidecars copied along), byte-exact comparison via SHA-256; (3) create the encrypted copy next to it via ATTACH ... KEY and sqlcipher_export; (4) open the encrypted copy through the central opener (open_identity_db/open_master_db), compare row counts per table with the original and run PRAGMA integrity_check; (5) only with --yes: atomically replace the original via rename (the backup stays, the original's old -wal/-shm files are removed). Without --yes the original stays unchanged and the encrypted copy is removed again (dry run). Output prints counts only, never values; at the end the command for the way back is printed (copy the backup back).

## Data flow

- **Reads:** `identity.db`, `bzw.`, `master.db`, `(Klartext-Original)`, `health_config.json/db.key/KYORO_DB_KEY`, `(Schlüssel-Lookup)`
- **Writes:** `~/kyoro-backups/<Zeitstempel>/ (Sicherung), die Zieldatei selbst nur mit --yes (atomar), temporäre *.encrypted-Kopie daneben`

## Limitations

Defaults to a dry run (--yes needed for the replacement). Prints counts only, never values. Aborts when the file is already encrypted, missing, or no key is available. Database backups never belong in the config folder (see config_backup.py exclusions).

## Usage

```bash
# Trockenlauf (Standard): prüft und meldet, ändert nichts
python3 scripts/migrations/encrypt_identity_master_db.py --target both
# Ausführen: identity.db und master.db ersetzen, Sicherung bleibt liegen
python3 scripts/migrations/encrypt_identity_master_db.py --target both --yes
# Anderer Sicherungsordner
python3 scripts/migrations/encrypt_identity_master_db.py --target identity --backup-dir ~/sicherungen --yes
```
