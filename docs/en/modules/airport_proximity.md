# Flughafennähe-Erkennung: strukturelles Standortrisiko unabhängig von Ausbrüchen

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/modules/airport_proximity.py`

**Evidence tier:** heuristic (deliberate design from domain knowledge, no formal literature or validation basis)

## Purpose

Determines the current home location from location_stays (is_home=1) and checks the distance to the nearest major international airport from a curated reference list. Below a radius threshold, returns a standing-risk entry in the same shape as known_risk_exposures.json, for merging with the manually curated entries in the outbreak exposure report.

## Relevance

Automatically detects whether the current home location lies near a major international airport — a structural, standing risk factor for locally acquired (non-travel-associated) aircraft-imported diseases such as "airport malaria". Unlike the outbreak/endemic analysis (analyse_outbreak_exposure.py, analyse_pathogen_exposure.py), this is NOT matched against concrete reported outbreak events — it raises pretest probability regardless of whether an outbreak has been reported, closing the gap a travel-/outbreak-only history has (malaria is often not even considered in practice without a travel history).

## Method

Haversine distance to the nearest airport in MAJOR_INTERNATIONAL_AIRPORTS (curated, non- exhaustive list of major international hubs, weighted toward Europe/Germany). Two radius tiers: <5 km = "high" (classic "airport malaria" zone per Isaäcson 1989), 5-15 km = "medium" (wider zone, baggage/vehicle vector rather than aircraft cabin).

## Scoring

```
Zwei Radius-Stufen (Haversine-Distanz Wohnort zu nächstem Flughafen aus
MAJOR_INTERNATIONAL_AIRPORTS):
  AIRPORT_RADIUS_HOCH_KM   = 5.0 km  -> level "high"   (klassische "Airport-Malaria"-Zone, Isaäcson 1989)
  AIRPORT_RADIUS_MITTEL_KM = 15.0 km -> level "medium" (weitere Zone, Gepäck-/Fahrzeugvektor)
  > 15 km -> kein Treffer, leere Liste
Rückgabe ist ein einzelner known_risk_exposures-artiger Eintrag (slug "malaria",
level, description, notes, auto=True), kein numerischer Score — heuristisch,
keine epidemiologische Validierung der Radius-Schwellen.
```

## Data flow

- **Reads:** `location_stays`, `location_stays_geocoded`
- **Writes:** `keine (reine Berechnungsfunktion, kein DB-Schreibzugriff — der Aufrufer entscheidet, was mit dem Ergebnis geschieht)`

## Limitations

Airport list is a curated selection of major international hubs (Europe-weighted), not an exhaustive world list — a missing airport causes a false negative, not a false alarm. Radius thresholds (5/15 km) are a rough, project-internal heuristic without formal epidemiological calibration; documented cases per Isaäcson 1989 mostly occur close (a few km) to the airport, with isolated cases further away (baggage/vehicle-transported mosquito). Only malaria is well documented for this phenomenon; other Aedes-/Anopheles-borne diseases (dengue, chikungunya, zika) are theoretically plausible via the same transport route but not comparably documented in the literature — deliberately not tagged with the same confidence.

## References

- Isaäcson M (1989). Airport malaria: a review. Bulletin of the World Health Organization, 67(6), 737-743. PMID:2699278
- Alenou LD, Etang J (2021). Airport Malaria in Non-Endemic Areas: New Insights into Mosquito Vectors, Case Management and Major Challenges. Microorganisms, 9(10), 2160. doi:10.3390/microorganisms9102160

## Usage

```bash
python3 -c "from modules.airport_proximity import nearest_airport; print(nearest_airport(50.05, 8.57))"
python3 -c "from modules.db import open_db; from modules.airport_proximity import home_airport_risk_exposures; print(home_airport_risk_exposures(open_db()))"
```
