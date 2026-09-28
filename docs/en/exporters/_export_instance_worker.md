# _export_instance_worker.py — single-instance export worker for export_research_cohort.py

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/exporters/_export_instance_worker.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Started by export_research_cohort.py as a separate subprocess per person instance (with KYORO_ACTIVE_PATIENT_DIR in the process environment). Runs the profile queries against exactly one instance's health.db and prints the result as JSON to stdout.

## Relevance

Enables export of health data, essential for data sharing and interoperability

## Method

A separate process per instance is required because scripts/health_config.py computes KYORO_CONFIG_DIR as a module constant at first import (sys.modules caching) — repeatedly changing KYORO_ACTIVE_PATIENT_DIR within the same process has no effect on an already-imported health_config module (see docs/SHARED_ACCESS_DEPLOYMENT.md, "Understanding concurrency": the env var applies per process, not repeatedly flippable within one run).

## Data flow

- **Reads:** `$KYORO_ACTIVE_PATIENT_DIR/data/health.db`, `(via`, `health_config.Config)`
- **Writes:** `stdout (JSON only)`

## Limitations

Expects KYORO_ACTIVE_PATIENT_DIR already set in the process environment (by the calling export_research_cohort.py). Not intended for direct interactive use.

## Usage

```bash
KYORO_ACTIVE_PATIENT_DIR=/path/to/instance python3 _export_instance_worker.py         --profile research --person all --date-from 2020-01-01 --date-to 2026-12-31
python3 _export_instance_worker.py --help
```
