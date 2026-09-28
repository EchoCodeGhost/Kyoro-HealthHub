# check_outbreak_source_health — Proaktive Erreichbarkeitspruefung aller Ausbruchsdatenquellen

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/utils/check_outbreak_source_health.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

On every run, checks ALL sources registered in import_outbreak_data.py (_FETCHERS) for actual reachability -- including the ones currently commented out as "DEAD" (who_searo, crm, healthmap, ...), so a silent provider-side fix (like who_paho, which was wrongly marked dead) surfaces automatically instead of being discovered by accident. Reports only STATE CHANGES (newly broken / newly recovered) against the last baseline, not the full status of every run -- keeps the output readable even with 20+ sources.

## Relevance

Without this script, dead/blocked sources (WHO SEARO/EURO/WPRO, HealthMap, CRM, ProMED) continue to be discovered only by accident -- exactly the pattern that led to discovering who_paho (wrongly marked dead) and the real WAHIS blocking cause (Cloudflare, not an auth token, see the _WAHISDB_API comment in import_outbreak_data.py for the alternative source chosen as a result), but by chance rather than systematically.

## Method

Calls every fetch function from _FETCHERS unmodified against its own in-memory SQLite database (utils/create_schema.py::SCHEMA) -- the same code, the same network calls as the real import, but without touching health.db. All sources are checked in PARALLEL via a ProcessPoolExecutor (up to 12 at once): sequentially, a run over ~20 sources -- several of which are only recognized as broken after their full network timeout (up to 30s for dead sources like CRM/WHO EURO) -- took several minutes (observed in practice); in parallel, only the single slowest source dominates total runtime. Every fetch function already catches its own network errors; many try several candidate URLs and log a generic "Fetch error ..." line for EACH failed candidate before a later one may still succeed (e.g. who_paho, cdc_travel, crm, all WHO regional offices). This script captures stdout during the call but does NOT classify on every error line (that caused a live false positive on who_paho, which actually works via its second candidate) -- instead it looks for the one textual marker every fetch function uses EXCLUSIVELY as a definitive conclusion once all candidates are truly exhausted: "reachable"/"erreichbar" (e.g. "no RSS reachable", "not reachable") -- see the _BROKEN_MARKERS comment for the grep-verified derivation. Plus xml-error/json-error/db-error, which can only occur AFTER a candidate was already successfully selected and therefore always mean real failure. RATE_LIMITED (e.g. GDELT 429/"Please limit requests") is treated as inconclusive and does not change the baseline; any unexpected exception (including its own SIGALRM timeout, see check_source()) also counts as BROKEN. ALWAYS persists (no --update gate like the topic-specific freshness checkers) -- reachability is an objective fact, not an interpretation that needs human confirmation.

## Data flow

- **Reads:** `Externe`, `URLs`, `aller`, `registrierten`, `Quellen;`, `outbreak_source_health_baseline.json`, `(lokaler`, `Zustand)`
- **Writes:** `outbreak_source_health_baseline.json (bei jedem Lauf, nicht nur mit --update)`

## Limitations

Detects only reachability/parsing breakage (exception or error-signaling text marker), not content correctness -- a source that returns 200 OK with empty/wrong content, without the fetch function noticing itself, is reported as OK. RATE_LIMITED detection relies on a fixed marker list ("429", "too many requests", "please limit requests", "rate limit"); a provider with different wording would be wrongly counted as BROKEN. RKI SurvStat is deliberately queried nationally only, not for all 16 federal states, via _HEALTH_CHECK_KWARGS (see comment there) -- a purely state-specific SOAP API outage would therefore not be caught, only a general one. fetch_rki_survstat() does not print a "reachable" marker on a network-level SOAP failure (only on a content-level SOAP fault, see _rki_soap_call()) -- a real network outage would therefore only be caught via an exception (e.g. the SIGALRM timeout), easily missed with a silent return of 0.

## Usage

```bash
python3 scripts/utils/check_outbreak_source_health.py
python3 scripts/utils/check_outbreak_source_health.py --quiet   # nur bei Aenderungen Ausgabe
```
