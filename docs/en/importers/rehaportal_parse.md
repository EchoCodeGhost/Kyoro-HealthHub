# dasrehaportal.de → JSON-Parser

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/importers/rehaportal_parse.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Converts the category result lists fetched by rehaportal_download.py into a deduplicated, structured clinic list.

## Relevance

Structures rehab clinic reference data for rehabilitation planning, no direct relevance to personal health data

## Method

Parses every ".clinic-result-box" on every saved page (ID/slug from the link, name/zip/city from the heading, rehab form from the category icons) and deduplicates across the numeric clinic ID — a clinic appearing under multiple categories gets a merged "kategorien" list instead of duplicate entries. If a detail page downloaded by rehaportal_details_download.py is present (imports/rehaportal/details/<id>.html), two sections are parsed from it: "Kostenträger & Rehaformen" (cost-carrier name → list of covered rehab forms) and the room tab "#patient-rooms" (room type, e.g. "Einzelzimmer mit Dusche/WC" → detail text including count); without a detail page both fields stay an empty dict instead of erroring. Full address/service description only live on the detail pages and are not extracted here.

## Data flow

- **Reads:** `imports/rehaportal/kategorien/<slug>/page_*.html`, `imports/rehaportal/details/<id>.html`, `(optional)`
- **Writes:** `imports/rehaportal/kliniken.json`

## Limitations

No database writes — pure file conversion, so log_import() does not apply. Contains no address data; cost-carrier info only if the matching detail page has already been downloaded.

## Usage

```bash
python3 rehaportal_parse.py
python3 rehaportal_parse.py --help
```
