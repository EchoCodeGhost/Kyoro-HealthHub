# migrate_location_tables_to_location_db.py — Tracks, Aufenthalte und Standortverlauf von health.db nach location.db

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/migrations/migrate_location_tables_to_location_db.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Zieht session_tracks, location_stays, location_history und location_stays_geocoded aus health.db nach location.db um und entfernt sie danach aus health.db, damit dort keine Koordinaten zurückbleiben. Audit-Log-Einträge dieser Tabellen (sie enthalten Koordinaten) ziehen mit um.

## Relevanz

Stufe 3 des Ortsregisters: health.db enthält danach keine Tracks und Aufenthalte mehr

## Methode

Ablauf mit --execute: (1) Backup von health.db über die SQLite-Backup-Funktion (oder ein vorhandenes, angegebenes Backup, das auf Lesbarkeit und Zeilenzahlen geprüft wird); (2) Zeilen unverändert nach location.db kopieren (INSERT OR IGNORE, Spalten über Namen); (3) Abgleich: jede Zeile aus health.db muss identisch in location.db stehen (EXCEPT-Abfrage), dazu Zeilenzahlen und eine SHA-256-Prüfsumme über die sortierten Zeilen beider Seiten; (4) Audit-Log-Einträge der Tabellen nach location.db übertragen; (5) in einer Transaktion mit secure_delete: Einträge aus dem health.db-Audit-Log löschen, Tabellen löschen (photo_locations nur, wenn leer), ein Audit-Eintrag nur mit Anzahlen. Bricht vor jedem Löschen ab, wenn der Abgleich nicht stimmt. Erneut ausführbar.

## Datenfluss

- **Liest:** `health.db`, `(session_tracks`, `location_stays`, `location_history`, `location_stays_geocoded`, `photo_locations`, `audit_log)`, `location.db`
- **Schreibt:**

  ```
  location.db (dieselben Tabellen, audit_log), health.db (DROP TABLE,
  audit_log), data/backups/health.db.pre_location_migration_<Datum>.bak
  ```

## Grenzen

Standard ist ein Trockenlauf, der nur Anzahlen nennt, nie Koordinaten. Die Daten werden unverändert übernommen: keine Rundung, keine Privatsphäre-Zonen (dafür apply_privacy_zones.py). location.db darf vorher keine Aufenthalte enthalten, die nicht aus health.db stammen (ihre ids würden kollidieren).

## Aufruf

```bash
# Trockenlauf (Standard)
python3 scripts/migrations/migrate_location_tables_to_location_db.py
# Ausführen, mit neuem Backup
python3 scripts/migrations/migrate_location_tables_to_location_db.py --execute
# Ausführen mit vorhandenem Backup
python3 scripts/migrations/migrate_location_tables_to_location_db.py --execute \
    --backup data/backups/health.db.pre_location_stage3_<Datum>.bak
```
