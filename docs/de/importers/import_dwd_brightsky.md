# DWD Stationsdaten via Brightsky API → weather_dwd_station

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/importers/import_dwd_brightsky.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Importiert DWD-Stationsdaten via Brightsky API

## Relevanz

Ermöglicht den Import von Gesundheitsdaten, essentiell für die umfassende Datenanalyse

## Methode

Brightsky (https://api.brightsky.dev) ist ein kostenloses JSON-Frontend fuer DWD-Stationsdaten. Kein API-Key, keine Registrierung noetig. Stationsauswahl erfolgt automatisch anhand von Koordinaten. Koordinaten kommen aus fetch_daily.py (Config oder Travel-Log).

## Datenfluss

- **Liest:** `Brightsky`, `API`, `(online)`
- **Schreibt:** `weather_dwd_station`

## Grenzen

Abhaengig von DWD/Brightsky API-Verfuegbarkeit.

## Aufruf

```bash
python3 import_dwd_brightsky.py
python3 import_dwd_brightsky.py --date 2026-01-01
```
