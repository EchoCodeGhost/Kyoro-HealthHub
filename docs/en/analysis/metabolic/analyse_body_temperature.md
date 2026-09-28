# Body temperature-Verlauf & Entzündungs-Analyse

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/analysis/metabolic/analyse_body_temperature.py`

**Evidence tier:** heuristic (deliberate design from domain knowledge, no formal literature or validation basis)

## Purpose

Analyses long-term skin temperature from Polar (distal), nightly wrist temperature from Apple Watch and Oura deviations; detects subfebrile phases and circadian patterns.

## Relevance

Enables metabolic analysis, essential for metabolic health

## Method

Heuristic thresholds: Oura deviation > 0.8 °C = elevated; distal skin > 36 °C = unusually high. Pearson correlation temperature × HRV/symptoms. No clinically validated fever algorithm.

## Scoring

```
Temperature thresholds: Oura deviation >0.8°C elevated | Polar distal >36°C unusually high
Subfebrile phase: persistent elevation above baseline
Correlation strength: |r| <0.2 weak | 0.2-0.4 moderate | 0.4-0.7 strong | >0.7 very strong
```

## Data flow

- **Reads:** `measurements`, `(skin_temperature`, `wrist_temp_sleep)`, `oura_temperature_raw`, `daily_stress`, `symptoms`
- **Writes:** `analyses/metabolic/*.{md,png} (kein DB-Write)`

## Limitations

Heuristic method: Skin temperature (distal) does not reflect core body temperature. Oura deviation is relative to personal baseline, not absolute. Consumer sensors, n=1.

## References

- Mackowiak PA, Wasserman SS, Levine MM (1992). A critical appraisal of 98.6°F, the upper limit of the normal body temperature, and other legacies of Carl Reinhold August Wunderlich. JAMA, 268(12), 1578-1580. doi:10.1001/jama.1992.03490120092034
- Pho GN, Thigpen N, Patel S, Tily H (2023). Feasibility of measuring physiological responses to breakthrough infections and COVID-19 vaccine using a wearable ring sensor. Digital Biomarkers, 1-6. doi:10.1159/000528874 (Ring-Temperaturabweichung als Infektions-Frühwarnsignal)
- Smarr BL, Aschbacher K, Fisher SM, et al. (2020). Feasibility of continuous fever monitoring using wearable devices. Scientific Reports, 10(1):21640. doi:10.1038/s41598-020-78355-6 (peer-reviewt, n=50; periphere Hauttemperatur via Wearable korreliert mit selbstberichtetem Fieber — direkte methodische Stuetze fuer die hier durchgefuehrte Hauttemperatur-Langzeitanalyse)

## Usage

```bash
python analyse_body_temperature.py
python analyse_body_temperature.py --help
python analyse_body_temperature.py --from 2024-01-01 --to 2024-12-31
```
