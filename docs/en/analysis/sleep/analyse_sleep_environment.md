# Umgebungs- & Sleepqualitäts-Analyse

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/analysis/sleep/analyse_sleep_environment.py`

**Evidence tier:** heuristic (deliberate design from domain knowledge, no formal literature or validation basis)

## Purpose

Analyses the association between indoor and outdoor environmental parameters (temperature, humidity, lux, air pressure, solar radiation) and sleep quality as well as HRV.

## Relevance

Enables sleep analysis, essential for sleep research and health monitoring

## Method

Spearman rank correlation between environmental parameters and sleep/HRV; custom optimal value ranges (bedroom 16–19 °C, humidity 40–60 %).

## Scoring

```
Indoor temperature: 16-19°C optimal bedroom (Lack & Gradisar 2019)
Humidity: 40-60% optimal
Lux: higher = brighter (daytime correlation)
Correlation strength: |r| <0.2 weak | 0.2-0.4 moderate | 0.4-0.7 strong | >0.7 very strong
```

## Data flow

- **Reads:** `home_environment`, `weather_station`, `daily_stress`
- **Writes:** `analyses/sleep/*.{md,png}`

## Limitations

Heuristic method: Observational study without causal inference; optimal values from general sleep hygiene guidelines, not individually validated. Data only available if Home Assistant sensors are present.

## References

- Okamoto-Mizuno K, Mizuno K (2012). Effects of thermal environment on sleep and circadian rhythm. Journal of Physiological Anthropology, 31(1). doi:10.1186/1880-6805-31-14
- Hirshkowitz M, Whiton K, Albert SM et al. (2015). National Sleep Foundation’s sleep time duration recommendations: methodology and results summary. Sleep Health, 1(1):40-43. doi:10.1016/j.sleh.2014.12.010

## Usage

```bash
python analyse_sleep_environment.py
python analyse_sleep_environment.py --help
python analyse_sleep_environment.py --from 2024-01-01 --to 2024-12-31
```
