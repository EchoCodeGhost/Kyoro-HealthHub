# backfill_travel_environment_person.py — pollen/biometeo/air_quality: person='unknown' → real pseudonym

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/migrations/backfill_travel_environment_person.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Backfills historical rows in pollen, biometeo and air_quality that still carry the schema default person='unknown' to the real person pseudonym ID — on the user's explicit request, after weighing it against the general exclusion rule for 'unknown' in pseudonymize_device_person_identifiers.py (see @limits).

## Relevance

Fixes a historical data gap that made person-filtered queries (the project-wide standard pattern) blind to a large share of environmental data rows

## Method

import_airquality.py (the sole writer of these three tables) already defaults person to OWN_PERSON_ID correctly — the 'unknown' rows are historical (bug fixed long ago, everything since has been correct), not an active code bug anymore. No PK conflict possible: these three tables' primary key is (date, lat, lon) without person, so a plain UPDATE suffices (unlike e.g. rename_kiste_export_source.py, where person is part of the PK and collisions must be checked for).

## Data flow

- **Reads:** `pollen`, `biometeo`, `air_quality`, `(person`, `column)`
- **Writes:** `pollen, biometeo, air_quality (UPDATE person='unknown' → real pseudonym)`

## Limitations

Deliberately deviates from the general rule in pseudonymize_device_person_identifiers.py, which does NOT pseudonymize 'unknown' (rationale there: 'unknown' means "no person recorded", not "a specific person" — converting it would misrepresent a missing value as a real identity). For THESE three tables the situation differs: this project has so far only ever held one person's data, and the affected rows demonstrably originate from stays/fetches for the user herself (not a shared or genuinely unknown source) — hence backfilled here on her explicit request. This exception applies ONLY to these three tables, not to 'unknown' project-wide. Meant to run once; safe to re-run (no-op once no 'unknown' rows remain).

## Usage

```bash
python3 scripts/migrations/backfill_travel_environment_person.py
python3 migrations/backfill_travel_environment_person.py  # from inside scripts/
```
