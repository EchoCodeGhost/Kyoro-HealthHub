# analyse_urine.py — Urin-Monitoring Trendanalyse

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/analysis/manual/analyse_urine.py`

**Evidence tier:** heuristic (deliberate design from domain knowledge, no formal literature or validation basis)

## Purpose

Analyzes urine dipstick test data from home monitoring

## Relevance

Enables health data analysis, essential for medical diagnostics

## Method

Reads urine dipstick test data from medicine.db (lab_manual, Urine-* parameters) and creates: - Trend table of all 12 parameters over time - Protein/Creatinine Ratio (PCR) if numerically available - Flagging of conspicuous individual values and trends - Optional: LLM comment

## Scoring

```
Anomalie-Score basierend auf Abweichung von Normalbereichen und Trendrichtung
```

## Data flow

- **Reads:** `medicine.db`, `(lab_manual)`
- **Writes:** `Analyseergebnisse als Markdown/CSV`

## Limitations

Heuristic method: Heuristic analysis. Dependent on data quality.

## References

- Simerville JA, Maxted WC, Pahira JJ (2005). Urinalysis: A Comprehensive Review. American Family Physician, 71(6):1153-1162. (kein DOI verfügbar)
- Fogazzi GB, Verdesca S, Garigali G (2008). Urinalysis: Core Curriculum 2008. American Journal of Kidney Diseases, 51(6):1052-1067. doi:10.1053/j.ajkd.2007.11.039

## Usage

```bash
python3 scripts/analysis/analyse_urine.py
python3 scripts/analysis/analyse_urine.py --plot
python3 scripts/analysis/analyse_urine.py --from 2026-01-01
python3 scripts/analysis/analyse_urine.py --no-llm
```
