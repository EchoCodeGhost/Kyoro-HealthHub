# Importers Module — Datenimport-Skripte für Kyoro-HealthHub

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/importers/__init__.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Enthält alle Import-Skripte für Gesundheitsdaten aus verschiedenen Quellen

## Methode

Import von Daten aus Wearables (Polar, Garmin, Apple, Oura, etc.), manuellen Eingaben, Laborwerten, Umweltdaten und anderen Quellen

## Datenfluss

- **Liest:** `Externe`, `Datenquellen`, `(CSV`, `JSON`, `APIs)`
- **Schreibt:** `Rohdaten-Tabellen in Kyoro-HealthHub-Datenbank`

## Grenzen

Datenformat und -qualität hängt von der Quelle ab

## Aufruf

```bash
python __init__.py
python __init__.py --help
python __init__.py --from 2024-01-01 --to 2024-12-31
```
