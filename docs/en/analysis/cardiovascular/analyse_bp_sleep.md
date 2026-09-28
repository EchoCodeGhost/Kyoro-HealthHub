# Blutdruck × Schlaf — Dipping-Analyse und Schlafqualitäts-Korrelation

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/analysis/cardiovascular/analyse_bp_sleep.py`

**Evidence tier:** validated (clinical validation study exists: sensitivity/specificity or endpoints prospectively established)

## Purpose

Classifies blood pressure measurements as sleep or wake values and computes the nocturnal dipping pattern as well as associations between sleep quality and next-day blood pressure.

## Relevance

Enables cardiovascular analysis, essential for cardiac diagnostics

## Method

Dipping classification per ESC definition: dipper ≥ 10 %, non-dipper 0–10 %, reverse-dipper < 0 %, extreme dipper > 20 % (systolic drop). Sleep sessions from multiple sources (Oura, SleepCycle, Garmin, Polar).

## Data flow

- **Reads:** `blood_pressure`, `sessions`, `session_metrics`
- **Writes:** `analyses/cardiovascular/*.{md,png} (kein DB-Write)`

## Limitations

Home BP measurements without standardised protocol. Timestamp assignment to sleep sessions is approximate. No 24h-ABPM. n=1, consumer device.

## References

- McEvoy JW, McCarthy CP, Bruno RM, et al. (2024). 2024 ESC Guidelines for the management of elevated blood pressure and hypertension. European Heart Journal. doi:10.1093/eurheartj/ehae178  (ESC 2024 — Dipping-Def.)
- Hermida RC, Crespo JJ, Domínguez-Sardiña M et al. (2020). Bedtime hypertension treatment improves cardiovascular risk reduction: the Hygia Chronotherapy Trial. European Heart Journal, 41(48):4565-4576. doi:10.1093/eurheartj/ehz754

## Usage

```bash
python analyse_bp_sleep.py
python analyse_bp_sleep.py --help
python analyse_bp_sleep.py --from 2024-01-01 --to 2024-12-31
```
