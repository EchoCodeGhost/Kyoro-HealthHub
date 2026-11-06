# create_location_schema.py — Erstellt das Schema für location.db

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/utils/create_location_schema.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Erstellt die location.db mit dem zentralen Location-Registry-Schema. Idempotent: kann mehrmals ausgeführt werden.

## Relevanz

Wesentlich für die Speicherung von GPS-Daten in einer separaten Datenbank

## Methode

Erstellt die Tabelle location_registry und die Ortsdaten-Tabellen session_tracks, location_history, location_stays und location_stays_geocoded mit CREATE TABLE IF NOT EXISTS. Eine Tabelle ohne region-Spalte (früheres Schema) wird einmalig neu aufgebaut (lat/lon nullbar, region aus den gespeicherten Koordinaten).

## Datenfluss

- **Liest:** `location.db`, `(wenn`, `existiert`, `zum`, `Prüfen)`
- **Schreibt:** `location.db (Tabellen, Indizes; einmaliger Umbau location_registry)`

## Grenzen

Beim Umbau wird die Region aus bereits gerundeten Koordinaten bestimmt; an Grenzen kann sie von der Region des Originalpunkts abweichen.

## Aufruf

```bash
# Schema erstellen
python3 scripts/utils/create_location_schema.py
```
