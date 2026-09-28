# fhir_validate.py — Strukturelle FHIR-R4(B)-Validierung für den Export-Bundle

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/exporters/fhir_validate.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Structurally validates the built FHIR bundle (required fields, cardinalities, types) before it is written to disk, aborting with a clear error message if the structure does not conform to the FHIR schema.

## Relevance

Provides FHIR interfaces, essential for standardized data exchange

## Method

- validate_bundle(bundle: dict) -> None: raises ValueError on structural violations, RuntimeError if the validation library is missing. No return value on success.

## Data flow

- **Reads:** `nichts`, `von`, `der`, `Platte`, `/`, `nothing`, `from`, `disk`, `—`, `arbeitet`, `nur`, `mit`, `dem`, `übergebenen`, `dict`, `im`, `Speicher`
- **Writes:** `nichts / nothing`

## Limitations

- Validates only the base FHIR R4B resource shape (required fields, data types, cardinality) — NO terminology check (whether a LOINC code genuinely exists), NO US Core or other profiles. - "R4B" instead of pure "R4": see provenance note below — the installed version of the package used here ships no pure-R4 model package, only R4B (HL7's technical-correction release of R4; no structural break for Bundle/Observation/Condition/Patient/ MedicationStatement versus R4).

## Usage

```bash
from fhir_validate import validate_bundle
validate_bundle(bundle_dict)  # raises on failure, returns None on success
```
