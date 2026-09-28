# create_schema.py — Datenbank-Schema Phase 1 erstellen

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/utils/create_schema.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Erstellt health_v2.db mit vollem v2-Schema und migriert kleine Tabellen. Phase 1 der Datenbank-Migration.

## Relevanz

Ermöglicht die Erstellung von Datenbank-Schemata, essentiell für die Datenorganisation und -struktur

## Methode

Schritte: 1) health_v2.db mit v2-Schema erstellen, 2) persons + devices befüllen, 3) source_priority (initiale Einträge), 4) Kleine klinische Tabellen aus health.db migrieren, 5) Kontext-Tabellen kopieren (home_*, weather_*, location_*, polar_sleep_*), 6) schema_version + import_log schreiben. Sicher wiederholbar — bricht ab, wenn schema_version 1 bereits vorhanden.

## Datenfluss

- **Liest:** `data/health.db`
- **Schreibt:** `data/health_v2.db (schema_version, import_log, kleine Tabellen)`

## Grenzen

Migration ist einmalig. Vorherige DB bleibt als health.db erhalten. Setzt Python 3.10+ voraus.

## Aufruf

```bash
python create_schema.py
python create_schema.py --help
python create_schema.py --from 2024-01-01 --to 2024-12-31
```
