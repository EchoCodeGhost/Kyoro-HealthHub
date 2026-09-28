# Umweltdaten für Reiseaufenthalte → health.db (air_quality, pollen, biometeo)

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/importers/import_travel_environment.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Rückwirkender Import von Umweltdaten (Luftqualität, Pollen, Biometeorologie) für Reiseaufenthalte zur Korrelationsanalyse mit gesundheitlichen Symptomen

## Relevanz

Ermöglicht den Import von Umweltdaten, essentiell für die Analyse von Umweltfaktoren Ermöglicht den Import von Umweltdaten, essentiell für die Analyse von Umweltfaktoren

## Methode

Aggregiert Aufenthaltsdaten aus travel_history.json, location_stays (DB) und GPS-Trainings-Tracks. Für jeden Nicht-Heim-Aufenthalt werden historische Umweltdaten von Open-Meteo (Luftqualität, Pollen, Biometeo) und optional AEMET (Spanien) abgerufen und in die DB geschrieben. Daten werden in die regulären Tabellen (air_quality, pollen, biometeo) gespeichert.

## Datenfluss

- **Liest:** `~/Kyoro-HealthHub/.config/kyoro/travel_history.json`, `health.db:location_stays`, `health.db:location_stays_geocoded`, `health.db:sessions`, `health.db:session_tracks`
- **Schreibt:** `health.db:air_quality, health.db:pollen, health.db:biometeo, health.db:import_log`

## Grenzen

Erfordert Internetverbindung für API-Abfragen. Koordinatenauflösung für Aufenthalte ohne GPS-Daten via Nominatim. AEMET erfordert API-Key (kostenlos, aber manuelle Registrierung). Aufenthalte < 2 km vom Heim werden übersprungen.

## Referenzen

- Open-Meteo API: https://open-meteo.com/en/docs AEMET OpenData: https://opendata.aemet.es/

## Aufruf

```bash
python3 import_travel_environment.py                   # alle Aufenthalte
python3 import_travel_environment.py --from 2022-01-01
python3 import_travel_environment.py --sources travel  # nur travel_history
python3 import_travel_environment.py --dry-run
python3 import_travel_environment.py --force           # vorhandene überschreiben
```
