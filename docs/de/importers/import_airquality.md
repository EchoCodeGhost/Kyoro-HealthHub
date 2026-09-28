# Open-Meteo Luftqualität, Pollen und Biometeo → health.db (air_quality, pollen, biometeo)

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/importers/import_airquality.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Import von Umweltdaten (Luftqualität, Pollen, Biometeorologie) von Open-Meteo API

## Relevanz

Ermöglicht den Import von Gesundheitsdaten, essentiell für die umfassende Datenanalyse Ermöglicht den Import von Gesundheitsdaten, essentiell für die umfassende Datenanalyse

## Methode

Abruf von Luftqualitätsdaten (PM2.5, PM10, NO2, O3, CO, AQI, Staub) und Pollendaten (Birke, Erle, Gräser, Beifuß, Ragweed, Olive) über Air Quality API. Biometeo-Daten (Sonnenschein, Strahlung, gefühlte Temperatur, Taupunkt, Feuchte) werden über Archive API abgerufen. Tageswerte werden aggregiert.

## Datenfluss

- **Liest:** `Open-Meteo`, `Air`, `Quality`, `API`, `Open-Meteo`, `Archive`, `API`
- **Schreibt:** `health.db:air_quality, health.db:pollen, health.db:biometeo, health.db:import_log`

## Grenzen

Erfordert Internetverbindung. Datenabruf in 90-Tage-Chunks. Koordinaten werden gerundet. Historische Daten ab 2013-01-01 verfügbar. Keine Echtzeit-Daten (leicht verzögert).

## Referenzen

- Open-Meteo Air Quality API: https://open-meteo.com/en/docs/air-quality-api Open-Meteo Archive API: https://open-meteo.com/en/docs/archive-api

## Aufruf

```bash
python3 import_airquality.py --lat 51.2 --lon 10.5
python3 import_airquality.py --update --from 2024-01-01
```
