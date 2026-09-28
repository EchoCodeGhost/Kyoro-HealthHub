# scrub_pii — Umfassende PII-Bereinigung für health.db

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/utils/scrub_pii.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Durchsucht die Datenbank nach persönlich identifizierbaren Informationen (PII) und pseudonymisiert oder entfernt sie. PII-Kategorien: E-Mail-Adressen, Telefonnummern, IP-Adressen, Versicherungsnummern, Krankenkassen-Namen, Geburtsdaten, vollständige Namen, Adressen, Stadtnamen.

## Relevanz

Bietet Funktionen zur Datenbereinigung und Anonymisierung, essentiell für den Datenschutz

## Methode

Durchsucht definierte Tabellen/Spalten nach diversen PII-Mustern. Verwendet scrub_sensitive_health_data() aus utils.anonymize. Erstellt Rolling-Backup (wird bei jedem Lauf überschrieben). Unterstützt Modi: Pseudonymisierung (Standard) oder komplett Entfernen (--remove-all). Kann automatisch ohne Prompt laufen (--auto). Protokolliert in import_log. Exit-Code: 0 = Erfolg, 1 = Fehler.

## Datenfluss

- **Liest:** `health.db`, `(measurements`, `sessions`, `blood_pressure`, `devices`, `persons)`
- **Schreibt:** `health.db (aktualisierte Felder), health.db.pii_scrub_backup (Rolling-Backup), import_log`

## Grenzen

Durchsucht nur definierte Tabellen/Spalten. Überspringt bereits pseudonymisierte Felder. Rolling-Backup überschreibt vorheriges Backup. Skippt sehr kurze Texte (<10 Zeichen). Enthält explizit KEINE medizinischen Diagnosen, demografische Daten oder Orte in den Docstrings.

## Aufruf

```bash
python scripts/utils/scrub_pii.py
python scripts/utils/scrub_pii.py --db /path/to/health.db
python scripts/utils/scrub_pii.py --dry-run
python scripts/utils/scrub_pii.py --remove-all
python scripts/utils/scrub_pii.py --auto --no-backup
# --db: Pfad zur Datenbank angeben
# --dry-run: Zeigt Änderungen ohne sie durchzuführen
# --remove-all: Entfernt alle PII komplett
# --auto: Kein interaktives Prompt
# --no-backup: Kein Backup erstellen
```
