# Body temperature-Verlauf & Entzündungs-Analyse

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/analysis/metabolic/analyse_body_temperature.py`

**Evidenzstufe:** Heuristik (deliberate Designentscheidung aus Domänenwissen, keine formale Literatur- oder Validierungsbasis)

## Zweck

Analysiert Langzeit-Hauttemperatur aus Polar (distal, SL_DISTAL), nächtliche Handgelenktemperatur aus Apple Watch und Oura-Abweichungen; detektiert subfebrile Phasen und zirkadiane Muster.

## Relevanz

Ermöglicht die Stoffwechselanalyse, essentiell für die metabolische Gesundheit

## Methode

Heuristische Schwellen: Oura-Abweichung > 0,8 °C = erhöht; Haut-Distal > 36 °C = ungewöhnlich hoch. Pearson-Korrelation Temperatur × HRV/Symptome. Kein klinisch validierter Fieber-Algorithmus.

## Berechnung

```
Temperature thresholds: Oura deviation >0.8°C elevated | Polar distal >36°C unusually high
Subfebrile phase: persistent elevation above baseline
Correlation strength: |r| <0.2 weak | 0.2-0.4 moderate | 0.4-0.7 strong | >0.7 very strong
```

## Datenfluss

- **Liest:** `measurements`, `(skin_temperature`, `wrist_temp_sleep)`, `oura_temperature_raw`, `daily_stress`, `symptoms`
- **Schreibt:** `analyses/metabolic/*.{md,png} (kein DB-Write)`

## Grenzen

Heuristische Methode: Hauttemperatur (distal) ist kein Maß für Körperkerntemperatur. Oura-Abweichung ist relativ zur persönlichen Baseline, nicht absolut. Consumer-Sensorik, n=1.

## Referenzen

- Mackowiak PA, Wasserman SS, Levine MM (1992). A critical appraisal of 98.6°F, the upper limit of the normal body temperature, and other legacies of Carl Reinhold August Wunderlich. JAMA, 268(12), 1578-1580. doi:10.1001/jama.1992.03490120092034
- Pho GN, Thigpen N, Patel S, Tily H (2023). Feasibility of measuring physiological responses to breakthrough infections and COVID-19 vaccine using a wearable ring sensor. Digital Biomarkers, 1-6. doi:10.1159/000528874 (Ring-Temperaturabweichung als Infektions-Frühwarnsignal)
- Smarr BL, Aschbacher K, Fisher SM, et al. (2020). Feasibility of continuous fever monitoring using wearable devices. Scientific Reports, 10(1):21640. doi:10.1038/s41598-020-78355-6 (peer-reviewt, n=50; periphere Hauttemperatur via Wearable korreliert mit selbstberichtetem Fieber — direkte methodische Stuetze fuer die hier durchgefuehrte Hauttemperatur-Langzeitanalyse)

## Aufruf

```bash
python analyse_body_temperature.py
python analyse_body_temperature.py --help
python analyse_body_temperature.py --from 2024-01-01 --to 2024-12-31
```
