# Changepoint-Detektion auf täglichen Marker-Zeitreihen.

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/analysis/neurology/analyse_changepoint.py`

**Evidence tier:** heuristic (deliberate design from domain knowledge, no formal literature or validation basis)

## Purpose

Detects sustained level shifts (step changes) in daily marker time series and dates them; compares breakpoints against configured clinical events.

## Relevance

Enables neurological analysis, essential for nervous system diagnostics

## Method

Binary segmentation with mean-shift cost (between-group SS) and distribution-free permutation test (500 permutations, p < 0.01); minimum effect size Cohen's d ≥ 0.5. Thresholds internally configured, not validated.

## Scoring

```
Changepoint detection: binary segmentation with between-group SS cost
Effect size threshold: Cohen's d >= 0.5 for sustained level shifts
Significance: p < 0.01 (permutation test with 500 permutations)
```

## Data flow

- **Reads:** `daily_stress`, `polar_nightly_hrv`, `ppi_hrv_advanced`, `measurements`
- **Writes:** `analyses/neurology/*.{md,png} (kein DB-Write)`

## Limitations

Heuristic method: Purely statistical; no causal interpretation. Consumer sensors with measurement artefacts. Permutation test power is limited for short segments. Hypothesis-generating only — no clinical conclusions.

## References

- Killick R, Eckley IA (2014). changepoint: An R Package for Changepoint Analysis. Journal of Statistical Software, 58(3). doi:10.18637/jss.v058.i03
- Truong C, Oudre L, Vayatis N (2020). Selective review of offline change point detection methods. Signal Processing, 167:107299. doi:10.1016/j.sigpro.2019.107299

## Usage

```bash
python analyse_changepoint.py
python analyse_changepoint.py --help
python analyse_changepoint.py --from 2024-01-01 --to 2024-12-31
```
