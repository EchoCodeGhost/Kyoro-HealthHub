# import_amelag.py — RKI/UBA Abwassersurveillance AMELAG → health.db (wastewater_amelag)

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/importers/import_amelag.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Imports the AMELAG wastewater surveillance (SARS-CoV-2, Influenza A/B, RSV) from RKI and the Federal Environment Agency — nationwide aggregated curve plus individual sites for a selectable federal state (default: derived from the configured home coordinate, see modules/geo_bundesland.py — no hardcoded federal state, works for any installation).

## Relevance

Enables import of health data, essential for comprehensive data analysis Enables import of health data, essential for comprehensive data analysis

## Method

Downloads two TSV files from GitHub: the nationwide aggregated curve (small, ~1000 rows) and the per-site file (nationwide ~460,000 rows, filtered locally to one federal state — no server-side filtering exists). Stores both in wastewater_amelag with INSERT OR IGNORE. Rolling time window like GrippeWeb/ARE consultation incidence (import_outbreak_data.py) — full history since data collection began (Feb 2022) via --full-history.

## Data flow

- **Reads:** `GitHub`, `(robert-koch-institut/Abwassersurveillance_AMELAG`, `CC-BY`, `4.0)`
- **Writes:** `health.db:wastewater_amelag, health.db:import_log`

## Limitations

Per-site file is ~50 MB (nationwide), downloaded in full and filtered locally — no server-side federal-state filtering available. No medical interpretation of viral-load values.

## References

- RKI/UBA AMELAG: https://github.com/robert-koch-institut/Abwassersurveillance_AMELAG

## Usage

```bash
python3 import_amelag.py
python3 import_amelag.py --bundesland BY
python3 import_amelag.py --full-history
```
