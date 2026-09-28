# Sport × Umwelt-Analyse

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/analysis/activity/analyse_sport_environment.py`

**Evidenzstufe:** Heuristik (deliberate Designentscheidung aus Domänenwissen, keine formale Literatur- oder Validierungsbasis)

## Zweck

Korreliert Trainingseinheiten (Sportart, Dauer, Load) mit Umweltdaten (Pollen, Luftqualität, UV, Temperatur) unter Berücksichtigung des Trainingsstandorts via GPS.

## Relevanz

Ermöglicht die Analyse von Aktivitätsdaten, essentiell für die Bewegungs- und Fitnessanalyse

## Methode

Spearman-Rangkorrelation zwischen Pollenbelastung/AQI und Trainingsparametern; GPS-Zentroid aus session_tracks oder location_stays; Standort-Matching mit ±1-Tag-Toleranz.

## Berechnung

```
Correlation strength: |r| <0.2 weak | 0.2-0.4 moderate | 0.4-0.7 strong | >0.7 very strong
Location type: home | travel | mixed
```

## Datenfluss

- **Liest:** `sessions`, `session_metrics`, `pollen`, `air_quality`, `biometeo`, `session_tracks`, `location_stays`, `symptoms`
- **Schreibt:** `analyses/activity/*.{md,png}`

## Grenzen

Heuristische Methode: Keine Kausalitätsaussage; Pollenexposition abhängig von Quell- und Gebietsgenauigkeit; kein personalisierter Allergie-Schwellenwert; GPS-Daten nicht immer vorhanden.

## Referenzen

- D'Amato G, Cecchi L, Bonini S, Nunes C, Annesi-Maesano I, Behrendt H, Liccardi G, Popov T, Van Cauwenberge P (2007). Allergenic pollen and pollen allergy in Europe. Allergy, 62(9):976-990. doi:10.1111/j.1398-9995.2007.01393.x
- Brook RD, Rajagopalan S, Pope CA et al. (2010). Particulate Matter Air Pollution and Cardiovascular Disease. Circulation, 121(21):2331-2378. doi:10.1161/CIR.0b013e3181dbece1

## Aufruf

```bash
python analyse_sport_environment.py
python analyse_sport_environment.py --help
python analyse_sport_environment.py --from 2024-01-01 --to 2024-12-31
```
