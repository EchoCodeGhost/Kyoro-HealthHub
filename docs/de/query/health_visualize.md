# health_visualize.py — Gesundheitsdaten Dashboard Visualisierung

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/query/health_visualize.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Erstellt ein Dashboard mit Visualisierungen von Gesundheitsmetriken aus der Datenbank

## Relevanz

Bietet Visualisierungsfunktionen für Gesundheitsdaten, essentiell für die Datenpräsentation

## Methode

Erstellt ein mehrseitiges Dashboard mit matplotlib. Unterstuetzt zwei Formate: - dashboard: Einzes PNG mit mehreren Plots in einem Grid (Standard) - individual: Einzelne PNG-Dateien pro Metrik Plots umfassen: HRV, Ruhepuls, Stress-Score, SpO2, Schlaf, Trainingsbelastung, zirkadianer Rhythmus, VO2max, Blutdruck, Gewicht, orthostatische Tests, PEM-Muster. Farben und Stile sind vordefiniert. Daten werden aus den Tabellen gelesen.

## Datenfluss

- **Liest:** `measurements`, `(HRV/SpO2/VO2max`, `ueber`, `modules/metric_loader.py`, `-`, `geraeteunabhaengig)`, `daily_stress`, `apple_records`, `training-View`, `heart_rate-View`, `sessions`, `session_metrics`, `pem_correlation`
- **Schreibt:** `analyses/dashboard/ Verzeichnis (PNG-Dateien)`

## Grenzen

Abhaengig von Datenverfuegbarkeit. Keine Datenmanipulation, nur Visualisierung.

## Aufruf

```bash
python health_visualize.py
python health_visualize.py --format individual
python health_visualize.py --only hrv,stress
python health_visualize.py --format png
```
