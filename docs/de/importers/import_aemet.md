# AEMET-Importer — Agencia Estatal de Meteorología

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/importers/import_aemet.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Importiert tägliche Klimadaten von AEMET-Messstationen

## Relevanz

Ermöglicht den Import von Gesundheitsdaten, essentiell für die umfassende Datenanalyse

## Methode

Holt tägliche Klimadaten (inkl. Sonnenstunden, Strahlung) von der nächstgelegenen AEMET-Messstation. API-Key: Kostenlose Registrierung unter https://opendata.aemet.es/ In health_config.json: { "apis": { "aemet_api_key": "eyJ..." } }

## Datenfluss

- **Liest:** `AEMET`, `API`, `(online`, `spanische`, `Wetterdaten)`
- **Schreibt:** `health.db (Tabelle weather_aemet)`

## Grenzen

Nur für Aufenthalte in Spanien. Benötigt API-Key.

## Aufruf

```bash
python importers/import_aemet.py --lat 40.4 --lon -3.7 --date-from 2026-06-01 --date-to 2026-06-05
python importers/import_aemet.py --discover --lat 40.4 --lon -3.7
```
