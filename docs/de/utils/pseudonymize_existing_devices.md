# pseudonymize_existing_devices — Bestehende Geräte-Seriennummern in der Datenbank pseudonymisieren

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/utils/pseudonymize_existing_devices.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Findet alle Geräte ohne SN-Präfix in der Seriennummer und ersetzt sie durch Pseudonyme. Dieses Skript: 1) Findet alle Geräte ohne SN-Präfix, 2) Erstellt Pseudonyme und speichert sie in identity.db, 3) Aktualisiert die health.db mit den pseudonymisierten Seriennummern, 4) Erstellt ein Backup vor der Änderung.

## Relevanz

Bietet Hilfsfunktionen für die Datenverarbeitung, essentiell für die Systemfunktionalität

## Methode

Sucht in der devices-Tabelle nach Seriennummern ohne SN-Präfix. Nutzt pseudonymize_device_serial() und get_device_pseudo() aus utils.anonymize. Zeigt alle geplanten Änderungen vor der Ausführung an. Benötigt Benutzerbestätigung vor Ausführung (außer --dry-run). Erstellt Zeitstempel-basiertes Backup. Protokolliert in import_log. Exit-Code: 0 = Erfolg, 1 = Fehler.

## Datenfluss

- **Liest:** `health.db.devices`
- **Schreibt:** `health.db.devices, identity.db.device_serial_map, import_log, health.db.backup`

## Grenzen

Prüft nur Geräte mit nicht-leeren Seriennummern ohne SN-Präfix. Backup wird im selben Verzeichnis wie die Datenbank erstellt.

## Aufruf

```bash
python scripts/utils/pseudonymize_existing_devices.py
python scripts/utils/pseudonymize_existing_devices.py --db /path/to/health.db
python scripts/utils/pseudonymize_existing_devices.py --dry-run
# --db: Pfad zur Datenbank angeben
# --dry-run: Zeigt Änderungen ohne sie durchzuführen
```
