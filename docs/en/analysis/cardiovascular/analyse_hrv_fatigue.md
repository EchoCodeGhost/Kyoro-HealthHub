# HRV × Erschöpfung — Lag-Correlationsanalyse

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/analysis/cardiovascular/analyse_hrv_fatigue.py`

**Evidence tier:** heuristic (deliberate design from domain knowledge, no formal literature or validation basis)

## Purpose

Examines the time-lagged relationship between nocturnal HRV (RMSSD) and subjective fatigue using lag correlation (±7 days).

## Relevance

Enables cardiovascular analysis, essential for cardiac diagnostics

## Method

Pearson correlation (pure Python) for HRV(t) × fatigue(t+lag) over all overlapping days; lag scan from −7 to +7.

## Scoring

```
Fatigue scale: 0-10 (subjective, from symptom diary)
Correlation strength: |r| <0.2 weak | 0.2-0.4 moderate | 0.4-0.7 strong | >0.7 very strong
Lag direction: negative (HRV leads fatigue) | positive (fatigue leads HRV)
```

## Data flow

- **Reads:** `measurements`, `symptoms`
- **Writes:** `analyses/cardiovascular/hrv_fatigue_*.{md,png}`

## Limitations

Heuristic method: Exploratory analysis without significance threshold; symptom diary data currently very sparse (no consistent logging); causal direction not determinable; no adjustment for confounding.

## References

- Shaffer F, Ginsberg JP (2017). An overview of heart rate variability metrics and norms. Frontiers in Public Health, 5:258. doi:10.3389/fpubh.2017.00258
- Davenport TE, Stevens SR, VanNess MJ, Snell CR, Little T (2010). Conceptual model for physical therapist management of chronic fatigue syndrome/myalgic encephalomyelitis. Physical Therapy, 90(4):602-614. doi:10.2522/ptj.20090047

## Usage

```bash
python analyse_hrv_fatigue.py
python analyse_hrv_fatigue.py --help
python analyse_hrv_fatigue.py --from 2024-01-01 --to 2024-12-31
```
