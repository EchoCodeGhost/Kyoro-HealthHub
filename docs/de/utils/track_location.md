# iPhone location tracker via Home Assistant

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/utils/track_location.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Verfolgt iPhone-Standortdaten über Home Assistant für Wetter- und Reiseanalysen

## Relevanz

Ermöglicht die Verfolgung und Analyse von Standortdaten, essentiell für die Mobilitätsanalyse

## Methode

Abfrage des aktuellen Standorts von Home Assistant alle paar Stunden; speichert über location_store in location.db::location_history (Genauigkeit und Zonen nach location_privacy.json, Importer track_location); Wetter-Importer nutzt diese Daten für Open-Meteo-Standortbestimmung. Koordinaten für externe APIs nach `external_api` in `location_privacy.json` vergröbert (Standard 1 Stelle, ~11 km; Ortsnamen 2 Stellen).

## Datenfluss

- **Liest:** `~/.config/kyoro/travel_history.json`, `ext.`, `Geolocation-APIs`
- **Schreibt:** `~/.config/kyoro/travel_history.json, location.db::location_history`

## Grenzen

Abhängig von Home Assistant-Konfiguration und iPhone-Standortfreigabe

## Aufruf

```bash
python track_location.py
python track_location.py --help
python track_location.py --from 2024-01-01 --to 2024-12-31
```
