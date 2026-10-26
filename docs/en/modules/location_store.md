# location_store.py — Zentrale GPS/Ortsdaten-Registrierung und Policy-Enforcement

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/modules/location_store.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Central storage and querying of GPS coordinates and location data. Implements the location-privacy policy from location_privacy.json. All GPS coordinates are stored here only, never in health.db or medicine.db.

## Relevance

Core module for location privacy, essential for all importers

## Method

resolve_policy returns the applicable policy for an importer/file type. record stores a location in the registry (applying precision and zones). region_of returns the federal state/country for coordinates. location_token generates deterministic tokens for cells. for_prompt and filter_prompt_text enforce the outbound rules.

## Data flow

- **Reads:** `location.db`, `location_privacy.json`, `identity.db`, `(für`, `Salt)`
- **Writes:** `location.db (INSERT OR IGNORE)`

## Limitations

No storage without valid policy. Precision is ALWAYS applied before writing and is irreversible. No real data in tests.

## Usage

```bash
from modules.location_store import resolve_policy, record, file_sha256
from modules.location_store import location_token, for_prompt, filter_prompt_text
from modules.location_store import for_external_api, get_caller_name
```
