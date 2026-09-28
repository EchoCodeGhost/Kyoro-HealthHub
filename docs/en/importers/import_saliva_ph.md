# import_saliva_ph.py — Speichel-pH-Messungen importieren

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/importers/import_saliva_ph.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Imports saliva pH home-monitoring data from CSV templates into medicine.db. Reference ranges are loaded context-dependently from ~/.config/kyoro/saliva_ph_ranges.json — adjust individual thresholds (e.g. MCAS-specific) there, not in the script.

## Relevance

Enables import of health data, essential for comprehensive data analysis

## Method

Reads CSV (template: templates/saliva_ph_template.csv) and writes each measurement as a row in lab_manual (parameter="Speichel-pH"). Context (fasting_morning, post_meal_1h …) is stored in kommentar, ref_min/ref_max come from the JSON configuration.

## Data flow

- **Reads:** `CSV-Datei`, `(Template-Format)`, `~/.config/kyoro/saliva_ph_ranges.json`
- **Writes:** `lab_manual, import_log`

## Limitations

pH strips are typically ±0.5 accurate; value stored as measured. Unknown context keys are imported as "unknown" (no reference values).

## Usage

```bash
python3 scripts/importers/import_saliva_ph.py datei.csv
python3 scripts/importers/import_saliva_ph.py templates/saliva_ph_template.csv --dry-run
```
