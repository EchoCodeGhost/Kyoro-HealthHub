# manage_shared_devices.py — Gemeinsamer Geräte-Katalog (Provisionierungsquelle)

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/utils/manage/shared_access/manage_shared_devices.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Manages a shared catalog of shared devices (e.g. a household's shared blood-pressure monitor) as a copy template for new person instances — not shared runtime state. Built for the private multi-person context, see SHARED_ACCESS_DEPLOYMENT.md.

## Relevance

Provides health data functions, essential for medical data processing

## Method

Reads/writes ~/.config/kyoro-master/master.db (table practice_devices, always in the real operator home, not an active person instance). `manage_people.py add` can copy entries from it into the new instance config (one-time, independent afterward).

## Data flow

- **Reads:** `~/.config/kyoro-master/master.db`, `(practice_devices)`
- **Writes:** `~/.config/kyoro-master/master.db (practice_devices)`

## Limitations

Not shared state after copying — catalog changes do NOT affect already-created instances (intentional, otherwise an isolation violation). No person data in this table.

## Usage

```bash
python3 scripts/utils/manage/shared_access/manage_shared_devices.py list
python3 scripts/utils/manage/shared_access/manage_shared_devices.py add omron-haushalt-1 Omron "X7 Smart" AABBCC112233 bp_monitor
python3 scripts/utils/manage/shared_access/manage_shared_devices.py remove omron-haushalt-1
```
