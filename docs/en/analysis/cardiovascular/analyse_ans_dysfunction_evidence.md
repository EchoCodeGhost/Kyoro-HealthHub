# Autonome-Dysfunktion-Evidenz — Bericht über compute_ans_dysfunction_evidence.py

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/analysis/cardiovascular/analyse_ans_dysfunction_evidence.py`

**Evidence tier:** heuristic (deliberate design from domain knowledge, no formal literature or validation basis)

## Purpose

Report counterpart to compute/compute_ans_dysfunction_evidence.py: reads the `ans_dysfunction_evidence` table written there and prepares it -- yearly overview, trend, list of critical days with component breakdown, channel coverage check, and the comparison against Polar's own nocturnal ANS signal (context, s. that docstring). The compute script itself only prints a short console summary -- everything here was ad-hoc SQL during development, now a reusable script.

## Relevance

Makes the suspicion score computed in compute_ans_dysfunction_evidence.py readable instead of leaving it as a raw table -- including the context comparisons that would otherwise need to be re-queried ad-hoc every time.

## Method

Reads exclusively from `ans_dysfunction_evidence` (already computed by compute_ans_dysfunction_evidence.py -- this script computes nothing new) and `polar_nightly_hrv` for the context comparison. Yearly/monthly overview via SQL GROUP BY. Critical days: `level='critical'`, components parsed from the stored `components` JSON column and formatted readably. Polar comparison: Pearson r(score, ans_status) pooled AND per year (s. @limits -- the pooled value can mimic a correlation that is really a shared multi-year trend, s. compute script docstring for the values already found there). Channel coverage: the same check as in the compute script (`_print_coverage_check()`), added here as a report section so it's visible without console access too.

## Scoring

```
Berechnet nichts neu -- liest den fertigen Score aus
compute_ans_dysfunction_evidence.py::ans_dysfunction_evidence,
s. dortiges @scoring fuer die Formel (direct=max(...),
support=min(20,sum(...)), score=direct+support, max. 50).
```

## Data flow

- **Reads:** `ans_dysfunction_evidence`, `polar_nightly_hrv`
- **Writes:** `analyses/cardiovascular/ans_dysfunction_evidence_*.md (+ .png bei --plot)`

## Limitations

Purely descriptive -- no new statistics/criteria beyond the compute script, only presentation. The pooled Polar comparison (multiple years together) is susceptible to a spurious- correlation effect from a shared trend -- the per-year breakdown is therefore ALWAYS shown alongside it, never the pooled value alone. Assumes compute_ans_dysfunction_evidence.py has already run -- otherwise shows an empty table, does not recompute anything.

## References

- s. compute/compute_ans_dysfunction_evidence.py @refs (Sheldon 2015, ESC BP-dipping) -- cited there, not re-derived here.

## Usage

```bash
python3 analyse_ans_dysfunction_evidence.py
python3 analyse_ans_dysfunction_evidence.py --from 2023-01-01 --to 2023-12-31
python3 analyse_ans_dysfunction_evidence.py --plot
python3 analyse_ans_dysfunction_evidence.py --no-llm
```
