# Symptom canonicalisation: symptoms -> symptoms_canonical.

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/compute/compute_symptoms.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Normalises raw symptom labels (DE/EN, various apps) onto a unified canonical vocabulary. Pure vocabulary mapping.

## Relevance

Enables symptom analysis, essential for clinical diagnostics

## Method

Each label is mapped via the mapping file to canonical DE/EN terms. Unmapped entries are carried over 1:1 (category='other').

## Data flow

- **Reads:** `symptoms`
- **Writes:** `symptoms_canonical`

## Limitations

Deliberately no ICD-10 coding — symptom mapping files are not maintained as a verified diagnostic coding source (see commit history). Unmapped symptoms remain uncategorised.

## Usage

```bash
python3 compute_symptoms.py
python3 compute_symptoms.py --update
python3 compute_symptoms.py --list-unmapped
```
