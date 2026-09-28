# dasrehaportal.de → Klinikdetailseiten-Download

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/importers/rehaportal_details_download.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Downloads the individual detail page for every unique facility found by rehaportal_parse.py — the only page that contains the cost-carrier section (which insurers/payers cover which rehab form at that facility).

## Relevance

Fetches raw data for rehabilitation planning, no direct relevance to personal health data

## Method

Reads imports/rehaportal/kliniken.json (output of rehaportal_parse.py) and fetches each facility's "url" field. Saves the raw page to imports/rehaportal/details/<id>.html — skips already-downloaded IDs so adding new categories later doesn't re-fetch all 237+ detail pages. A short delay is kept between requests.

## Data flow

- **Reads:** `imports/rehaportal/kliniken.json`, `https://www.dasrehaportal.de/reha/<id>/<slug>`, `(online`, `einmal`, `je`, `eindeutiger`, `Einrichtung)`
- **Writes:** `imports/rehaportal/details/<id>.html`

## Limitations

One request per unique facility — with several hundred facilities, a noticeably larger scrape than the category lists themselves. robots.txt was checked before building the overall pipeline (no disallow, no crawl-delay); the delay between requests is kept anyway.

## Usage

```bash
python3 rehaportal_details_download.py
python3 rehaportal_details_download.py --help
```
