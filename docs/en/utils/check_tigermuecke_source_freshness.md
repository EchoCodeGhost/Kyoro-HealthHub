# check_tigermuecke_source_freshness — Erkennt Aktualisierungen der Tigermücken-Kartenquellen

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/utils/check_tigermuecke_source_freshness.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Checks whether the external map sources behind the hardcoded tiger mosquito district data in import_outbreak_data.py (_TIGERMUECKE_*) have changed since the last check, so the yearly-due update does not simply get forgotten.

## Relevance

Without this check the yearly tiger-mosquito district update relies purely on memory — exactly the maintenance problem noticed after the district-level mapping work in September 2026.

## Method

For each known source (FLI commission page, LGL monitoring index page, LGL annual-report PDF) fetches the raw bytes over HTTP and computes a SHA-256 hash. Compares it against the last-confirmed hash in tigermuecke_source_baseline.json. A source counts as "changed" if the hash differs, and "gone" if the fetch fails (e.g. because a year-bound URL like .../jb24_....pdf moved to .../jb25_....pdf — the new URL then needs to be found manually, see the comments next to the _TIGERMUECKE_*-lists in import_outbreak_data.py). Deliberately does NOT try to OCR the "Stand: DD.MM.YYYY" date baked into the map images (the label is plain pixel graphics, see comments near _TIGERMUECKE_BAYERN_LGL_NOTE) — hashing the raw file is more robust and needs no image recognition.

## Data flow

- **Reads:** `Externe`, `URLs`, `(FLI`, `LGL);`, `tigermuecke_source_baseline.json`, `(lokaler`, `Zustand)`
- **Writes:** `tigermuecke_source_baseline.json (nur mit --update)`

## Limitations

A changed hash only means "the page/file changed somehow" (even a purely cosmetic HTML change with no map content triggers it) — not proof that district data actually changed. Conversely an unchanged hash does not guarantee the source is still current (caching effects on fetch are not excluded). Does not replace an annual manual visual review, only prevents it from being forgotten.

## Usage

```bash
python3 scripts/utils/check_tigermuecke_source_freshness.py
python3 scripts/utils/check_tigermuecke_source_freshness.py --update
```
