# Histamin-Trigger-Tagebuch → health.db (food_triggers + histamine_food_db)

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/importers/import_histamine_diary.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Imports histamine trigger diary data

## Relevance

Enables import of health data, essential for comprehensive data analysis

## Method

Documents food and occurring symptoms. On first run, the histamine reference database is populated. CSV format: ts,food_name,portion_g,reaction_h,symptoms,severity,meal_type,notes Histamine categories: high, medium, low, liberator, blocker.

## Data flow

- **Reads:** `CSV-Dateien`, `aus`, `~/Kyoro-HealthHub/imports/histamine_diary/`
- **Writes:** `food_triggers, histamine_food_db`

## Limitations

Heuristic categorization. Dependent on data quality.

## Usage

```bash
python3 import_histamine_diary.py           # alle CSVs
python3 import_histamine_diary.py --manual  # interaktive Eingabe
python3 import_histamine_diary.py --template
python3 import_histamine_diary.py --show-db # Datenbank ausgeben
```
