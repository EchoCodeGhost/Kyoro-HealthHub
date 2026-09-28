# Muster-Analyse — tägliche/wöchentliche Gesundheitsübersicht

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/analysis/internal_medicine/analyse_overview.py`

**Evidenzstufe:** kalibriert (Literaturbasis + Parameter auf persönliche Baselines angepasst, keine externe Validierung)

## Zweck

Kombiniert alle wichtigen Biomarker (RHR, HRV, Schlaf, SpO₂, Aktivität, Symptome) in einer täglichen/wöchentlichen Übersichtsanalyse mit Ereignismarkern aus clinical.events.

## Relevanz

Bietet eine integrierte Übersicht über alle Gesundheitsdaten, essentiell für die schnelle Orientierung und die Identifikation von Auffälligkeiten in komplexen Datensätzen

## Methode

7-Tage-Rollmittel je Biomarker; Zusammenführung aus mehreren Compute- und Import-Tabellen (measurements, sessions, oura_sleep_model); Ereignislinien aus konfigurierter clinical.events-Liste.

## Datenfluss

- **Liest:** `measurements`, `sessions`, `session_metrics`, `oura_sleep_model`, `symptoms`
- **Schreibt:** `analyses/internal_medicine/overview_*.{md,png}`

## Grenzen

Aggregations-Dashboard ohne Signifikanztests; SpO₂-Schwellenwerte (94/90 %) sind klinische Orientierungswerte, nicht individuell kalibriert; Datenqualität variiert stark je nach verfügbaren Geräten.

## Referenzen

- Task Force of the European Society of Cardiology and the North American Society of Pacing and Electrophysiology (1996). Heart rate variability: standards of measurement, physiological interpretation, and clinical use. Circulation, 93(5), 1043-1065. doi:10.1161/01.CIR.93.5.1043
- Shaffer F, Ginsberg JP (2017). An overview of heart rate variability metrics and norms. Frontiers in Public Health, 5:258. doi:10.3389/fpubh.2017.00258

## Aufruf

```bash
python analyse_overview.py
python analyse_overview.py --help
python analyse_overview.py --from 2024-01-01 --to 2024-12-31
```
