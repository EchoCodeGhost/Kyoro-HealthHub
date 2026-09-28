# Fluessigkeitsaufnahme → health.db (fluid_intake)

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/importers/import_fluid_intake.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Tracks daily fluid and salt intake

## Relevance

Enables import of health data, essential for comprehensive data analysis

## Method

Tracks daily fluid and salt intake. Goals configurable via clinical.fluid_target_ml / clinical.sodium_target_mg. CSV format: ts,beverage,volume_ml,caffeine_mg,alcohol_g,sodium_mg,notes Beverages: water, tea, coffee, juice, broth, sports_drink, other Caffeine lookup for standard values.

## Data flow

- **Reads:** `CSV-Dateien`, `aus`, `~/Kyoro-HealthHub/imports/fluid_intake/`
- **Writes:** `fluid_intake`

## Limitations

Dependent on manual input.

## Usage

```bash
python3 import_fluid_intake.py           # alle CSVs
python3 import_fluid_intake.py --update  # nur neue Daten
python3 import_fluid_intake.py --manual  # interaktive Eingabe
python3 import_fluid_intake.py --template
python3 import_fluid_intake.py --summary # Tagesuebersicht
```
