# manage_risk_markers.py — Eigene Risikomarker und genetische Befunde verwalten

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/utils/manage/personal/manage_risk_markers.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Documents own genetic variants, lab findings with genetic significance, hereditary risks (derived from family history) and clinical phenotypes with genetic component. Shows pending tests and actions at a glance.

## Relevance

Provides health data functions, essential for medical data processing

## Method

Stores in KYORO_CONFIG_DIR/own_risk_markers.json (local only, not in repo). Categories: lab finding, genetic variant, clinical phenotype, hereditary risk, immunological. Status: confirmed/suspected/pending. --pending shows only entries with open action items.

## Data flow

- **Reads:** `KYORO_CONFIG_DIR/own_risk_markers.json`
- **Writes:** `KYORO_CONFIG_DIR/own_risk_markers.json`

## Limitations

Not a substitute for genetic counseling. No automatic risk calculation.

## Usage

```bash
python3 scripts/utils/manage/personal/manage_risk_markers.py list
python3 scripts/utils/manage/personal/manage_risk_markers.py list --pending
python3 scripts/utils/manage/personal/manage_risk_markers.py add
python3 scripts/utils/manage/personal/manage_risk_markers.py edit 3
python3 scripts/utils/manage/personal/manage_risk_markers.py delete 3
python3 scripts/utils/manage/personal/manage_risk_markers.py export
```
