# Training Performance Analysis

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/analysis/activity/analyse_workout_performance.py`

**Evidenzstufe:** kalibriert (Literaturbasis + Parameter auf persönliche Baselines angepasst, keine externe Validierung)

## Zweck

Analysiert Trainings-Performance aus Polar-Sessions: Volumenentwicklung, HR-Zonenverteilung, Erholungsmuster (Folgetag-HRV-Delta) und PEM-Schwellenschätzung per Dezilanalyse.

## Relevanz

Ermöglicht die Analyse von Aktivitätsdaten, essentiell für die Bewegungs- und Fitnessanalyse

## Methode

Aggregiert kcal, Dauer, HR und Distanz aus sessions/session_metrics; HR-Zonen basierend auf cfg.max_hr (220−Zeitraum als Fallback); Pearson-Korrelation kcal × Folgetag-HRV-Delta.

## Datenfluss

- **Liest:** `sessions`, `session_metrics`, `measurements`
- **Schreibt:** `analyses/activity/*.{md,png}`

## Grenzen

HR-Zonen-Grenzen (60/70/80/90 % HRmax) sind Standardmethode, aber individuelle anaerobe Schwelle kann abweichen. PEM-Schwellenschätzung aus Dezilanalyse ist heuristisch.

## Referenzen

- Midgley AW, McNaughton LR, Jones AM (2007). Training to Enhance the Physiological Determinants of Long-Distance Running Performance. Sports Medicine, 37(10):857-880. doi:10.2165/00007256-200737100-00003
- Achten J, Jeukendrup AE (2003). Heart Rate Monitoring. Sports Medicine, 33(7):517-538. doi:10.2165/00007256-200333070-00004

## Aufruf

```bash
python analyse_workout_performance.py
python analyse_workout_performance.py --help
python analyse_workout_performance.py --from 2024-01-01 --to 2024-12-31
```
