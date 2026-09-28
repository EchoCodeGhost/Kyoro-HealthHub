# db.py — Datenbankverbindung

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/modules/db.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

The single place in the project that opens a SQLite/SQLCipher connection. All scripts import open_db from here.

## Relevance

Provides database functions, essential for data persistence

## Method

Manages database key lookup in priority order: 1) Environment variable KYORO_DB_KEY, 2) System keyring, 3) ~/.config/kyoro/db.key, 4) health_config.json["db_key"]. Supports both SQLite and SQLCipher. Every opened connection automatically gets DB-internal chain-of-custody triggers (audit_log table, UPDATE/DELETE on every table) — fires regardless of the calling code, even access via the sqlite3 CLI or Datasette.

## Data flow

- **Reads:** `DB-Datei`, `(health.db`, `oder`, `health_encrypted.db)`
- **Writes:** `DB-Datei (über SQLite/SQLCipher); audit_log-Tabelle + Trigger (automatisch)`

## Limitations

Single DB access point. Changes break all scripts. SQLCipher requires pysqlcipher3. Audit triggers cover UPDATE/DELETE only, not INSERT (performance on million-row bulk imports, see _install_audit_log_triggers's docstring). Callers catching DB errors from a connection obtained via open_db() must use DB_ERRORS/DB_OPERATIONAL_ERRORS from this module, not sqlite3.Error/sqlite3.OperationalError directly — when db_key is set, the connection is a sqlcipher3.dbapi2.Connection whose exceptions do not inherit from stdlib sqlite3.Error.

## Usage

```bash
from modules.db import open_db, DB_ERRORS, DB_OPERATIONAL_ERRORS
conn = open_db()
try:
    conn.execute(...)
except DB_ERRORS as e:
    ...
```
