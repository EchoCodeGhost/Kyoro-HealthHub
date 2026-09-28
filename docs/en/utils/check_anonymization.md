# check_anonymization — Anonymisierungs-Compliance-Check für health.db

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/utils/check_anonymization.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Checks the health.db database for anonymization compliance. Identifies potential issues such as: real names in person_ids, GPS data with excessive precision (>5 decimal places), unpseudonymized device serial numbers and cleartext account information.

## Relevance

Provides verification functions for data quality and privacy, essential for data integrity

## Method

Uses functions from utils.anonymize (check_anonymization_compliance, print_compliance_report, get_all_device_mappings) for database checking. Can additionally check source code AND docs (.py/.md/.json, whole repo) for privacy violations (identifiers, hardcoding) by calling check_source_privacy.scan_directory. Supports different output modes: normal, JSON and device mappings display. Exit code: 0 = clean, 1 = issues found.

## Data flow

- **Reads:** `health.db`, `(alle`, `Tabellen)`, `identity.db.device_serial_map`
- **Writes:** `stdout (Berichte und JSON-Ausgabe)`

## Limitations

Only checks the database configured in health_config.json if --db not specified. Source code check may produce false positives (e.g., in t() calls).

## Usage

```bash
python scripts/utils/check_anonymization.py
python scripts/utils/check_anonymization.py --db /path/to/health.db
python scripts/utils/check_anonymization.py --show-mappings
python scripts/utils/check_anonymization.py --source-code --strict
python scripts/utils/check_anonymization.py --json
# --db: Pfad zur Datenbank angeben
# --show-mappings: Zeige alle Geräte-Pseudonymisierungs-Mappings
# --source-code: Prüfe zusätzlich Source-Code auf Privacy-Verstöße
# --strict: Wertet auch low-confidence Findings als Fehler
# --json: Ausgabe als JSON für automatische Verarbeitung
```
