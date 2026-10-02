# secure_io.py — Dateien mit Zugangsdaten ohne Lesbarkeits-Zeitfenster schreiben

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/modules/secure_io.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Writes config and key files holding tokens, passwords or the DB key directly with mode 0600.

## Relevance

Protects API tokens and the database key from being read by other local users

## Method

write_private_text() opens the file via os.open() with mode 0600 instead of writing with the default umask and calling chmod afterwards — in between, the file would briefly be readable by other users. Pre-existing files with looser permissions are set to 0600 via fchmod() before writing.

## Data flow

- **Reads:** `—`
- **Writes:** `die übergebene Datei / the given file`

## Limitations

On filesystems without POSIX permissions (e.g. FAT, some network shares) fchmod errors are ignored; the content is still written.

## Usage

```bash
from modules.secure_io import write_private_text
write_private_text(CONFIG_PATH, json.dumps(cfg, indent=2))
```
