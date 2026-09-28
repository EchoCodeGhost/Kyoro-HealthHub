# Tageslicht-Exposition & Circadiane Gesundheit

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/analysis/environment/analyse_daylight.py`

**Evidence tier:** heuristic (deliberate design from domain knowledge, no formal literature or validation basis)

## Purpose

Analyses daily daylight exposure (Apple Watch) and its association with sleep quality, HRV, energy and mood via Spearman correlation.

## Relevance

Analyzes the impact of daylight exposure on sleep quality, mood, and circadian rhythm, essential for identifying sleep disorders and optimizing light therapy

## Method

Sums time_in_daylight entries from apple_records; Spearman correlation without multiple-testing correction. Minimum 30 min/day guideline (circadian rhythm) without RCT backing.

## Scoring

```
Daylight exposure: <30 min/day low | 30-60 min/day moderate | >60 min/day high (circadian rhythm guideline)
Correlation strength: |r| <0.2 weak | 0.2-0.4 moderate | 0.4-0.7 strong | >0.7 very strong
```

## Data flow

- **Reads:** `apple_records`, `(time_in_daylight)`, `daily_stress`, `polar_sleep_score`, `symptoms`, `weather_station`
- **Writes:** `analyses/environment/*.{md,png} (kein DB-Write)`

## Limitations

Heuristic method: Apple Watch measures daylight indirectly (UV sensor or motion data); no lux calibration. Confounding by seasonality not controlled. Correlations are exploratory. n=1.

## References

- Lewy AJ, Wehr TA, Goodwin FK, Newsome DA, Markey SP (1980). Light suppresses melatonin secretion in humans. Science, 210(4475):1267-1269. doi:10.1126/science.7434030
- Wirz-Justice A, Benedetti F, Terman M (2013). Chronotherapeutics for Affective Disorders: A Clinician's Manual for Light and Wake Therapy (2nd ed.). Karger. doi:10.1159/isbn.978-3-318-02091-5

## Usage

```bash
python analyse_daylight.py
python analyse_daylight.py --help
python analyse_daylight.py --from 2024-01-01 --to 2024-12-31
```
