# CGM-Glukose-Analyse — Freestyle Libre 3 Continuous Glucose Monitor

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/analysis/metabolic/analyse_cgm_glucose.py`

**Evidenzstufe:** validiert (klinische Validierungsstudie vorhanden: Sensitivität/Spezifität oder Endpunkte prospektiv geprüft)

## Zweck

Analysiert kontinuierliche Glukosedaten (CGM, Freestyle Libre 3): Time-in-Range, Glukosevariabilität, Tagesrhythmus und Zusammenhänge mit Aktivität und HRV.

## Relevanz

Ermöglicht die Stoffwechselanalyse, essentiell für die metabolische Gesundheit

## Methode

TIR/TAR/TBR nach ATTD-Konsensus 2019: Zielbereich 3,9–10,0 mmol/L; CV-Ziel < 36 % (stabile Glukose). Prädiabetes-Schwellen: Nüchtern 5,6 mmol/L, postprandial 7,8 mmol/L.

## Datenfluss

- **Liest:** `cgm_readings`, `blood_glucose`, `sessions`, `measurements`, `(hrv_rmssd/rmssd_ms)`
- **Schreibt:** `analyses/metabolic/*.{md,png} (kein DB-Write)`

## Grenzen

CGM-Sensoren haben eine Messungenauigkeit von ±10–15 %. Kalibrierung und Sensor-Warmup-Phasen sind nicht gesondert gefiltert. n=1, kein RCT-Design.

## Referenzen

- Battelino T, Danne T, Bergenstal RM et al. (2019). Clinical Targets for Continuous Glucose Monitoring Data Interpretation: Recommendations From the International Consensus on Time in Range. Diabetes Care, 42(8):1593-1603. doi:10.2337/dci19-0028

## Aufruf

```bash
python analyse_cgm_glucose.py
python analyse_cgm_glucose.py --help
python analyse_cgm_glucose.py --from 2024-01-01 --to 2024-12-31
```
