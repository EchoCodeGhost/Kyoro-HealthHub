# export_research_cohort.py — research cohort export with anonymization

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/exporters/export_research_cohort.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Exports anonymized research cohorts from multiple patient instances. Checks consents, applies date shifting and age banding, and filters small groups via k-anonymity. Without valid consent for ALL active patients, NO output is written (abort before any writing).

## Relevance

Enables export of health data, essential for data sharing and interoperability

## Method

1. Reads patient_number_map from master.db 2. Checks research_consent for each scope 3. Aborts if any active instance lacks consent 4. Activates each instance sequentially, runs profile export 5. Applies per-patient date shifting 6. Applies age banding 7. Checks k-anonymity on quasi-identifiers 8. Writes kept data + manifest, suppressed data separately

## Data flow

- **Reads:** `~/.config/kyoro-master/master.db`, `patient`, `instance`, `health.db`, `files`
- **Writes:** `KYORO_MASTER_DIR/research_exports/<date>/...`

## Limitations

Date shifting removes temporal alignment between patients. k-anonymity only checks explicitly provided quasi-identifiers. No automatic detection of identifiers.

## Usage

```bash
python3 scripts/exporters/export_research_cohort.py         --scope study-2026-hrv-cohort-a         --profile research         --quasi-identifiers age_band,timezone         --k 5 --age-band-width 5         --date-from 2020-01-01 --date-to 2026-12-31
python3 scripts/exporters/export_research_cohort.py --help
```
