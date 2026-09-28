# Query Module — Abfrage- und Berichts-Skripte für Kyoro-HealthHub

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/query/__init__.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Enthält Abfrage- und Berichts-Skripte für Gesundheitsdaten

## Methode

Generierung von Gesundheitsberichten, Datenabfragen und Visualisierungen basierend auf den gespeicherten Daten

## Datenfluss

- **Liest:** `Alle`, `Tabellen`, `aus`, `Kyoro-HealthHub-Datenbank`
- **Schreibt:** `Berichte, Visualisierungen, Export-Dateien`

## Grenzen

Abfragen sind lesend, keine Datenmodifikation

## Aufruf

```bash
python __init__.py
python __init__.py --help
python __init__.py --from 2024-01-01 --to 2024-12-31
```
