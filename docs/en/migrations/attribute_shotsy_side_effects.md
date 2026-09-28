# attribute_shotsy_side_effects.py — Backfills medication attribution for

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/migrations/attribute_shotsy_side_effects.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Retroactively applies import_shotsy.py:: attribute_side_effects_to_medication() to already-imported symptoms rows (source='shotsy') — the importer change only affects future runs.

## Relevance

Surfaces which medication was likely responsible for a logged side effect — used directly by compute_pem.py::alt_explanation_hint

## Method

Calls the same function the importer uses: symptoms.value_text is set to the name of the most recent preceding (or same-day) Shotsy injection, where still NULL. Best-effort, not exact causality — see the function's docstring.

## Data flow

- **Reads:** `health.db`, `(symptoms`, `medications)`
- **Writes:** `health.db (symptoms.value_text für source='shotsy')`

## Limitations

Only affects symptoms with source='shotsy'. compute_pem.py should be recomputed afterwards if alt_explanation_hint is used.

## Usage

```bash
python3 scripts/migrations/attribute_shotsy_side_effects.py --dry-run
python3 scripts/migrations/attribute_shotsy_side_effects.py
```
