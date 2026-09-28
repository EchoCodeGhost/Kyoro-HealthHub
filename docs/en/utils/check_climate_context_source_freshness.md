# check_climate_context_source_freshness — Erkennt Aktualisierungen der Vektor-/Klimaeignungs-Kartenquellen

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/utils/check_climate_context_source_freshness.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Checks whether the official map sources backing the "KLIMAWANDEL-BEZUG" (climate-change context) statements in the syndrome files (scripts/analysis/syndromes/*.json — tick cluster, mosquito-borne pathogens, Bavaria overview page) have changed, so a stale range-expansion claim (e.g. "Ixodes ricinus is spreading north") doesn't sit unnoticed once the underlying mapping has moved on.

## Relevance

Without this check, the climate-change context added in September 2026 (tick cluster, Usutu, avian influenza, alpha-gal) would gradually freeze at the knowledge level of when it was written, even though vector distribution maps in particular move fast (e.g. the ECDC tick maps: 50 new administrative units with confirmed tick presence in the June 2026 update alone).

## Method

For each known source (ECDC VectorNet tick/mosquito distribution maps, LGL Bavaria overview page on climate change and infectious disease) fetches the raw bytes over HTTP and computes a SHA-256 hash, mirroring check_tigermuecke_source_freshness.py. Compares it against the last-confirmed hash in climate_context_source_baseline.json. Unlike the tiger-mosquito or FSME checker there is NO fixed list of affected files to update here — instead, a detected change points at the "KLIMAWANDEL-BEZUG" marker string (case-insensitive "klimawandel" for the older files written before this convention, e.g. candida_auris.json/zika.json) that every affected syndrome file carries in its system_prompt: a hardcoded file list would go stale the moment a new syndrome file adds a climate statement; a grep over the marker does not.

## Data flow

- **Reads:** `Externe`, `URLs`, `(ECDC`, `VectorNet`, `LGL`, `Bayern);`, `climate_context_source_baseline.json`, `(lokaler`, `Zustand)`
- **Writes:** `climate_context_source_baseline.json (nur mit --update)`

## Limitations

Only covers the three sources with a concrete, stably reachable map/overview page (ECDC tick/mosquito maps, LGL overview page). Pure literature citations without a trackable live source (e.g. Gray et al. 2009, Medlock et al. 2013, Tersago et al. 2009 for the hantavirus mast-year correlation, Walker 2018 for legionellosis) are deliberately NOT monitored — there is no URL whose change would say anything about a published paper's continued validity. A changed hash only means "the page changed somehow", not necessarily that distribution data changed in substance (same caveat as the tiger-mosquito checker). Does not replace an occasional manual literature review of the pure citations, only prevents the map-based statements from going stale unnoticed.

## Usage

```bash
python3 scripts/utils/check_climate_context_source_freshness.py
python3 scripts/utils/check_climate_context_source_freshness.py --update
```
