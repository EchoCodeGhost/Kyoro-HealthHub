# create_medicine_schema.py — medicine.db initialisieren

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/utils/create_medicine_schema.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Initialisiert medicine.db mit Tabellen für medizinische Daten.

## Relevanz

Ermöglicht die Erstellung von Datenbank-Schemata, essentiell für die Datenorganisation und -struktur

## Methode

Tabellen (identische Schemas wie in health.db zur verlustfreien Migration): lab_manual (manuelle Laborbefunde), lab_results (strukturierte Laborbefunde), medications (Medikamente), assessments (Klinische Scores / Beurteilungen), findings (Befunde mit ICD-Code). Läuft bei jedem Aufruf zusätzlich ``_migrate_medications_is_chronic`` — fügt is_chronic per ALTER TABLE nach, falls eine ältere medicine.db die Spalte noch nicht hat (idempotent, per PRAGMA table_info geprüft).

## Datenfluss

- **Liest:** `Keine`, `(erstellt`, `neues`, `Schema)`
- **Schreibt:** `medicine.db (Tabellen: lab_manual, lab_results, medications, assessments, findings)`

## Grenzen

Einmalig aufrufen. Wiederholte Ausfuehrung ist idempotent (CREATE IF NOT EXISTS).

## Aufruf

```bash
python3 scripts/utils/create_medicine_schema.py
python3 scripts/utils/create_medicine_schema.py --force
```
