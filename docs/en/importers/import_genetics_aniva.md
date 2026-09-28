# import_genetics_aniva.py — Aniva Health Biomarker- und Genetik-Daten importieren

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/importers/import_genetics_aniva.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Imports Aniva Health data in two modes: 1. Biomarker CSV (standard membership): 100+ blood markers → lab_manual 2. Genetics CSV (genetics add-on): SNP panel → genetic_risk_markers Aniva is a longevity platform with biological age assessment, personalized recommendations, and optional genetics add-on.

## Relevance

Enables import of genetic data, essential for genetic analysis

## Method

Mode 1 (--mode biomarker): Reads Aniva biomarker CSV (template: templates/aniva_biomarker_template.csv) → lab_manual. Mode 2 (--mode genetics): Reads Aniva genetics CSV (template: templates/genetics_manual_template.csv) → genetic_risk_markers. Auto-detects mode from CSV column headers if --mode is omitted.

## Data flow

- **Reads:** `CSV-Datei`, `(Aniva`, `Dashboard-Export`, `oder`, `manuell`, `ausgefüllt)`
- **Writes:**

  ```
  health.db:lab_manual (Biomarker), health.db:genetic_risk_markers (Genetik),
  health.db:import_log
  ```

## Limitations

Aniva does not provide a standardized machine export (as of 2026). Data must be manually transferred from the dashboard into the template. For biological age: value in years stored in lab_manual (parameter='Biologisches Alter').

## Usage

```bash
# Biomarker (Standard-Mitgliedschaft):
python3 scripts/importers/import_genetics_aniva.py aniva_biomarker_2026-01.csv
python3 scripts/importers/import_genetics_aniva.py aniva_biomarker.csv --mode biomarker --dry-run
```
