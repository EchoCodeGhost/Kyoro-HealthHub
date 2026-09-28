# DRV-Reha-Kliniken → JSON-Parser

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/importers/drv_kliniken_parse.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Converts the HTML page fetched by drv_kliniken_download.py (the German pension insurance's clinic location overview) into structured JSON.

## Relevance

Structures rehab clinic reference data for rehabilitation planning, no direct relevance to personal health data

## Method

Parses the "sedcard" detail block per clinic (<div id="ttaddress__record-N">), which appears twice on the page (responsive layout variants) — duplicates are removed via the numeric ID. Extracts name, address, coordinates, contact info (phone/fax/e-mail/website), description text, and the two tab lists "Klinikangebot" (treated indications) and "Das bieten wir" (amenities/services). If kategorien.json is present (from drv_kliniken_categories.py), the official category assignment (e.g. "Onkologische Krankheiten") is attached per clinic as well; otherwise the field stays empty.

## Data flow

- **Reads:** `imports/drv-kliniken/kliniken`, `(Roh-HTML`, `von`, `drv_kliniken_download.py)`, `imports/drv-kliniken/kategorien.json`, `(optional`, `von`, `drv_kliniken_categories.py)`
- **Writes:** `imports/drv-kliniken/kliniken.json`

## Limitations

No database writes — pure file conversion, so log_import() does not apply. The "Klinikangebot" list is free text authored by each clinic, not a controlled vocabulary (e.g. ICD-10) — suitable for AI-assisted matching, not exact code lookups.

## Usage

```bash
python3 drv_kliniken_parse.py
python3 drv_kliniken_parse.py --help
```
