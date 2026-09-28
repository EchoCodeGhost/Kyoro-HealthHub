# export_health.py — Themenspezifische Gesundheitsdaten-Exporte

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/export_health.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Exports curated health data packages from health.db and medicine.db

## Relevance

Provides health data functions, essential for medical data processing

## Method

Exports data from health.db and medicine.db as CSV or JSON based on profile definitions. Each profile query is routed to the correct database by its FROM table (lab_manual/lab_results/medications/assessments -> medicine.db, everything else -> health.db; see MEDICINE_DB_TABLES). Profile definitions are stored as JSON files in scripts/exporters/profiles/. Supports filtering by date, person, and output format.

## Data flow

- **Reads:** `health.db`, `medicine.db`, `Profil-Definitionen`, `aus`, `scripts/exporters/profiles/`
- **Writes:** `Exportierte CSV/JSON-Dateien in exports/-Verzeichnis`

## Limitations

Data selection based on profiles. No automatic anonymisation.

## Usage

```bash
python export_health.py --profile cardiology --from 2026-01-01 --format csv
python export_health.py --profile general_practitioner --last 365d --person self
python export_health.py --profile research --person all --format json
python export_health.py --list                  # alle verfügbaren Profile
```
