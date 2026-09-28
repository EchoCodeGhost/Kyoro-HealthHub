# Symptomtagebuch CSV → health.db (symptoms)

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/importers/import_symptom_diary.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Import von Symptomdaten aus der Symptom diary-App (Adam C.) für Longitudinal-Analysen

## Relevanz

Ermöglicht den Import von Symptomdaten, essentiell für die klinische Analyse

## Methode

Parsen von CSV-Dateien mit breitem Format (ein Symptom pro Spalte, ein Tag pro Zeile). Werte-Mapping auf numerische Skala (0-4) und Speicherung in symptoms-Tabelle. Kategorie-Zuordnung über KATEGORIE_DEFAULTS und DB-Abfrage.

## Datenfluss

- **Liest:** `~/Kyoro-HealthHub/imports/symptomtagebuch/*.csv`, `health.db:symptoms`, `health.db:user_context`
- **Schreibt:** `health.db:symptoms, health.db:user_context, health.db:import_log`

## Grenzen

Verarbeitet nur Dateien im CSV-Format. Notizen werden separat in user_context gespeichert. Historische Daten können nicht nachträglich geändert werden (INSERT OR IGNORE).

## Aufruf

```bash
python3 import_symptom_diary.py         # all CSVs
python3 import_symptom_diary.py --update # only neue Daten
```
