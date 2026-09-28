# DRV-Reha-Kliniken → Kategorie-Zuordnung

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/importers/drv_kliniken_categories.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Resolves the clinic-offer categories that drv-reha.de/kliniken filters server-side (e.g. "Onkologische Krankheiten") per clinic, by replaying the page's own category filter query once for each of the roughly 18 categories.

## Relevance

Adds the official category mapping to the rehab clinic reference data, no direct relevance to personal health data

## Method

Loads the page once live (which yields both the <select id="category"> with the current category IDs/names and the hidden TYPO3 Extbase form fields __referrer/__trustedProperties), then replays the same POST request the "Filter by" form issues, once per category. Each filtered response is scanned for its <div id="ttaddress__record-N"> blocks to determine which numeric clinic IDs belong to that category. A short delay is kept between requests to avoid hammering the server.

## Data flow

- **Reads:** `https://www.drv-reha.de/kliniken`, `(online`, `1`, `GET`, `+`, `ca.`, `18`, `POST)`
- **Writes:** `imports/drv-kliniken/kategorien.json`

## Limitations

Reverse-engineers a TYPO3 Extbase form from its own hidden fields — if drv-reha.de changes the form's field structure, this script needs to be revisited. No parallelism, deliberately sequential with a delay between requests.

## Usage

```bash
python3 drv_kliniken_categories.py
python3 drv_kliniken_categories.py --help
```
