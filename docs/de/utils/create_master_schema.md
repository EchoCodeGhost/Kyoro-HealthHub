# create_master_schema.py — Praxisweite Verwaltungsdatenbank erstellen/aktualisieren

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/utils/create_master_schema.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Erstellt oder migriert ~/.config/kyoro-master/master.db. Diese Datenbank hält betreiberweite Verwaltungsdaten (welche Patient:innen-Instanzen existieren, gemeinsam genutzte Praxisgeräte) — im Gegensatz zu identity.db, das pro Instanz existiert und Pseudonym-Zuordnungen für genau eine Person hält.

## Relevanz

Ermöglicht die Erstellung von Datenbank-Schemata, essentiell für die Datenorganisation und -struktur

## Methode

Tabellen: patient_number_map (Patientenregistratur), practice_devices (Geräte-Katalog).

## Datenfluss

- **Liest:** `~/.config/kyoro-master/master.db`
- **Schreibt:** `~/.config/kyoro-master/master.db`

## Grenzen

Einmalig aufrufen. Wiederholte Ausführung ist idempotent. Liegt IMMER im echten Betreiber-Home, folgt NIE KYORO_ACTIVE_PATIENT_DIR — sonst würde die Patientenliste selbst in einer Patienten-Instanz verschwinden.

## Aufruf

```bash
python -m utils.create_master_schema
python3 scripts/utils/create_master_schema.py  # from repo root
```
