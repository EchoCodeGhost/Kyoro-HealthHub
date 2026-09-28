# Gefäßgesundheit — Überblick vaskulärer Parameter aus Wearable-Quellen

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/analysis/cardiovascular/analyse_vascular_health.py`

**Evidenzstufe:** Heuristik (deliberate Designentscheidung aus Domänenwissen, keine formale Literatur- oder Validierungsbasis)

## Zweck

Überblicksanalyse vaskulärer Wearable-Parameter: SpO2, Ruhepuls, Aktivität, Hauttemperatur, Atemfrequenz, Pulswellengeschwindigkeit, Körpergewicht und Oura-Erholungsscore.

## Relevanz

Ermöglicht die kardiovaskuläre Analyse, essentiell für die Herz-Kreislauf-Diagnostik

## Methode

Monatliche Aggregation und Trendberechnung je Parameter; Einordnung gegen klinische Referenzbereiche (ESC 2018 PWV <10 m/s, Ruhepuls 50–90 bpm); Pearson-Korrelation zwischen Parametern.

## Berechnung

```
SpO2: normal >=95% | mild 90-95% | moderate 85-90% | severe <85%
PWV: normal <10 m/s | elevated 10-12 m/s | high >12 m/s (ESC 2018)
Resting HR: normal 60-100 bpm | bradycardic <60 | tachycardic >100 (AHA)
```

## Datenfluss

- **Liest:** `measurements`, `daily_stress`, `oura_temperature_raw`, `oura_daytime_stress`, `body_composition`
- **Schreibt:** `analyses/cardiovascular/*.{md,png}`

## Grenzen

Heuristische Methode: Wearable-basierte PWV (Polar PTT) nicht klinisch validiert für Gefäßsteifigkeit; ESC-Referenz gilt für applanationstonometrische Messung (Mancia 2013). Validierte Normwerte: SpO2 <95% (WHO/ESC), Ruhepuls 60-100 bpm (AHA), Atemfrequenz 12-20/min, WHtR >=0.5 (Ashwell 2016). Viszeralfett-Schwellen (>13 erhoet, >17 hoch) sind Geraetehersteller-Klassifikation, nicht WHO/klinisch validiert. Analyse ist beschreibend, ohne Kausalhypothesen.

## Referenzen

- Williams B, Mancia G, Spiering W et al. (2018). 2018 ESC/ESH Guidelines for the management of arterial hypertension. European Heart Journal, 39(33):3021-3104. doi:10.1093/eurheartj/ehy339
- Mancia G, Fagard R, Narkiewicz K et al. (2013). 2013 ESH/ESC Guidelines for the management of arterial hypertension. European Heart Journal, 34(28):2159-2219. doi:10.1093/eurheartj/eht151 (PWV-Klassifikation)
- Ashwell M, Gibson S (2016). Waist-to-height ratio as an indicator of 'early health risk'. BMJ Open, 6(3):e010159. doi:10.1136/bmjopen-2015-010159 (WHtR ≥0.5)

## Aufruf

```bash
python analyse_vascular_health.py
python analyse_vascular_health.py --help
python analyse_vascular_health.py --from 2024-01-01 --to 2024-12-31
```
