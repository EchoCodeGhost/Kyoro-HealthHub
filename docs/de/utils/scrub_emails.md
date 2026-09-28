# scrub_emails — E-Mail-Adressen in der Datenbank bereinigen

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/utils/scrub_emails.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Durchsucht die Datenbank nach E-Mail-Adressen und entfernt oder pseudonymisiert sie. Dieses Skript: 1) Durchsucht alle Textfelder nach E-Mail-Adressen, 2) Ersetzt sie durch Pseudonyme oder entfernt sie komplett, 3) Erstellt ein Backup vor der Änderung, 4) Protokolliert alle Änderungen.

## Relevanz

Bietet Funktionen zur Datenbereinigung und Anonymisierung, essentiell für den Datenschutz

## Methode

Durchsucht definierte Tabellen und Spalten (measurements.source_app, sessions.source_app, blood_pressure.source, devices.notes, persons.notes, import_log.error_detail) nach E-Mail-Mustern. Verwendet pseudonymize_email() aus utils.anonymize für Pseudonymisierung oder ersetzt durch [EMAIL-REMOVED] beim Entfernen. Erstellt Zeitstempel-basiertes Backup. Protokolliert in import_log. Benötigt Benutzerbestätigung vor Ausführung (außer --dry-run). Exit-Code: 0 = Erfolg, 1 = Fehler.

## Datenfluss

- **Liest:** `health.db`, `(definierte`, `Tabellen`, `und`, `Spalten)`
- **Schreibt:** `health.db (aktualisierte Felder), health.db.backup (Backup), import_log`

## Grenzen

Durchsucht nur definierte Tabellen/Spalten - andere Tabellen werden nicht geprüft. Backup wird im selben Verzeichnis wie die Datenbank erstellt.

## Aufruf

```bash
python scripts/utils/scrub_emails.py
python scripts/utils/scrub_emails.py --db /path/to/health.db
python scripts/utils/scrub_emails.py --dry-run
python scripts/utils/scrub_emails.py --remove
# --db: Pfad zur Datenbank angeben
# --dry-run: Zeigt Änderungen ohne sie durchzuführen
# --remove: Entfernt E-Mails komplett statt sie zu pseudonymisieren
```
