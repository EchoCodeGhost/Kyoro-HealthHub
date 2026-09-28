# migrate_health_to_medicine — Migration klinischer Daten von health.db nach medicine.db

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/utils/migrate_health_to_medicine.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Migriert klinische Tabellen von der health.db in die spezielle medicine.db. Betroffene Tabellen: lab_manual, lab_results, medications und assessments. Die Daten bleiben in health.db erhalten (kein Löschen).

## Relevanz

Bietet Migrationsfunktionen für Daten, essentiell für die Datenaktualisierung und -umstrukturierung

## Methode

Verwendet INSERT OR IGNORE für alle Tabellen, um Duplikate zu vermeiden und die Migration wiederholbar zu machen. Vor der Migration wird sichergestellt, dass das medicine.db-Schema existiert (Aufruf von create_medicine_schema). Unterstützt Dry-Run-Modus (--dry-run) zur Vorschau ohne Schreiboperationen. Spalten werden dynamisch aus der Quelltabelle extrahiert.

## Datenfluss

- **Liest:** `health.db.lab_manual`, `health.db.lab_results`, `health.db.medications`, `health.db.assessments`
- **Schreibt:** `medicine.db.lab_manual, medicine.db.lab_results, medicine.db.medications, medicine.db.assessments`

## Grenzen

Daten werden nicht aus health.db gelöscht - manuelles Löschen nach Verifikation erforderlich. Erfordert Zugriff auf beide Datenbanken (health.db und medicine.db). Dry-Run-Modus zeigt nur die Anzahl der zu migrierenden Zeilen an, ohne diese zu schreiben.

## Aufruf

```bash
python scripts/utils/migrate_health_to_medicine.py
python scripts/utils/migrate_health_to_medicine.py --dry-run
# Vorraussetzung: health.db und medicine.db müssen existieren
# --dry-run: Zeigt an, welche Daten migriert würden, ohne sie zu schreiben
```
