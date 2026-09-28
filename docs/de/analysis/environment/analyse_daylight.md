# Tageslicht-Exposition & Circadiane Gesundheit

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/analysis/environment/analyse_daylight.py`

**Evidenzstufe:** Heuristik (deliberate Designentscheidung aus Domänenwissen, keine formale Literatur- oder Validierungsbasis)

## Zweck

Analysiert tägliche Tageslichtexposition (Apple Watch) und deren Zusammenhang mit Schlafqualität, HRV, Energie und Stimmung via Spearman-Korrelation.

## Relevanz

Analysiert den Einfluss von Tageslichtexposition auf Schlafqualität, Stimmung und zirkadianen Rhythmus, essentiell für die Erkennung von Schlafstörungen und die Optimierung der Lichttherapie

## Methode

Summiert time_in_daylight-Einträge aus apple_records; Spearman-Korrelation ohne Multiple-Testing-Korrektur. Richtwert 30 min/Tag als Mindest-Exposition (zirkadiane Rhythmik) ohne RCT-Backing.

## Berechnung

```
Daylight exposure: <30 min/day low | 30-60 min/day moderate | >60 min/day high (circadian rhythm guideline)
Correlation strength: |r| <0.2 weak | 0.2-0.4 moderate | 0.4-0.7 strong | >0.7 very strong
```

## Datenfluss

- **Liest:** `apple_records`, `(time_in_daylight)`, `daily_stress`, `polar_sleep_score`, `symptoms`, `weather_station`
- **Schreibt:** `analyses/environment/*.{md,png} (kein DB-Write)`

## Grenzen

Heuristische Methode: Apple Watch misst Tageslicht indirekt (UV-Sensor oder Bewegungsdaten); keine Lux-Kalibrierung. Konfundierung durch Saisonalität nicht kontrolliert. Korrelationen sind explorativ. n=1.

## Referenzen

- Lewy AJ, Wehr TA, Goodwin FK, Newsome DA, Markey SP (1980). Light suppresses melatonin secretion in humans. Science, 210(4475):1267-1269. doi:10.1126/science.7434030
- Wirz-Justice A, Benedetti F, Terman M (2013). Chronotherapeutics for Affective Disorders: A Clinician's Manual for Light and Wake Therapy (2nd ed.). Karger. doi:10.1159/isbn.978-3-318-02091-5

## Aufruf

```bash
python analyse_daylight.py
python analyse_daylight.py --help
python analyse_daylight.py --from 2024-01-01 --to 2024-12-31
```
