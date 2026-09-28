# export_analyses_to_ods.py — Master-Exporter für alle Infektionsanalysen

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/analysis/infectious/export_analyses_to_ods.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Converts output files from all infection analysis scripts into sortable/filterable OpenOffice spreadsheets (.ods).

## Relevance

Supports infection-related data analysis and decision-making through systematic processing of wearable and symptom data sortierbare/filterbare OpenOffice-Tabellen (.ods).

## Method

Reads JSON/CSV/MD outputs from analyses/*/ and writes .ods files via odfpy. Supports outbreak_exposure, pathogen_exposure, postinfectious_diagnose, acute_response, and combined export.

## Data flow

- **Reads:** `analyses/infectious/`, `(outbreak_exposure_*.md`, `pathogen_exposure_*.md`, `acute_response_*.md)`, `analyses/postinfectious/`
- **Writes:** `analyses/*/..._tabellen.ods, analyses/infectious_analysen_kombiniert.ods`

## Limitations

Requires odfpy. No DB connection — reads analysis output files only.

## Usage

```bash
python3 export_analyses_to_ods.py
python3 export_analyses_to_ods.py --type outbreak_exposure
python3 export_analyses_to_ods.py --type all --output alle_infektionen.ods
python3 export_analyses_to_ods.py --recent-only
```
