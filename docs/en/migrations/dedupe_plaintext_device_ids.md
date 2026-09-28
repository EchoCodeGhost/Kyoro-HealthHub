# Klartext-Geräte-IDs nachträglich pseudonymisieren bzw. deduplizieren

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/migrations/dedupe_plaintext_device_ids.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Cleans up rows that carry a plaintext device id despite the pseudonymisation trigger. Such rows accumulated while the trigger was silently ineffective under INSERT OR IGNORE (fixed in modules/db.py) — they expose the device inventory and duplicate the affected measurements at the same time.

## Relevance

The device inventory is treated as sensitive in this project (docs/PRIVACY_ARCHITECTURE.md). Plaintext model names next to pseudonymised ids undermine exactly that protection.

## Method

Mirrors the trigger logic set-wise: first UPDATE OR IGNORE to the pseudonym; where that fails on the primary key, the pseudonymised row already exists and the plaintext row is a duplicate — it gets deleted. Devices that do NOT resolve (pseudonymize_* returns its input) are left untouched; deleting those would be data loss rather than deduplication.

## Data flow

- **Reads:** `health.db`, `(alle`, `Tabellen`, `mit`, `device_id/device-Spalte)`
- **Writes:** `health.db (device_id-Spalten, Löschung von Duplikat-Zeilen)`

## Limitations

Requires identity.db to be reachable — without a mapping nothing is changed. Unresolvable devices remain in plaintext and are reported at the end so they do not pass unnoticed.

## Usage

```bash
python3 scripts/migrations/dedupe_plaintext_device_ids.py --dry-run
python3 scripts/migrations/dedupe_plaintext_device_ids.py
```
