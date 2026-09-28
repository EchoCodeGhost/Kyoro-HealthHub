# PII Anonymization Infrastructure - Documentation

> **Deutsche Version:** [PII_Anonymization_DE.md](PII_Anonymization_DE.md)

## Overview

This document describes the PII (Personally Identifiable Information) anonymization infrastructure for health data. The infrastructure provides tools and functions to detect, pseudonymize, and remove sensitive personal data from health databases.

### Scope vs. other privacy tools

This infrastructure deals with PII in **database content** (free text from imported documents, names/addresses/contact details). Two separate, equally central tools cover other layers and are not part of this document:

- **`scripts/utils/check_source_privacy.py`** checks the repo's **source code** (not the database) for forbidden identifier fragments from `privacy_check.forbidden_identifiers` — enforces the rules in [`PRIVACY_ARCHITECTURE.md`](PRIVACY_ARCHITECTURE.md) and CLAUDE.md § "Privacy rules". Required before every merge (`check_anonymization.py --source-only` invokes the same mechanism from that file).
- **`scripts/check_compliance.py`** maintains a review queue for newly detected violations (see `compliance_baseline.json`) — part of the pre-PR checks described in `docs/CONTRIBUTING.md`.
- Device/person pseudonymization itself (`DEV-XXXXXXXX`/`PER-XXXXXXXX`, the `identity_resolver` module, DB triggers) is documented in [`PRIVACY_ARCHITECTURE.md`](PRIVACY_ARCHITECTURE.md) — `pseudonymize_existing_devices.py` (below) is a migration tool for legacy data within that system, not a separate architecture.

## Architecture

### Core modules

1. **`utils/anonymize.py`** - Core pseudonymization functions
2. **`utils/check_anonymization.py`** - Compliance checking
3. **`utils/scrub_pii.py`** - Comprehensive PII scrubbing
4. **`utils/scrub_emails.py`** - Email-specific scrubbing
5. **`utils/pseudonymize_existing_devices.py`** - Device pseudonymization

### Data flow

```
Health data → [Compliance check] → [PII detection] → [Pseudonymization] → Anonymized data
                       ↑
                   [Backup]
                       ↑
                   [Logging]
```

## PII categories

### Detected and pseudonymized

| Category | Examples | Pseudonymization pattern |
|-----------|----------|------------------------|
| **Email addresses** | `max.mustermann@example.com` | `user-XXXXXX@example.com` |
| **Phone numbers** | `089/12345678` | `[TELEFON-XXXXXX]` |
| **Fax numbers** | `Fax: 030-98765432` | `Fax: [FAX-XXXXXX]` |
| **IP addresses** | `192.168.1.1` | `[IP-ENTFERNT]` |
| **Full names** | `Max Mustermann` | `[NAME-ENTFERNT]` |
| **First names** | `Max`, `Sandra` | `Vorname-XXXXXX` |
| **Last names** | `Müller`, `Schmidt` | `Nachname-XXXXXX` |
| **Doctor titles + names** | `Dr. med. Müller` | `Arzt-XXXXXX` |
| **Medical center names** | `MVZ München` | `MVZ-XXXXXX` |
| **Postal codes** | `80331` | `PLZ-XXXXX` |
| **Street names** | `Hauptstraße` | `[STRASSE-ENTFERNT]` |
| **City names** | `München` | `[STADT-ENTFERNT]` |
| **Insurance numbers** | `123456789` | `INS-XXXXXX` |
| **Health insurers** | `AOK`, `TK` | `Krankenkasse` |
| **Birth dates** | `15.05.1985` | `Alter: 38` |

### Preserved (not pseudonymized)

- **Gender**: `männlich`, `weiblich`, `divers`
- **Age**: `38 Jahre`
- **Emergency numbers**: `112`
- **Medically relevant information**

## Tools and their usage

### 1. Compliance check

**Purpose**: Checks the database for PII violations

**Usage**:
```bash
python3 scripts/utils/check_anonymization.py
```

**Options**:
- `--db PATH`: Path to the database
- `--show-mappings`: Shows device pseudonymization mappings
- `--json`: JSON output for automated processing

**Example output**:
```
=== Anonymisierungs-Compliance-Bericht ===
✅ Keine Probleme gefunden - Alle Daten sind korrekt anonymisiert!

⚠️  5 potenzielle Probleme gefunden:
  🚫 E-Mail-Adressen gefunden: 2
  🚫 Versicherungsdaten gefunden: 1
  🚫 Geburtsdaten gefunden: 3
  🚫 Nicht-pseudonymisierte Geräte: 1
  🚫 GPS mit hoher Präzision: 42277
```

### 2. Comprehensive PII scrubbing

**Purpose**: Pseudonymizes all PII data in the database

**Usage**:
```bash
python3 scripts/utils/scrub_pii.py [--dry-run] [--remove-all]
```

**Options**:
- `--dry-run`: Shows changes without applying them
- `--remove-all`: Removes PII completely (no pseudonymization)

**Example**:
```bash
# Dry run (safe test)
python3 scripts/utils/scrub_pii.py --dry-run

# Actual scrubbing
python3 scripts/utils/scrub_pii.py
```

### 3. Email scrubbing

**Purpose**: Specific to email addresses

**Usage**:
```bash
python3 scripts/utils/scrub_emails.py [--dry-run] [--remove]
```

### 4. Device pseudonymization

**Purpose**: Pseudonymizes device serial numbers

**Usage**:
```bash
python3 scripts/utils/pseudonymize_existing_devices.py [--dry-run]
```

### 5. GPS precision reduction

**Purpose**: Retroactively rounds overly precise GPS points in `session_tracks` (>5 decimal places)
down to 5 decimal places (~1.1 m grid) — for legacy data imported before automatic
rounding was introduced. New track imports already round on write
via `round_coords()` from `utils/anonymize.py` (see `import_tracks.py`).

**Usage**:
```bash
python3 scripts/utils/reduce_gps_precision.py --dry-run
python3 scripts/utils/reduce_gps_precision.py
```

## Pseudonymization functions

### Individual functions

```python
from utils.anonymize import (
    pseudonymize_email,
    pseudonymize_first_name,
    pseudonymize_last_name,
    pseudonymize_arzt_name,
    pseudonymize_mvz_name,
    pseudonymize_zip_code,
    pseudonymize_insurance_number,
    pseudonymize_birthdate
)

# Examples
print(pseudonymize_email("max@example.com"))  # user-ABC123@example.com
print(pseudonymize_first_name("Max"))        # Vorname-ABC123
print(pseudonymize_last_name("Müller"))      # Nachname-ABC123
print(pseudonymize_arzt_name("Dr. Müller"))  # Arzt-ABC123
print(pseudonymize_mvz_name("MVZ München")) # MVZ-ABC123
print(pseudonymize_zip_code("80331"))        # PLZ-ABC12
print(pseudonymize_insurance_number("123456789")) # INS-ABC123
print(pseudonymize_birthdate("15.05.1985"))  # Alter: 38
```

## Best practices

### 1. Regular compliance checks

Run a compliance check after every data import:
```bash
python3 scripts/utils/check_anonymization.py
```

### 2. Backup before changes

All scrubbing tools automatically create backups. Keep these for audit purposes.

### 3. Dry run for new tools

Always test new tools in dry-run mode first:
```bash
python3 scripts/utils/scrub_pii.py --dry-run
```

### 4. Preserve gender and age

Always use `preserve_gender_age=True` to keep medically relevant information:
```python
scrub_sensitive_health_data(text, preserve_gender_age=True)
```

### 5. Logging

All changes are automatically logged in the `import_log` table.

## Privacy concept

### Pseudonymization strategy

- **Deterministic**: Same input → same pseudonym (SHA-256)
- **Consistent**: Across all tools and imports
- **Irreversible**: No way back to the original data
- **Auditable**: All changes are logged

### Data categories

| Category | Strategy | Example |
|-----------|-----------|----------|
| **Identifying data** | Full pseudonymization | Names, addresses, phone numbers |
| **Medically relevant** | Preserved | Gender, age, diagnoses |
| **Technical data** | Partial pseudonymization | Device serial numbers (SN-XXXX) |
| **Geodata** | Precision reduction | GPS to ~1m, postal code to city level |

### Compliance

- **GDPR**: Article 25 (data protection by design)
- **BDSG** (German Federal Data Protection Act): §§ 64 ff. (pseudonymization)
- **Hospital laws**: State-level (Germany) requirements
- **ISO 27001**: Information security management

## Troubleshooting

### Common issues

**Problem**: False positives on names
**Solution**: Adjust the `get_common_german_first_names()` and `get_common_german_last_names()` lists

**Problem**: Phone numbers not detected
**Solution**: Use the format `Tel: 089/12345678` or `Telefon: 089-12345678`

**Problem**: Email addresses inside JSON data
**Solution**: Parse the JSON first, then scrub the text fields

### Debugging

```python
# Test detailed PII detection
from utils.scrub_pii import find_pii_in_database
from modules.db import open_db

conn = open_db()
pii_data = find_pii_in_database(conn)
for item in pii_data:
    print(f"Table: {item[0]}.{item[1]}, Types: {item[4]}, Text: {item[3]}")
conn.close()
```

## Maintenance

### Updating lists

Extend the lists in `utils/anonymize.py`:

```python
def get_common_german_first_names() -> list[str]:
    return [
        # Current list
        'Max', 'Leon', 'Ben',  # Add new names
    ]
```

### Adding new PII categories

1. Create a new pseudonymization function
2. Add a pattern in `scrub_pii.py`
3. Extend the compliance check in `check_anonymization.py`

## Example workflows

### Workflow 1: Importing new data

```bash
# 1. Import data (e.g. Garmin)
python3 scripts/importers/import_garmin.py

# 2. Check compliance
python3 scripts/utils/check_anonymization.py

# 3. Scrub if issues were found
python3 scripts/utils/scrub_pii.py

# 4. Check again
python3 scripts/utils/check_anonymization.py
```

### Workflow 2: Cleaning up existing data

```bash
# 1. Check compliance status
python3 scripts/utils/check_anonymization.py

# 2. Specific tools for issues found:
#    - GPS: python3 scripts/utils/reduce_gps_precision.py
#    - Devices: python3 scripts/utils/pseudonymize_existing_devices.py
#    - Emails: python3 scripts/utils/scrub_emails.py
#    - All PII: python3 scripts/utils/scrub_pii.py

# 3. Final check
python3 scripts/utils/check_anonymization.py
```

## Summary

This documentation describes the PII anonymization infrastructure, which:

- ✅ Detects and pseudonymizes **all PII categories**
- ✅ Preserves **medically relevant data** (gender, age)
- ✅ Provides **deterministic pseudonymization** for consistency
- ✅ Provides **compliance checks** for regular review
- ✅ Includes **secure tools** with backup and logging

The infrastructure covers this layer of data protection for health data; it complements — but does not replace — the source-code privacy checks and device/person pseudonymization architecture described above.
