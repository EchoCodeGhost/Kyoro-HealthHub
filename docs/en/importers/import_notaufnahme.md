# import_notaufnahme.py — RKI-Notaufnahmesurveillance → health.db (ed_syndromic_surveillance)

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/importers/import_notaufnahme.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Imports the RKI emergency-department syndromic surveillance (AKTIN infrastructure/emergency department register) — daily shares of ARI, ILI, COVID, SARI, GI, and HEAT presentations among all emergency department visits in Germany, including expected value and prediction interval.

## Relevance

Enables import of health data, essential for comprehensive data analysis Enables import of health data, essential for comprehensive data analysis

## Method

Downloads the nationwide time-series TSV from GitHub (~330,000 rows since 2019, all ED types/age groups). Filters by default to ed_type='all' and age_group='00+' (total population, all hospital types) — otherwise the age-cohort/ED-type breakdown would needlessly bloat the table. Rolling time window like GrippeWeb/ARE consultation incidence/AMELAG (import_outbreak_data.py, import_amelag.py) — full history since 2019 via --full-history.

## Data flow

- **Reads:** `GitHub`, `(robert-koch-institut/Daten_der_Notaufnahmesurveillance`, `CC-BY`, `4.0)`
- **Writes:** `health.db:ed_syndromic_surveillance, health.db:import_log`

## Limitations

Nationwide aggregate only, no federal-state/district level available. No medical interpretation of the values.

## References

- RKI Notaufnahmesurveillance: https://github.com/robert-koch-institut/Daten_der_Notaufnahmesurveillance

## Usage

```bash
python3 import_notaufnahme.py
python3 import_notaufnahme.py --ed-type all --age-group 00+
python3 import_notaufnahme.py --full-history
```
