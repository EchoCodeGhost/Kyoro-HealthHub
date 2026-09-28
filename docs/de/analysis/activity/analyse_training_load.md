# Workout load & Recoverys-Analyse

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/analysis/activity/analyse_training_load.py`

**Evidenzstufe:** Heuristik (deliberate Designentscheidung aus Domänenwissen, keine formale Literatur- oder Validierungsbasis)

## Zweck

Analysiert Polar-Trainingsbelastung (Load, Sportart, Dauer) mit Fokus auf PEM-Risiko, Belastungstoleranz und sicheres Aktivitätsbudget; korreliert mit Folgetag-HRV und Schrittzahl.

## Relevanz

Ermöglicht die Analyse von Aktivitätsdaten, essentiell für die Bewegungs- und Fitnessanalyse

## Methode

Aggregiert Training-Sessions aus sessions/session_metrics; korreliert Training-Load mit Folgetag-RMSSD; PEM-Risikomodell (Belastungsgruppen × HRV-Einbruch) eigenentwickelt ohne formale Validierung.

## Berechnung

```
Load classification: low <300 | moderate 300-600 | high 600-900 | very high >900 (Polar Load units)
PEM risk: low | moderate | high | critical (based on ACWR + HRV drop)
```

## Datenfluss

- **Liest:** `sessions`, `session_metrics`, `measurements`, `polar_nightly_hrv`
- **Schreibt:** `analyses/activity/*.{md,png}`

## Grenzen

Heuristische Methode: ACWR-Konzept (Gabbett 2016) ist Orientierung; die konkreten Schwellen und PEM-Risikoklassen sind nicht klinisch validiert. Daten nur für Polar-erfasste Einheiten vorhanden.

## Referenzen

- Gabbett TJ (2016). The training—injury prevention paradox: should athletes be training smarter and harder?. British Journal of Sports Medicine, 50(5):273-280. doi:10.1136/bjsports-2015-095788
- Ruijgt TM, Slaghekke A, Ellens A, Janssen KW, Wüst RCI (2026). Wearable Heart Rate Variability Monitoring, Autonomic Dysfunction and Post-exertional Malaise in Long COVID: An Observational Study. Sports Medicine, online ahead of print. doi:10.1007/s40279-026-02487-4 (peer-reviewed; n=121 Long-COVID + 21 Kontrollen; HRV bleibt nach Belastung nahe/über der ersten ventilatorischen Schwelle einen vollen Tag supprimiert, stärkere Belastung korreliert mit stärker reduzierter nächtlicher HRV — stützt Wearable-HRV als PEM-Risikomarker speziell im Long-COVID-Kontext)

## Aufruf

```bash
python analyse_training_load.py
python analyse_training_load.py --help
python analyse_training_load.py --from 2024-01-01 --to 2024-12-31
```
