# post_import_sanitize — Automatische Post-Import PII-Bereinigung und Compliance-Check

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/utils/post_import_sanitize.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Wird automatisch von import_all.py und import_staged.py nach jedem erfolgreichen Import aufgerufen, damit die Datenbank jederzeit an Cloud-LLMs weitergegeben werden kann ohne PII zu leaken.

## Relevanz

Bietet Hilfsfunktionen für die Datenverarbeitung, essentiell für die Systemfunktionalität

## Methode

Führt drei Schritte nacheinander aus: 1. scrub_pii: Bereinigt bekannte PII-Muster in Text-Spalten 2. pseudonymize_devices: Ersetzt echte Seriennummern durch SN-Pseudonyme 3. check_anonymization: Prüft GPS-Präzision, Seriennummern, Person-IDs Kein Schritt blockiert - bei Fehlern wird nur eine Warnung ausgegeben. Protokolliert alle Änderungen in import_log.

## Datenfluss

- **Liest:** `health.db`, `(alle`, `Tabellen`, `für`, `PII-Prüfung)`
- **Schreibt:** `health.db (bereinigte Felder), import_log`

## Grenzen

Gibt nur Warnungen aus, bricht nie ab (nicht blockierend). Erstellt keine Backups (wird von den Import-Skripten verwaltet).

## Aufruf

```bash
# Wird automatisch von import_all.py und import_staged.py aufgerufen
from utils.post_import_sanitize import run
run()
# Oder direkt:
python -c "from utils.post_import_sanitize import run; run()"
```
