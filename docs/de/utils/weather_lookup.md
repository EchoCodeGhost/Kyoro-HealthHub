# Wetter-Lookup for beliebige Zeitpunkte and Koordinaten.

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/utils/weather_lookup.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Ermöglicht Wetterdaten-Abfragen für beliebige Zeitpunkte und Koordinaten

## Relevanz

Ermöglicht die Suche und Referenzierung von Daten, essentiell für die Datenintegration

## Methode

Strategie: Innerhalb HOME_RADIUS_M → lokale Wetterstation; außerhalb → Open-Meteo Archive API mit Caching in weather_remote

## Datenfluss

- **Liest:** `Externe`, `Wetter-APIs`, `(Open-Meteo`, `DWD`, `Brightsky)`
- **Schreibt:** `Keine Tabellen (gibt Wetterdaten als Dict zurueck)`

## Grenzen

Genauigkeit abhängig von Open-Meteo-Daten und lokaler Station

## Aufruf

```bash
python weather_lookup.py
python weather_lookup.py --help
python weather_lookup.py --from 2024-01-01 --to 2024-12-31
```
