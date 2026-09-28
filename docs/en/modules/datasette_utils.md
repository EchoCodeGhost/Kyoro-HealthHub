# datasette_utils.py — Shared SQLCipher-aware decrypt-to-temp helper for Datasette.

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/modules/datasette_utils.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Provides a shared function that decrypts a (possibly SQLCipher- encrypted) health.db into a temporary unencrypted copy so Datasette can access it.

## Relevance

Prevents every Datasette caller from reimplementing SQLCipher decryption independently (and possibly inconsistently) — central to correct access to encrypted instance databases.

## Method

With db_key set: SQLCipher export via ATTACH+sqlcipher_export() into a temp file. Without db_key: plain copy. Caller is responsible for deleting the temp file (e.g. via atexit).

## Data flow

- **Reads:** `die`, `übergebene`, `db_path`
- **Writes:** `Temporäre Datei im System-Temp-Verzeichnis`

## Limitations

Requires sqlcipher3 if db_key is set. No locking against concurrent writes to the source file during export. The temp file is chmod'd to owner-only (0600) since the system temp directory is shared across all local users.

## Usage

```bash
from modules.datasette_utils import decrypt_to_temp
tmp_path = decrypt_to_temp(db_path, db_key, "kyoro_health.db")
```
