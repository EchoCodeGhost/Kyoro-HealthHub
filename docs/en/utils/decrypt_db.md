# decrypt_db.py — SQLCipher-Verschlüsselung deaktivieren

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/utils/decrypt_db.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Deactivates SQLCipher encryption of a database by migrating to an unencrypted SQLite database.

## Relevance

Provides decryption functions for sensitive data, essential for secure data access

## Method

One-time migration: encrypted DB → unencrypted DB. After successful migration, db.key is removed; open_db() then uses plain sqlite3. Process: 1) Backup, 2) Create decrypted copy, 3) Verify integrity, 4) Replace original, 5) Clear db.key.

## Data flow

- **Reads:** `health.db`, `(verschlüsselt)`, `KYORO_CONFIG_DIR/db.key`
- **Writes:** `health.db (unverschlüsselt)`

## Limitations

Requires sqlcipher3. Sufficient free space (2× DB size).

## Usage

```bash
python3 scripts/utils/decrypt_db.py
python3 scripts/utils/decrypt_db.py --db medicine
python3 scripts/utils/decrypt_db.py --all
python3 scripts/utils/decrypt_db.py --dry-run
```
