# Clinical Befunde-Timeline

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/analysis/internal_medicine/analyse_clinical_findings.py`

**Evidence tier:** heuristic (deliberate design from domain knowledge, no formal literature or validation basis)

## Purpose

Displays all structured clinical findings over time: categories, severity grades and status progression (normal / borderline / notable).

## Relevance

Enables an overview of structured clinical findings over time, essential for tracking severity and status progression without re-reviewing every individual finding

## Method

Descriptive aggregation by category and status level; sorting by severity hierarchy (critical > warning > borderline > normal). No statistical tests, no published reference values implemented.

## Scoring

```
Severity hierarchy: critical > warning > borderline > normal
Status progression: normal -> borderline -> warning -> critical (worsening)
```

## Data flow

- **Reads:** `clinical_findings`
- **Writes:** `analyses/internal_medicine/*.{md,png} (kein DB-Write)`

## Limitations

Heuristic method: Finding quality depends on manual data entry. Status labels (normal, borderline, warning, critical) are self-assigned, not standardised.

## References

- Singhal K, Azizi S, Tu T, et al. (2023). Large language models encode clinical knowledge. Nature, 620(7972), 172-180. doi:10.1038/s41586-023-06291-2
- Naemi A, Sahafi A (2026). Benchmarking large language models for MIMIC-IV clinical note summarization. Journal of Healthcare Informatics Research, 10(1), 95-115. doi:10.1007/s41666-025-00221-9

## Usage

```bash
python analyse_clinical_findings.py
python analyse_clinical_findings.py --help
python analyse_clinical_findings.py --from 2024-01-01 --to 2024-12-31
```
