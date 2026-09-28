# Blood glucose-Analyse (Glukometer)

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/analysis/metabolic/analyse_blood_glucose.py`

**Evidence tier:** validated (clinical validation study exists: sensitivity/specificity or endpoints prospectively established)

## Purpose

Analyses blood glucose self-measurements from glucometer: time-of-day profiles, value distribution, time-in-range fraction, fasting/post-prandial markers and trend.

## Relevance

Enables metabolic analysis, essential for metabolic health

## Method

Classification per IDF/ADA thresholds: fasting <100 mg/dL normal, 100–125 pre-diabetic, ≥126 diabetic; 2h post-prandial <140 / 140–199 / ≥200 mg/dL. Target range 70–140 mg/dL for time-in-range calculation.

## Data flow

- **Reads:** `blood_glucose`
- **Writes:** `analyses/metabolic/*.{md,png} (kein DB-Write)`

## Limitations

Glucometer spot measurements do not capture continuous glucose fluctuations. Measurement frequency and timing are not standardised (not OGTT conditions).

## References

- American Diabetes Association Standards 2024, Diabetes Care,
- American Diabetes Association Professional Practice Committee (2024). 5. Facilitating Positive Health Behaviors and Well-being to Improve Health Outcomes: Standards of Care in Diabetes—2024. Diabetes Care, 47(Supplement_1):S77-S110. doi:10.2337/dc24-S005

## Usage

```bash
python analyse_blood_glucose.py
python analyse_blood_glucose.py --help
python analyse_blood_glucose.py --from 2024-01-01 --to 2024-12-31
```
