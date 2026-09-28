# Kyoro SymptomTrack JSON-Export → health.db (symptoms)

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/importers/import_symptomtrack_export.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Imports Kyoro SymptomTrack JSON exports (GET /api/export) into the shared symptoms table. Allows symptom data from a second device (e.g. family member) to be ingested under a separate --person ID, without modifying the Kyoro SymptomTrack backend.

## Relevance

Enables import of symptom data, essential for clinical analysis

## Method

Reads symptomtrack_export_*.json files (field symptom_entries[]). Fields: id, timestamp (ISO 8601), symptom, kategorie, wert_num, wert_text, note, source. Writes to symptoms with source='symptomtrack_export' (INSERT OR IGNORE on PRIMARY KEY (date, symptom, person, source)). Migraine and AFib entries (migraine_entries, afib_entries) are Kyoro SymptomTrack-internal specialist tables with no equivalent in health.db and are skipped.

## Data flow

- **Reads:** `symptomtrack_export_YYYY-MM-DD.json`, `(Kyoro`, `SymptomTrack`, `/api/export`, `output)`
- **Writes:** `symptoms`

## Limitations

No re-import of migraine/AFib episodes. Day-level deduplication only via PRIMARY KEY — multiple entries for the same symptom on the same day are skipped after the first INSERT.

## Usage

```bash
python3 import_symptomtrack_export.py symptomtrack_export_2026-07-08.json
python3 import_symptomtrack_export.py symptomtrack_export.json --person oma
```
