# Körpertemperatur-Analyse — Oura, Apple Watch, Polar

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/analysis/cardiovascular/analyse_oura_temperature.py`

**Evidenzstufe:** Heuristik (deliberate Designentscheidung aus Domänenwissen, keine formale Literatur- oder Validierungsbasis)

## Zweck

Analysiert Hauttemperatur-Daten aus Oura, Apple Watch und Polar auf Krankheitsmuster, Zirkadianrhythmus, zyklische Schwankungen und Frühwarnsignale.

## Relevanz

Ermöglicht die kardiovaskuläre Analyse, essentiell für die Herz-Kreislauf-Diagnostik

## Methode

Tagesaggregat je Quelle; Spearman-Korrelation mit Zyklusphase und Symptomen; eigener Fieber-Schwellenwert (--fever-threshold, Default 0.5 °C Oura-Abweichung); Zirkadianer Vergleich über Stundenmittelwerte.

## Berechnung

```
Fever threshold: >=0.5°C Oura deviation | >=37.0°C Apple Watch wrist temperature
Temperature baseline: personal mean (Oura) | absolute (Apple Watch, Polar)
```

## Datenfluss

- **Liest:** `oura_temperature_raw`, `measurements`, `symptoms`, `reproductive_health`
- **Schreibt:** `analyses/cardiovascular/oura_temperature_*.{md,png}`

## Grenzen

Heuristische Methode: Drei Quellen mit unterschiedlichen Skalen (Abweichung vs. Absolutwert) nicht direkt vergleichbar; Fieberschwellenwert (Default 0.5 °C Oura-Abweichung) heuristisch; Oura-Abweichung ist relativ zur persönlichen Baseline, nicht zu einem absoluten Grenzwert; Apple-Watch-Schwelle 37.0 °C (absolute Handgelenktemperatur im Schlaf) ist heuristisch — Hauttemperatur am Handgelenk liegt typischerweise unter 37 °C und ist kein direktes Surrogat für Kerntemperatur.

## Referenzen

- Grant A, Smarr B (2022). Feasibility of continuous distal body temperature for passive, early pregnancy detection. PLOS Digital Health, 1(5), e0000034. doi:10.1371/journal.pdig.0000034 (Zyklus-/Schwangerschaftsbezug)
- Pho GN, Thigpen N, Patel S, Tily H (2023). Feasibility of measuring physiological responses to breakthrough infections and COVID-19 vaccine using a wearable ring sensor. Digital Biomarkers, 1-6. doi:10.1159/000528874 (Ring-Temperaturabweichung als Infektions-Frühwarnsignal)
- Smarr BL, Aschbacher K, Fisher SM, et al. (2020). Feasibility of continuous fever monitoring using wearable devices. Scientific Reports, 10(1):21640. doi:10.1038/s41598-020-78355-6 (peer-reviewt, n=50, gleiche Autor:innengruppe wie Grant/Smarr 2022 oben; periphere Hauttemperatur korreliert mit selbstberichtetem Fieber, Krankheit vor Symptomerkennung feststellbar)

## Aufruf

```bash
python analyse_oura_temperature.py
python analyse_oura_temperature.py --help
python analyse_oura_temperature.py --from 2024-01-01 --to 2024-12-31
```
