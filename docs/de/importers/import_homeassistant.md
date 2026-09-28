# Home Assistant → health.db Import

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/importers/import_homeassistant.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Holt Sensordaten von Home Assistant-Geräten und speichert sie als Tagesmittel/-min/-max in die health.db. Unterstützt Philips Somneo (Schlafzimmer-Umgebung), EcoWitt-Wetterstationen, DWD-Stationen und Luftreiniger (Dyson, VeSync).

## Relevanz

Ermöglicht den Import von Gesundheitsdaten, essentiell für die umfassende Datenanalyse

## Methode

Nutzt die Home Assistant Statistics API. Konfiguration über ~/.config/kyoro/ha_config.json mit URL, Token und Entitäten. Unterstützt: Temperatur, Luftfeuchtigkeit, Licht, Geräuschpegel, Wetterdaten, Luftqualität. Daten werden als Tagesaggregate gespeichert.

## Datenfluss

- **Liest:** `Home`, `Assistant`, `Statistics`, `API`, `(http://homeassistant.local:8123)`
- **Schreibt:** `health.db (weather_station, indoor_air_quality, etc.)`

## Grenzen

Abhängig von der Verfügbarkeit der Home Assistant API und der Konfiguration. Keine medizinische Interpretation.

## Aufruf

```bash
python import_homeassistant.py --setup
python import_homeassistant.py --discover
python import_homeassistant.py
python import_homeassistant.py --update
python import_homeassistant.py --from 2024-01-01 --to 2025-12-31
python import_homeassistant.py --discover-airpurifiers
python import_homeassistant.py --add-airpurifier sensor.dyson_pm25
```
