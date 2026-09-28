# fhir_mapping.py — FHIR Mapping Utilities

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/exporters/fhir_mapping.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Loads LOINC/SNOMED mappings and manages unmapped metrics for FHIR export.

## Relevance

Provides FHIR interfaces, essential for standardized data exchange

## Method

- load_metric_code(): Loads LOINC mapping for a metric - track_unmapped(): Tracks unmapped metrics for report - write_unmapped_report(): Writes report file

## Data flow

- **Reads:** `-`, `scripts/exporters/fhir_metric_codes.json`
- **Writes:** `- fhir_export_unmapped_metrics.txt (Report-Datei)`

## Limitations

- No validation of input data - Report only written if unmapped metrics exist

## Usage

```bash
from scripts.exporters.fhir_mapping import load_metric_code, track_unmapped
```
