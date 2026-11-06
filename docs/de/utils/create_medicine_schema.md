# create_medicine_schema.py — medicine.db initialisieren

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/utils/create_medicine_schema.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Initialisiert medicine.db mit Tabellen für medizinische Daten.

## Relevanz

Ermöglicht die Erstellung von Datenbank-Schemata, essentiell für die Datenorganisation und -struktur

## Methode

Tabellen (identische Schemas wie in health.db zur verlustfreien Migration): lab_manual (manuelle Laborbefunde), lab_results (strukturierte Laborbefunde), medications (Medikamente), assessments (Klinische Scores / Beurteilungen), findings (Befunde mit ICD-Code), diagnoses (ICD-10-codierte Diagnosehistorie). Läuft bei jedem Aufruf zusätzlich fünf Migrationen für frühere medicine.db- Stände, die eine Spalte noch nicht haben (jeweils idempotent, per PRAGMA table_info geprüft): ``_migrate_medications_is_chronic``, ``_migrate_medications_prescriber_pseudonym``, ``_migrate_medications_date_abgabe``, ``_migrate_diagnoses_date_to``, ``_migrate_diagnoses_provider_pseudonym``.

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
