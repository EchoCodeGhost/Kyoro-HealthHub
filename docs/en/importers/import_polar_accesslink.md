# Polar AccessLink API v3 → health.db

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/importers/import_polar_accesslink.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Imports sleep data, nightly recharge, HRV and training sessions from Polar AccessLink API v3 directly into health.db.

## Relevance

Enables import of heart rate and activity data from Polar devices, essential for cardiac analysis

## Method

OAuth2 Authorization Code Flow (one-time via --setup, token stored locally). Then: Sleep + Nightly Recharge by date range, Exercise transactions (only new data since last commit). Writes sleep → sessions + session_metrics, metrics → measurements.

## Data flow

- **Reads:** `Polar`, `AccessLink`, `API`, `(https://www.polaraccesslink.com/v3)`
- **Writes:** `health.db (sessions, session_metrics, measurements)`

## Limitations

Exercise transactions only deliver new data since last API call (transaction model). Historical data: import_polar.py (GDPR export).

## Usage

```bash
python3 import_polar_accesslink.py --setup           # einmalig: OAuth2 + User-Registrierung
python3 import_polar_accesslink.py --setup --manual  # SSH/kein Browser: Link ausgeben, Code eingeben
python3 import_polar_accesslink.py --update      # nur neue Daten
python3 import_polar_accesslink.py               # ab data_start
python3 import_polar_accesslink.py --from 2026-01-01 --to 2026-07-10
```
