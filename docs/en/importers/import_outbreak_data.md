# import_outbreak_data.py — Ausbruchsdaten-Import: Alle 6 WHO-Regionen und weitere Quellen

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/importers/import_outbreak_data.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Imports outbreak data from multiple sources into health.db for epidemiological analysis

## Relevance

Enables import of health data, essential for comprehensive data analysis

## Method

Aggregates data from all 6 WHO regions (EMRO, AFRO, PAHO, SEARO, EURO, WPRO), ECDC, EFSA, GDELT, ProMED, RKI SurvStat, RKI GrippeWeb, RKI ARE consultation incidence, LGL Bayern, WAHIS/WOAH, WAHIS-Wild, CDC Travel, HealthMap, Eurosurveillance, ReliefWeb, CRM, FLI West Nile Virus and Avian Influenza (district-level, the only Playwright-based sources) and static endemic reference data. Data is written to tables with fields: source, typ, country, region, date, cases, deaths, severity, coordinates, notes. Supports RSS- and API-based sources. Includes mapping to syndrome slugs.

## Data flow

- **Reads:** `Verschiedene`, `Online-Quellen`, `(RSS`, `SOAP`, `API)`, `und`, `eingebettete`, `Endemie-Referenzdaten`
- **Writes:** `outbreak_reports, outbreak_sources, import_log`

## Limitations

Depends on source availability. No medical validation of outbreak data. Endemic reference data is static and must be manually updated. GENERAL data, not personal: WHO/ECDC/RKI surveillance data and the static endemic reference table (location/pathogen/season) are independent of the owner's travel/location history — checked, no connection to travel_history.json/location_stays anywhere in the code. The same global dataset is always fetched, regardless of where the person has been or is going. `person` in the write paths is therefore not a real data-ownership field the way it is in other importers, just a blanket "relevant for whom" tag on otherwise fully general data — deliberately NOT part of the --person convention fix applied to the other importers (see OpenSpec change add-importer-person-override-convention, task 3.3 item 5: edge case, low priority, documented here instead of fixed).

## Usage

```bash
python3 import_outbreak_data.py
python3 import_outbreak_data.py --list-sources
python3 import_outbreak_data.py --sources who rki cdc_travel crm endemic
python3 import_outbreak_data.py --sources promedmail --dry-run
python3 import_outbreak_data.py --full-history  # einmaliger Backfill GrippeWeb + ARE-Konsultationsinzidenz + RKI SurvStat
```
