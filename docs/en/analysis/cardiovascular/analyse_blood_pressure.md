# Blutdruck-Trendanalyse (Blutdruckmessgerät)

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/analysis/cardiovascular/analyse_blood_pressure.py`

**Evidence tier:** validated (clinical validation study exists: sensitivity/specificity or endpoints prospectively established)

## Purpose

Analyses long-term blood pressure data: time series, time-of-day profile, ESC classification, correlation with HRV and arrhythmia, and medication effect.

## Relevance

Enables cardiovascular analysis, essential for cardiac diagnostics

## Method

BP classification per ESC 2024 (McEvoy et al., Eur Heart J 2024) with 6 classes. ESC 2024 officially defines 4 classes (Normal <130/85, Elevated BP 130–139/85–89, Grade 1 140–159/90–99, Grade 2 ≥160/≥100). Two intentional deviations: (1) "Optimal" (<120/80) is retained as an additional class — as an aspirational target showing where BP ideally should be headed (pedagogically valuable). (2) "Grade 3" (≥180/≥110) is kept despite being merged into Grade 2 in ESC 2024 — to make it immediately visible when the situation is truly urgent and immediate medical action would be required. Terminology update: "High-normal" → "Elevated BP" per ESC 2024. PWV reference: ESC 2018 PWV >10 m/s.

## Data flow

- **Reads:** `blood_pressure`, `arrhythmie_episoden`, `daily_stress`, `measurements`
- **Writes:** `analyses/cardiovascular/*.{md,png} (kein DB-Write)`

## Limitations

Home BP measurements without standardised protocol (rest, repetition). No 24h-ABPM. n=1, consumer device, measurement timing not controlled.

## References

- McEvoy JW, McCarthy CP, Bruno RM, et al. (2024). 2024 ESC Guidelines for the management of elevated blood pressure and hypertension. European Heart Journal. doi:10.1093/eurheartj/ehae178
- Williams B, Mancia G, Spiering W et al. (2018). 2018 ESC/ESH Guidelines for the management of arterial hypertension. European Heart Journal, 39(33):3021-3104. doi:10.1093/eurheartj/ehy339

## Usage

```bash
python analyse_blood_pressure.py
python analyse_blood_pressure.py --help
python analyse_blood_pressure.py --from 2024-01-01 --to 2024-12-31
```
