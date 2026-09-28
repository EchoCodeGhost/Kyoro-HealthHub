# fix_weather_station_person.py — Corrects person attribution for existing

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/migrations/fix_weather_station_person.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

import_homeassistant.py::import_weather_to_db() und import_reise_weather() setzten die person-Spalte nie explizit — beide INSERT-Anweisungen liessen sie auf den Tabellen-Default fallen ('unknown'). Eine spaetere systemweite Pseudonymisierung wandelte einen Teil davon in ein frisch gemuenztes Pseudonym um (PER-982e9b5c), statt sie der tatsaechlichen Person zuzuordnen — weather_station ist Wetterstationsdaten eines Ein-Personen- Haushalts, keine echte zweite Identitaet. Der Importer-Bug ist mit dem Rest dieses Commits behoben; dieses Skript korrigiert die bereits importierten Zeilen.

## Relevanz

Ermoeglicht korrekte personenbezogene Filterung von Wetterstationsdaten, u.a. fuer compute_pem.py's Umwelt-Hinweise

## Methode

UPDATE weather_station SET person=OWN_PERSON_ID WHERE person IN ('unknown', 'PER-982e9b5c') — beide bekannten Fehlwerte in einem Lauf. Idempotent, sicher wiederholt ausfuehrbar.

## Datenfluss

- **Liest:** `health.db`, `(weather_station)`
- **Schreibt:** `health.db (weather_station.person)`

## Grenzen

Betrifft nur weather_station. Andere Tabellen mit aehnlichem Person-Attributionsfehler waeren separat zu pruefen.

## Aufruf

```bash
python3 scripts/migrations/fix_weather_station_person.py --dry-run
python3 scripts/migrations/fix_weather_station_person.py
```
