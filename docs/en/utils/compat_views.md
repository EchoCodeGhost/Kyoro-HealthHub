# compat_views — v1 zu v2 Kompatibilitäts-Views für Rückwärtskompatibilität

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/utils/compat_views.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Creates compatibility views mapping old v1 table names to new v2 sources. The v2 migration moved time series to EAV schema (measurements/sessions) and renamed compute outputs to *_new, but many readers (analysis/compute/query scripts) still use the old v1 table names. These views allow existing scripts to continue working without "no such table" errors.

## Relevance

Provides utility functions for data processing, essential for system functionality

## Method

Creates two types of views: 1. Real-backed views: Map old names to real v2 tables with SQL transformations (e.g., heart_rate → measurements WHERE metric='heart_rate'). 2. Stub views: Empty views (WHERE 0) with documented columns for sources without imported data, so scripts don't break with "no such table". Skips views if a real table with the same name already exists. Defensively drops potentially broken views (v_solar) as they will be recreated by analysis scripts if needed.

## Data flow

- **Reads:** `health.db`, `(diverse`, `Tabellen`, `für`, `View-Definitionen)`
- **Writes:** `health.db (neue Views: heart_rate, apple_records, apple_workouts, sleep, training, etc.)`

## Limitations

Views are read-only and based on underlying tables. Scripts using old table names will continue to work.

## Usage

```bash
python scripts/utils/compat_views.py
# Erstellt alle Kompatibilitäts-Views in der configurierten Datenbank
# kannst auch als Modul importiert und manuell aufgerufen werden:
# from utils.compat_views import apply; apply(conn)
```
