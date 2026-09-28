# Sport × Umwelt-Analyse

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/analysis/activity/analyse_sport_environment.py`

**Evidence tier:** heuristic (deliberate design from domain knowledge, no formal literature or validation basis)

## Purpose

Correlates training sessions (sport type, duration, load) with environmental data (pollen, air quality, UV, temperature) taking training location via GPS into account.

## Relevance

Enables activity data analysis, essential for movement and fitness analysis

## Method

Spearman rank correlation between pollen load/AQI and training parameters; GPS centroid from session_tracks or location_stays; location matching with ±1-day tolerance.

## Scoring

```
Correlation strength: |r| <0.2 weak | 0.2-0.4 moderate | 0.4-0.7 strong | >0.7 very strong
Location type: home | travel | mixed
```

## Data flow

- **Reads:** `sessions`, `session_metrics`, `pollen`, `air_quality`, `biometeo`, `session_tracks`, `location_stays`, `symptoms`
- **Writes:** `analyses/activity/*.{md,png}`

## Limitations

Heuristic method: No causal inference; pollen exposure depends on source and location accuracy; no personalised allergy threshold; GPS data not always available.

## References

- D'Amato G, Cecchi L, Bonini S, Nunes C, Annesi-Maesano I, Behrendt H, Liccardi G, Popov T, Van Cauwenberge P (2007). Allergenic pollen and pollen allergy in Europe. Allergy, 62(9):976-990. doi:10.1111/j.1398-9995.2007.01393.x
- Brook RD, Rajagopalan S, Pope CA et al. (2010). Particulate Matter Air Pollution and Cardiovascular Disease. Circulation, 121(21):2331-2378. doi:10.1161/CIR.0b013e3181dbece1

## Usage

```bash
python analyse_sport_environment.py
python analyse_sport_environment.py --help
python analyse_sport_environment.py --from 2024-01-01 --to 2024-12-31
```
