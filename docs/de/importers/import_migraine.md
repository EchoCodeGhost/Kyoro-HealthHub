# Migraine-App → health.db

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/importers/import_migraine.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Importiert Migräne- und Kopfschmerz-Daten aus der Migraine-App in die health.db. Ermöglicht detaillierte Dokumentation von Anfällen und Bewertung der Beeintächtigung.

## Relevanz

Ermöglicht den Import von Gesundheitsdaten, essentiell für die umfassende Datenanalyse

## Methode

Liest .mbu-Backup-Dateien aus ~/Kyoro-HealthHub/imports/migraene_app/. Mapping: Migräne-Anfälle → sessions (type='migraine') + session_metrics, HIT-6 / MIDAS Fragebögen → assessments. Intensität und Typ werden nach vordefinierten Mappings übersetzt.

## Datenfluss

- **Liest:** `{imports/migraene_app/}*.mbu`, `(Migraine-App`, `Backup)`
- **Schreibt:** `health.db (sessions, session_metrics, assessments)`

## Grenzen

Keine Validierung der Migraine-App-Datenqualität. Keine medizinische Bewertung aus den Daten. HIT-6 und MIDAS sind validierte Fragebögen.

## Aufruf

```bash
python3 import_migraine.py           # all .mbu files
python3 import_migraine.py --update  # only neue Daten
```
