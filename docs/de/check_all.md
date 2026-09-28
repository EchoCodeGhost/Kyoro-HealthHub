# Umfassender Privacy- und Anonymisierungs-Check

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/check_all.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Führt umfassende Privacy- und Anonymisierungs-Checks aus

## Relevanz

Bietet Gesundheitsdatenfunktionen, essentiell für die medizinische Datenverarbeitung

## Methode

Führt nacheinander drei Checks aus: 1. Quellcode- und Doku-Check mit check_source_privacy.py (.py/.md/.json, ganzes Repo) 2. Datenbank-Anonymisierungs-Check mit check_anonymization.py 3. PII-Scan mit scrub_pii.py --dry-run Zeigt standardmäßig nur Ergebnisse an. Mit --fix werden PII tatsächlich bereinigt (mit Backup).

## Datenfluss

- **Liest:** `Alle`, `Quellcode-Dateien`, `und`, `Datenbanktabellen`
- **Schreibt:** `PII-Bereinigte Dateien (nur mit --fix)`

## Grenzen

Keine direkte Validierung. Abhängig von den einzelnen Check-Skripten.

## Aufruf

```bash
python3 scripts/check_all.py
python3 scripts/check_all.py --skip-db       # nur Quellcode
python3 scripts/check_all.py --skip-source   # nur DB + PII
python3 scripts/check_all.py --fix           # PII tatsächlich bereinigen (mit Backup)
```
