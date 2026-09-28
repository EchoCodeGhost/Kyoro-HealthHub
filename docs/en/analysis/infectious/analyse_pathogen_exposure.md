# Lifetime-Pathogen-Expositionsanalyse

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/analysis/infectious/analyse_pathogen_exposure.py`

**Evidence tier:** heuristic (deliberate design from domain knowledge, no formal literature or validation basis)

## Purpose

Estimates lifetime pathogen exposure risks from travel history, GPS clusters and GPX routes by matching against outbreak and endemic patterns data and climate zone risk models.

## Relevance

Supports infection-related data analysis and decision-making through systematic processing of wearable and symptom data

## Method

Geo-matching (ISO country, coordinate radius, region text) combined with temporal overlap score; aggregation over all available stay sources (JSON, DB, Google Takeout, GPX).

## Scoring

```
Expositions-Score je Pathogen (heuristisch, projektintern):
Schweregewichte: {"hoch": 1.0, "mittel": 0.6, "niedrig": 0.25}
Aufenthaltsdauer-Faktor: dur = min(days, 30) / 30
Komponent-Score: w × (0.3 + 0.7 × dur)
Lifetime-Score: Summe aller Komponent-Scores je Pathogen
Basis: projektintern, keine epidemiologische Validierung.
```

## Data flow

- **Reads:** `outbreak_events`, `endemic_ref`, `location_stays`, `session_tracks`
- **Writes:** `analyses/infectious/pathogen_exposure_*.{md,txt}`

## Limitations

Heuristic method: Heuristic geo and time-window matching without epidemiological validation; severity weights (1.0/0.6/0.25) and score formula are project-internal; outbreak data requires manual maintenance; climate zone risk model is simplified (latitude classes); results only for hypothesis generation in medical consultation (no substitute for serology).

## References

- Brownstein JS, Freifeld CC, Reis BY, Mandl KD (2008). Surveillance Sans Frontières: Internet-based emerging infectious disease intelligence and the HealthMap project. PLoS Medicine, 5(7), e151. doi:10.1371/journal.pmed.0050151
- Aarestrup FM, Brown EW, Detter C, et al. (2012). Integrating genome-based informatics to modernize global disease monitoring, information sharing, and response. Emerging Infectious Diseases, 18(11), e1. doi:10.3201/eid1811.120453

## Usage

```bash
python analyse_pathogen_exposure.py
python analyse_pathogen_exposure.py --help
python analyse_pathogen_exposure.py --from 2024-01-01 --to 2024-12-31
```
