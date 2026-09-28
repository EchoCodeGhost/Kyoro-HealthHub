# Health Event Timeline Analysis — Systematic Biomarker Comparison

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/analysis/internal_medicine/analyse_health_timeline.py`

**Evidence tier:** heuristic (deliberate design from domain knowledge, no formal literature or validation basis)

## Purpose

Systematically compares biomarkers (HRV, RHR, SpO₂, activity) across N+1 configurable periods derived from clinical.events.

## Relevance

Enables comprehensive temporal analysis of health history, essential for identifying patterns, trends, and critical events in individual health trajectories

## Method

Period averages and trends from the EAV measurements schema; LLM commentary via SYSTEM_PROMPT; plots as PNG time series.

## Scoring

```
Period comparison: pre vs post-event trend analysis
Biomarker change: delta percentage from baseline
```

## Data flow

- **Reads:** `measurements`, `sessions`, `session_metrics`, `symptoms`
- **Writes:** `analyses/postinfectious/health_timeline_*.{md,png}`

## Limitations

Heuristic method: Unvalidated period comparison; sample size per period varies substantially; no confidence intervals; clinical causality not derivable.

## References

- Singhal K, Azizi S, Tu T et al. (2023). Large language models encode clinical knowledge. Nature, 620(7972):172-180. doi:10.1038/s41586-023-06291-2
- Topol EJ (2019). High-performance medicine: the convergence of human and artificial intelligence. Nature Medicine, 25(1):44-56. doi:10.1038/s41591-018-0300-7

## Usage

```bash
python analyse_health_timeline.py
python analyse_health_timeline.py --help
python analyse_health_timeline.py --from 2024-01-01 --to 2024-12-31
```
