# Kyoro SymptomTrack CSV-Export → health.db (symptoms)

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/importers/import_kyoro_symptoms.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Imports Kyoro SymptomTrack CSV exports

## Relevance

Enables import of symptom data, essential for clinical analysis

## Method

Reads symptom-history*.csv exports from the Kyoro SymptomTrack app and writes to the common symptoms table (source='kyoro_st'). Compared to the symptom diary importer, Kyoro ST has: - full ISO timestamps (ts column) - body region (body_region column) - notes (notes column) PRIMARY KEY (date, symptom, person, source): for multiple entries of the same symptom on the same day, the entry with the highest value wins. CSV format (multi-sectional) with metadata, entries per day, etc.

## Data flow

- **Reads:** `CSV-Dateien`, `aus`, `imports/kyoro-ST/`
- **Writes:** `symptoms`

## Limitations

Multi-sectional format. Dependent on app export. run()/import_file() already threaded person through correctly, but main() had no --person flag, so it was still effectively hardcoded to the own person. Now added; --rebuild consequently only deletes the selected person's entries.

## Usage

```bash
python3 import_kyoro_symptoms.py            # alle CSVs in imports/kyoro-ST/
python3 import_kyoro_symptoms.py --update   # nur neue Eintraege
python3 import_kyoro_symptoms.py --file /pfad/symptom-history.csv
python3 import_kyoro_symptoms.py --rebuild  # kyoro_st-Eintraege loeschen + neu
python3 import_kyoro_symptoms.py --person PER-xxxxxxxx
```
