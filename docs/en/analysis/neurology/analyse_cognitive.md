# Kognitive Funktion — Verlaufsanalyse

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/analysis/neurology/analyse_cognitive.py`

**Evidence tier:** experimental (exploratory, no stable conceptual foundation, hypothesis-generating)

## Purpose

Evaluates cognitive short tests (reaction time, SDMT, digit span, N-back): trend over time, time-of-day effects and correlation with HRV and fatigue symptoms.

## Relevance

Enables neurological analysis, essential for nervous system diagnostics

## Method

Pearson correlation of cognitive scores × HRV/fatigue; pre/post group comparison via configured event cutoff. No holdout, no normalisation to population reference. Test battery not formally validated for this application.

## Data flow

- **Reads:** `cognitive_tests`, `measurements`, `(HRV`, `via`, `modules/metric_loader)`, `symptoms`
- **Writes:** `analyses/neurology/*.{md,png} (kein DB-Write)`

## Limitations

Experimental method: Self-administered tests without standardised conditions. No population norms. Practice effects and daily condition not controlled. Exploratory, no diagnostic conclusions.

## References

- Davis HE, McCorkell L, Vogel JM, Topol EJ (2023). Long COVID: major findings, mechanisms and recommendations. Nature Reviews Microbiology, 21(3):133-146. doi:10.1038/s41579-022-00846-2
- Reitan 1955 (Trail Making Test — referenced in docstring)

## Usage

```bash
python analyse_cognitive.py
python analyse_cognitive.py --help
python analyse_cognitive.py --from 2024-01-01 --to 2024-12-31
```
