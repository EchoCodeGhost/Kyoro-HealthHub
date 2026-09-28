# Raumklima × Schlaf-Analyse — Temperatur, Luftfeuchtigkeit, CO2, Luftqualität

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/analysis/sleep/analyse_home_environment_sleep.py`

**Evidence tier:** heuristic (deliberate design from domain knowledge, no formal literature or validation basis)

## Purpose

Correlates indoor climate sensor data (temperature, humidity, CO2, PM2.5, VOC, noise) with sleep quality metrics (HRV device-agnostic, sleep efficiency from Oura).

## Relevance

Enables sleep analysis, essential for sleep research and health monitoring

## Method

Pearson correlation (pure Python) per environmental variable × sleep efficiency/HRV; WHO, UBA (German Federal Environment Agency), and EU guidelines used as orientation thresholds.

## Scoring

```
Temperature: 16-19°C optimal bedroom | <16°C too cold | >19°C too warm (Lack & Gradisar 2019)
Humidity: 40-60% optimal | <40% too dry | >60% too humid
CO2: <1000ppm hygienically unobjectionable | 1000-2000ppm elevated, ventilation recommended | >2000ppm unacceptable, ventilate urgently (UBA 2008)
PM2.5: <15 µg/m³ acceptable | 15-35 µg/m³ moderate | >35 µg/m³ high (WHO 2021)
Correlation strength: |r| <0.2 weak | 0.2-0.4 moderate | 0.4-0.7 strong | >0.7 very strong
```

## Data flow

- **Reads:** `home_environment`, `indoor_air_quality`, `measurements`, `oura_sleep_model`
- **Writes:** `analyses/sleep/home_environment_sleep_*.{md,png}`

## Limitations

Heuristic method: Very limited data basis (as of 2026: ~49 days); correlations without significance tests; WHO/UBA thresholds used as orientation, not as validated sleep medicine limits; causal direction not determinable.

## References

- WHO Air Quality Guidelines 2021 (PM2.5 24h: 15 µg/m³), doi:https://iris.who.int/handle/10665/345329
- WHO Night Noise Guidelines for Europe 2009 (Lnight <40 dB, Intervention >55 dB), doi:https://iris.who.int/handle/10665/326486
- WHO/IARC 2023: Formaldehyd als Gruppe-1-Karzinogen; 0.1 mg/m³ Kurzzeit-Richtwert
- Lack & Gradisar 2019, Sleep Med Rev 45:123-135 (Schlafzimmertemperatur 18–20°C)
- UBA 2008 (Ad-hoc-Arbeitsgruppe IRK/AOLG): Leitfaden für die Innenraumhygiene — CO2 als Lüftungsindikator, 1000/2000ppm-Stufung ("Pettenkofer-Zahl")

## Usage

```bash
python analyse_home_environment_sleep.py
python analyse_home_environment_sleep.py --help
python analyse_home_environment_sleep.py --from 2024-01-01 --to 2024-12-31
```
