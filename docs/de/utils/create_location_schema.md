# create_location_schema.py — Erstellt das Schema für location.db

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/utils/create_location_schema.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Erstellt die location.db mit dem zentralen Location-Registry-Schema. Idempotent: kann mehrmals ausgeführt werden.

## Relevanz

Wesentlich für die Speicherung von GPS-Daten in einer separaten Datenbank

## Methode

Erstellt die Tabellen location_registry und location_tokens (falls benötigt). Nutzt CREATE TABLE IF NOT EXISTS.

## Datenfluss

- **Liest:** `location.db`, `(wenn`, `existiert`, `zum`, `Prüfen)`
- **Schreibt:** `location.db (neue Tabellen)`

## Grenzen

Keine Datenmigration — nur Schema-Erstellung

## Aufruf

```bash
# Schema erstellen
python3 scripts/utils/create_location_schema.py
```
