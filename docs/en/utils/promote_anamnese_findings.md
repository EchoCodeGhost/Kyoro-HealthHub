# promote_anamnese_findings.py — Promotion logic for anamnese findings

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/utils/promote_anamnese_findings.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Implements promotion of anamnesis interview findings to existing structured JSON stores (family_history.json, travel_history.json, exposure_history.json, known_risk_exposures.json). Supports track-to-target mapping, chronic vs. one-off exposures, and human confirmation per finding/target.

## Relevance

Enables promotion of anamnesis findings, essential for clinical documentation

## Method

1) Track-to-target mapping per design.md decision 3, 2) Identify chronic exposures (keywords/duration), 3) Build target-specific entries with pseudonym resolution, 4) Call non-interactive append functions, 5) Obtain human confirmation, 6) Record the finding/target pair in anamnese_promotions (idempotency).

## Data flow

- **Reads:** `health.db`, `(anamnese_findings`, `anamnese_sessions`, `anamnese_promotions)`
- **Writes:**

  ```
  health.db (anamnese_promotions);
  ~/.config/kyoro/{family,travel,exposure,known_risk_exposures}.json
  ```

## Limitations

No automatic promotion — human confirmation per finding/target required. Idempotency tracking (task 2.3): a small mapping table (anamnese_promotions, columns finding_id/target_type/promoted_at, UNIQUE(finding_id, target_type)) rather than a column on anamnese_findings — one finding can be promoted to several targets.

## Usage

```bash
python3 scripts/utils/promote_anamnese_findings.py 1
python3 scripts/utils/promote_anamnese_findings.py 1 --auto
python3 scripts/query/anamnese_interview.py --promote 1
```
