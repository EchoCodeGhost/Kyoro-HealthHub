# health_ecg.py — EKG-Analyse fuer Apple Watch ECG CSVs

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/query/health_ecg.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Analysiert Apple Watch EKG-Aufzeichnungen: R-Peak-Detektion, Herzfrequenz, RR-Intervall-Variabilitaet, Rhythmus-Unregelmaessigkeiten

## Relevanz

Ermöglicht EKG-spezifische Abfragen, essentiell für die kardiologische Analyse

## Methode

Laedt EKG-CSV-Dateien aus dem Apple ECG-Verzeichnis und fuehrt algorithmische Analysen durch: - Bandpassfilter (5-25 Hz) zur Baseline-Korrektur - R-Peak-Detektion mit dynamischer Schwelle (0.5 SD) - Validierung: RR-Intervalle 300-1800ms (33-200 bpm) - HRV-Metriken: RMSSD, SDNN, pNN50, Variationskoeffizient - Unregelmaessigkeits-Metriken: CV_RR, Irregularity Index Optional: Plots (EKG-Signal + RR-Tachogramm) und detaillierte Metriken (experimentell) Zeigt Zusammenfassung mit Klassifizierungen und PEM-Warnungen an.

## Datenfluss

- **Liest:** `Apple`, `Watch`, `EKG-CSV`, `Dateien`, `aus`, `data/ecg/`, `oder`, `health_config.apple_xml.parent/electrocardiograms/`
- **Schreibt:** `analyses/ekg/ Verzeichnis (Plots als PNG-Dateien)`

## Grenzen

Experimentelle algorithmische Analyse. Resultate mit Vorsicht interpretieren. Abhaengig von Apple Watch EKG-Datenverfuegbarkeit.

## Aufruf

```bash
python health_ecg.py
python health_ecg.py --plot
python health_ecg.py --full
```
