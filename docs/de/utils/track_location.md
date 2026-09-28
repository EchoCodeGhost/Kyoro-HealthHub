# iPhone location tracker via Home Assistant

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/utils/track_location.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Verfolgt iPhone-Standortdaten über Home Assistant für Wetter- und Reiseanalysen

## Relevanz

Ermöglicht die Verfolgung und Analyse von Standortdaten, essentiell für die Mobilitätsanalyse

## Methode

Abfrage des aktuellen Standorts von Home Assistant alle paar Stunden; speichert in location_history; Wetter-Importer nutzt diese Daten für Open-Meteo-Standortbestimmung

## Datenfluss

- **Liest:** `~/.config/kyoro/travel_history.json`, `ext.`, `Geolocation-APIs`
- **Schreibt:** `~/.config/kyoro/travel_history.json`

## Grenzen

Abhängig von Home Assistant-Konfiguration und iPhone-Standortfreigabe

## Aufruf

```bash
python track_location.py
python track_location.py --help
python track_location.py --from 2024-01-01 --to 2024-12-31
```
