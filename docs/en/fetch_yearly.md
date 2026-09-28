# Yearly Fetch — lädt Referenzdaten von externen Quellen und speichert sie lokal.

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/fetch_yearly.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Downloads ECHA-SVHC candidate list (chronic risk substances: carcinogens, mutagens, reproductive toxicants, endocrine disruptors) and CosIng annex data (substances prohibited/restricted in EU cosmetics) as local CSV files. Enables allergen matching without repeated network requests and keeps reference data current through annual refresh.

## Relevance

Provides health data functions, essential for medical data processing

## Method

1. Downloads ECHA-SVHC candidate list from ECHA website (CSV/Excel → CSV) 2. Downloads CosIng Annex II (prohibited substances) and Annex III (restricted substances) from EU Commission website 3. Stores all data in data/reference/ (echa_svhc.csv, cosing_annex_ii.csv, cosing_annex_iii.csv) 4. Updates manifest.json with last fetch date per source 5. Each source is attempted independently; errors in one source don't break the entire process

## Data flow

- **Reads:** `ECHA-Website`, `(https://echa.europa.eu)`, `EU-Kommission`, `CosIng-Daten`
- **Writes:**

  ```
  data/reference/echa_svhc.csv, data/reference/cosing_annex_ii.csv,
  data/reference/cosing_annex_iii.csv, data/reference/manifest.json
  ```

## Limitations

Dependent on availability and format of download sources. Sources may change their format; manual parser adjustment may be needed. No live update — reference data is only updated by re-running this script.

## Usage

```bash
python scripts/fetch_yearly.py
python scripts/fetch_yearly.py --force
python scripts/fetch_yearly.py --check
```
