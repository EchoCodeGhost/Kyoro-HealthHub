# dasrehaportal.de → Kategorie-Listen-Download

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/importers/rehaportal_download.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Downloads the paginated clinic result lists from dasrehaportal.de for a configurable set of indication categories.

## Relevance

Fetches raw data for rehabilitation planning, no direct relevance to personal health data — the actually searched indications live only in the local config file

## Method

Category slugs (e.g. "rueckenschmerzen") come exclusively from a local, non-versioned config file (~/.config/kyoro/rehaportal_kategorien.json) — the script itself hardcodes zero indications, so neither the source code nor a commit reveals which conditions are actually being searched for. Adding a new category means adding a slug to the config file, no code change needed. Per category, https://www.dasrehaportal.de/reha/rehakliniken/<slug>?page=N is fetched page by page until a page contains no more "clinic-result-box" hits (does not rely on the pagination widget's structure, more robust against layout changes). A short delay is kept between requests.

## Data flow

- **Reads:** `https://www.dasrehaportal.de/reha/rehakliniken/<slug>`, `(online)`, `~/.config/kyoro/rehaportal_kategorien.json`, `(Kategorie-Liste)`
- **Writes:** `imports/rehaportal/kategorien/<slug>/page_<N>.html`

## Limitations

Reverse-engineers the server-rendered pagination of a commercial ratings platform from its own markup structure — if the layout changes, this script needs to be revisited. The site's robots.txt was checked before building this (no disallow for this path, no crawl-delay given); the hardcoded delay between requests is kept anyway to avoid hammering the server.

## Usage

```bash
python3 rehaportal_download.py
python3 rehaportal_download.py --help
```
