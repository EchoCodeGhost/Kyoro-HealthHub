# Respiration rate im Sleep — Analyse

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/analysis/sleep/analyse_respiration.py`

**Evidenzstufe:** Heuristik (deliberate Designentscheidung aus Domänenwissen, keine formale Literatur- oder Validierungsbasis)

## Zweck

Analysiert nächtliche Atemfrequenztrends aus Garmin- und Apple-Watch-Daten auf Ausreißer, Trends und Korrelationen mit Schlafqualität und HRV.

## Relevanz

Ermöglicht die Schlafanalyse, essentiell für die Schlafforschung und Gesundheitsüberwachung

## Methode

Tagesaggregat (AVG, MIN, MAX) aus measurements; Ausreißerdetektion mit eigenen Schwellen (>18/min Warnung, <10/min Warnung); gleitender Durchschnitt.

## Berechnung

```
Respiratory rate: <10/min warning | 12-20/min normal | >18/min warning (night average)
Outlier detection: values outside normal range flagged
Correlation strength: |r| <0.2 weak | 0.2-0.4 moderate | 0.4-0.7 strong | >0.7 very strong
```

## Datenfluss

- **Liest:** `measurements`
- **Schreibt:** `analyses/sleep/*.{md,png}`

## Grenzen

Heuristische Methode: Grenzwert 18/min ist literaturbasiert (Normwert 12–20/min), aber scriptspezifisch gewählt; Garmin-Atemfrequenz nur während des Schlafs erfasst. Keine Validierung als Detektor.

## Referenzen

- Cretikos MA, Bellomo R, Hillman K, Chen J, Finfer S, Flabouris A (2008). Respiratory rate: the neglected vital sign. Medical Journal of Australia, 188(11):657-659. doi:10.5694/j.1326-5377.2008.tb01825.x
- Massaroni C, Nicolò A, Schena E, Sacchetti M (2020). Remote Respiratory Monitoring in the Time of COVID-19. Frontiers in Physiology, 11:635. doi:10.3389/fphys.2020.00635

## Aufruf

```bash
python analyse_respiration.py
python analyse_respiration.py --help
python analyse_respiration.py --from 2024-01-01 --to 2024-12-31
```
