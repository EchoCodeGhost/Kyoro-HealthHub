# deidentify_cohort.py — k-anonymity and date-shifting helper functions

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/utils/deidentify_cohort.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Provides deterministic date shifting per patient pseudonym, age banding, and k-anonymity checking for research cohort exports. Date shifting is deterministic (same person → same offset on every run) but not reversible from the output (one-way hash, analogous to pseudonymize_device_serial).

## Relevance

Provides utility functions for data processing, essential for system functionality

## Method

- date_shift_offset_days: Computes offset from SHA-256 hash of pseudonym - shift_date: Shifts date values by the offset - age_band: Converts birthdate to age band (e.g., "30-34") - check_k_anonymity: Checks group sizes on quasi-identifiers

## Data flow

- **Reads:** `(none`, `—`, `pure`, `functions)`
- **Writes:** `(none — pure functions)`

## Limitations

Date shifting is deterministic per patient pseudonym but not reversible from the output. k-anonymity only checks the explicitly provided columns — no automatic detection of identifying fields. Age banding uses full calendar years, not exact age in days.

## Usage

```bash
from utils.deidentify_cohort import date_shift_offset_days, shift_date, age_band, check_k_anonymity
```
