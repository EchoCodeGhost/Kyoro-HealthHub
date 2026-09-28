# export_to_ods.py — Exportiert Infektionsanalysen als OpenOffice-Tabellen

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/analysis/infectious/export_to_ods.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Reads output files from infection analyses and converts them into sortable/filterable OpenOffice spreadsheets (.ods).

## Relevance

Supports infection-related data analysis and decision-making through systematic processing of wearable and symptom data in sortierbare/filterbare OpenOffice-Tabellen (.ods).

## Method

Reads JSON/CSV outputs from analyses/ and writes .ods files via odfpy. Supports outbreak_exposure and postinfectious types.

## Data flow

- **Reads:** `analyses/infectious/`, `analyses/postinfectious/`
- **Writes:**

  ```
  analyses/infectious/outbreak_exposure_tabellen.ods,
  analyses/postinfectious/postinfectious_tabellen.ods,
  analyses/infectious_analysen.ods
  ```

## Limitations

Requires odfpy. No DB connection — reads analysis output files only.

## Usage

```bash
python3 export_to_ods.py
python3 export_to_ods.py --type outbreak_exposure
python3 export_to_ods.py --type postinfectious
python3 export_to_ods.py --all
```
