# Expositionsanalyse: Reiseverlauf/Wohnsitz × Ausbruchsdaten

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/analysis/infectious/analyse_outbreak_exposure.py`

**Evidence tier:** heuristic (deliberate design from domain knowledge, no formal literature or validation basis)

## Purpose

Correlates travel history and home residences (travel_history.json + location_stays, is_home=0/1) with outbreak and endemic patterns data from DB, generating an exposure-based differential assessment list.

## Relevance

Supports infection-related data analysis and decision-making through systematic processing of wearable and symptom data

## Method

Geographic ISO-country and coordinate-radius matching (Haversine, GEO_RADIUS_KM_ENDEMIC=200 km, GEO_RADIUS_KM_EXACT=100 km); temporal overlap with date-fuzz buffer (±0/45/180 days depending on trip date precision) for trips; home residences use a separate score formula relative to outbreak duration instead of (often multi-year) residence duration; heuristic exposure score.

## Scoring

```
Expositions-Score (heuristisch, projektintern):
Reisen:    score = overlap_days / trip_duration  (0.0–1.0)
Wohnsitze: score = overlap_days / outbreak_duration  (0.0–1.0, s. _temporal_overlap_residence())
Geografische Radien (Haversine): GEO_RADIUS_KM_ENDEMIC=200 km (Endemie-Referenz, Länder-Zentroid),
                                 GEO_RADIUS_KM_EXACT=100 km (konkreter Ausbruch)
Datums-Unschärfe (nur Reisen): YYYY-MM-DD=±0 Tage, YYYY-MM=±45 Tage, YYYY=±180 Tage
Basis: projektintern, keine epidemiologische Validierung.
```

## Data flow

- **Reads:** `outbreak_events`, `endemic_ref`, `location_stays`
- **Writes:** `analyses/infectious/outbreak_exposure_*.{md,txt}`

## Limitations

Heuristic method: Coordinate matching uses Haversine formula; outbreak data must be manually maintained in outbreak_events; no substitute for serological confirmation; results to be interpreted as hypothesis generation only; incubation buffer (60 days) covers most diseases but is not calibrated per pathogen. Home-residence score is a separate, unvalidated heuristic (share of outbreak duration falling within the residence period), not directly comparable to the trip score.

## References

- Kulldorff M (1997). A spatial scan statistic. Communications in Statistics - Theory and Methods, 26(6), 1481-1496. doi:10.1080/03610929708831995
- Brownstein JS, Freifeld CC, Reis BY, Mandl KD (2008). Surveillance Sans Frontières: Internet-based emerging infectious disease intelligence and the HealthMap project. PLoS Medicine, 5(7), e151. doi:10.1371/journal.pmed.0050151

## Usage

```bash
python analyse_outbreak_exposure.py
python analyse_outbreak_exposure.py --infection-date 2023-10-15
python analyse_outbreak_exposure.py --from 2024-01-01 --no-llm
```
