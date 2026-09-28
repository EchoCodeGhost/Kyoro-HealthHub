# analyse_daily_load.py — HR-Zonenverteilung und Tagespensum-Analyse.

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/analysis/activity/analyse_daily_load.py`

**Evidence tier:** heuristic (deliberate design from domain knowledge, no formal literature or validation basis)

## Purpose

Analyses HR zone distribution and daily load score: overview, load levels, correlation load × next-day HRV/PEM, and red-zone frequency.

## Relevance

Enables activity data analysis, essential for movement and fitness analysis

## Method

Reads from compute_hr_zones-generated daily_hr_zones; empirically calibrated HR zones (Zone 0-4) and weighted daily load score from compute outputs. Data sources: daily_hr_zones, measurements (hrv_rmssd), pem_evidence_scores, symptoms. No published reference values for zone boundaries.

## Scoring

```
direct = Zone_4_Anteil * 50 + Rote-Zone-Tage * 30 + PEM_Korrelation * 20
```

## Data flow

- **Reads:** `daily_hr_zones`, `measurements`, `(hrv_rmssd)`, `pem_evidence_scores`, `symptoms`
- **Writes:** `analyses/activity/*.{md,png} (kein DB-Write)`

## Limitations

Heuristic method: Zone boundaries are empirically calibrated, not formally validated. No comparison with lactate tests or spiroergometric data. n=1, consumer sensors.

## References

- ACSM 2022, Guidelines for Exercise Testing and Prescription, 11th ed.
- Borg G 1998, Borg's Perceived Exertion and Pain Scales; ISBN:0-88011-623-4
- Chen MJ, Fan X, Moe ST (2002). Criterion-related validity of the Borg ratings of perceived exertion scale in healthy individuals: a meta-analysis. Journal of Sports Sciences, 20(11), 873-899. doi:10.1080/026404102320761787

## Usage

```bash
python3 scripts/analysis/analyse_daily_load.py [--from YYYY-MM-DD] [--to YYYY-MM-DD]
python3 scripts/analysis/analyse_daily_load.py --plot
python3 scripts/analysis/analyse_daily_load.py --no-llm
```
