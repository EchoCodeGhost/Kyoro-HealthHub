# RENPHO Smart-Maßband → health.db (body_composition)

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/importers/import_renpho_tape.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Imports CSV exports from the RENPHO app (smart tape measure) into health.db. Stores all body circumferences (neck, shoulder, arm, chest, waist, abdomen, hip, thigh, calf, custom) and the waist-to- hip ratio in body_composition.

## Relevance

Enables import of health data, essential for comprehensive data analysis

## Method

Reads CSV files from imports/_inbox/ (RENPHO*.csv) or an explicit path. Each row contains a date stamp (German format) and Key(unit):value pairs. Missing values ('--') are stored as NULL. New circumference columns are added to body_composition automatically if not yet present.

## Data flow

- **Reads:** `imports/_inbox/RENPHO*.csv`
- **Writes:**

  ```
  health.db: body_composition (neck_cm, shoulder_cm, upper_arm_left_cm,
  upper_arm_right_cm, chest_cm, abdomen_cm, thigh_left_cm,
  thigh_right_cm, calf_left_cm, calf_right_cm, custom_1..6,
  waist_to_hip_ratio, waist_cm, hip_cm)
  ```

## Limitations

RENPHO app exports "Custom Part 1" with unit "inch" (app bug); the value is stored as-is. No plausibility validation.

## Usage

```bash
python3 import_renpho_tape.py
python3 import_renpho_tape.py --inbox
python3 import_renpho_tape.py --file "RENPHO Health-Max.csv"
python3 import_renpho_tape.py --update
```
