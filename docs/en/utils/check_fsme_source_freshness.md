# check_fsme_source_freshness — Erkennt Aktualisierungen der RKI-FSME-Risikogebietsquelle

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/utils/check_fsme_source_freshness.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Checks whether the RKI source behind the hardcoded FSME risk- district lists in import_outbreak_data.py (FSME_RISIKOKREISE_*) has changed since the last check, so the yearly-due update (RKI publishes around late February in the Epidemiologisches Bulletin, usually issue 9) does not simply get forgotten.

## Relevance

Without this check the yearly FSME risk-district update relies purely on memory -- exactly the maintenance problem noticed after the nationwide FSME expansion in September 2026 (the previous source URLs were already dead without anyone noticing).

## Method

Fetches the RKI FSME topic page over HTTP and regex-extracts the "Epid Bull <issue>/<year>" text the page uses right next to "Karte der FSME-Risikogebiete" to reference the currently valid Epidemiologisches Bulletin issue. A SHA-256 hash of the full page would NOT be robust enough here -- verified via repeated fetches: the same page returns a different hash on every request despite identical byte length (likely a tracking token or similar embedded in the HTML), while the issue reference stays stable. Compares this reference against the last-confirmed one in fsme_source_baseline.json. Unlike the tiger-mosquito checker, there is no fixed yearly PDF URL to watch directly -- once an issue change is detected, the Epid. Bulletin PDF with the actual risk-district table must be found manually (e.g. web search "RKI Epidemiologisches Bulletin FSME-Risikogebiete <year>").

## Data flow

- **Reads:** `Externe`, `URL`, `(RKI`, `FSME-Themenseite);`, `fsme_source_baseline.json`, `(lokaler`, `Zustand)`
- **Writes:** `fsme_source_baseline.json (nur mit --update)`

## Limitations

The RKI topic page is a general overview article, not a machine- readable data format -- a changed hash can also mean a purely cosmetic change (layout, banner) unrelated to risk areas. Does not replace an annual manual review, only prevents it from being forgotten. The previously hardcoded RKI Content-URLs in import_outbreak_data.py had already been dead (404) for an unknown time when this script was written -- the same site restructuring could break the topic-page URL used here again; a persistently failing fetch is therefore also a check signal, not just a changed hash.

## Usage

```bash
python3 scripts/utils/check_fsme_source_freshness.py
python3 scripts/utils/check_fsme_source_freshness.py --update
```
