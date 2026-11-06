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
| **First names** | `Max`, `Erika` | `Vorname-XXXXXX` |
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

### 4b. Media scrubber (images and PDFs, local)

**Purpose**: Reports and removes metadata (EXIF incl. GPS, PDF info/XMP, attachments,
JavaScript) and blacks out postal addresses in the visible content of images and PDFs.
Originals are never overwritten.

**Usage**:
```bash
python -m utils.scrub_media report befund.pdf foto.jpg [--show-values] [--json-out report.json]
python -m utils.scrub_media scrub befund.pdf sauber.pdf [--address "Musterstraße 12, 12345 Musterstadt"]
python -m utils.scrub_media scrub-dir eingang/ ausgang/ --strict
python -m utils.scrub_media check ordner/
```

Address and name detection is heuristic (`modules/address_redaction.py`, `modules/name_redaction.py`).
Names are caught with salutation/title (`Frau X`, `Dr. med. X`), field labels (`Name:`) or from the
known names: `privacy_check.patient_names` in `health_config.json`, `person_name_map` in
`identity.db` and `--name`. Known addresses go under `privacy_check.patient_addresses`.
Phone/fax numbers (including short extensions), insurance numbers (health and pension insurance),
bank details (IBAN checked via its check digits, BIC, account number) and ID numbers of other
systems (patient, case, order, insurer and physician numbers, plus any unbroken digit sequence of 7
to 15 digits without a unit) are removed as well (`modules/identifier_redaction.py`). Use `--no-redact-names`, `--no-redact-addresses` or
`--no-redact-ids` to switch any of them off.

GPS coordinates in text (decimal degrees, degrees/minutes/seconds) and **personal place names** are
removed too (`modules/location_redaction.py`, `--no-redact-places`). Place names come only from your
local configuration: `privacy_check.patient_places` in `health_config.json`, the town in
`privacy_check.patient_addresses` and `--place`. There is deliberately no general town list, so
states, countries, travel destinations and endemic regions stay available for the analysis.
Coordinates in image metadata are removed by the metadata scrubbing as before; the rounded
`photo_locations` entries written by the importers are unchanged. Scans are checked
via OCR (optional: `pytesseract` + `tesseract` with language `deu`; text layer and rendering
need `poppler`). Affected PDF pages are replaced by image pages so no text layer remains. The
lab and FibriCheck PDF importers use the same function and fall back to metadata-only removal
with a warning when the tools are missing.

### 4c. Practice and laboratory pseudonymization

`post_import_sanitize` also runs `utils/pseudonymize_providers.py`: practice and lab names
(e.g. `lab_manual.labor`) become stable pseudonyms (`Labor-1A2B3C4D`); the mapping lives only
in `identity.db` (`provider_pseudonym_map`). Postal addresses are removed from lab free text.
Dry run: `python -m utils.pseudonymize_providers --dry-run`.

### 5. GPS precision reduction

**Purpose**: Retroactively rounds overly precise GPS points in `location.db::session_tracks`
(>5 decimal places) down to 5 decimal places (~1.1 m grid) — for legacy data imported
before automatic rounding was introduced. New track imports already round on write
via `location_store.store_track_points()` (see section 5c).

**Usage**:
```bash
python3 scripts/utils/reduce_gps_precision.py --dry-run
python3 scripts/utils/reduce_gps_precision.py
```

### 5b. Location privacy and outbound coarsening

**Purpose**: Controls the precision of location data sent to external services and
stores region information for local-first analysis.

Kyoro-HealthHub uses `location_privacy.json` to configure how location data is handled:

- **`external_api.precision`**: Default precision for coordinates sent to external
  services (default: 1 decimal place, ~11 km grid). Lower values = coarser precision.
- **`external_api.place_precision`**: Precision for place-name reverse geocoding
  (default: 2 decimal places, ~1 km). Used when `place=True` is passed to
  `for_external_api()`.
- **`external_api.services`**: Opt-in flags for services that require API keys.
  Currently: `google_pollen` (default: `false`). Must be explicitly enabled to send
  location data to Google.

**Region storage**: Locations are stored with ISO 3166-2 region codes (worldwide)
via `region_of()` from `location_store.py`. For units smaller than the stored precision
cell, only the country code is stored. This enables local-first analysis without
sending coordinates to external services.

**Configuration file**: `~/.config/kyoro/location_privacy.json` (created from
`templates/location_privacy.example.json` by `onboard.py`).

**Example configuration**:
```json
{
  "external_api": {
    "precision": 1,
    "place_precision": 2,
    "services": {
      "google_pollen": false
    }
  }
}
```

### 5c. Location registry and remote providers

**Purpose**: Keeps locations that importers find (for example GPS tags in
photos) in one place, at a precision you choose per importer, and controls
which locations may reach a remote LLM provider or an export.

**Location registry (`location.db`)**: Importers write locations through
`location_store.record()` into the table `location_registry` in
`data/location.db` (path: `paths.location_db`). The database is encrypted
with SQLCipher like `health.db` when `db_key` is set. Each entry holds the
importer and file type, the relative source file, the SHA-256 hash of the
original file (before metadata stripping) and of the stored file (after
stripping), date, the rounded coordinates, the applied precision, the
ISO 3166 region, a reference to the record it belongs to (for example an
`imaging_files` row) and the person pseudonym. Precision is applied before
writing and cannot be undone. Duplicates are skipped (`INSERT OR IGNORE`).
Photo locations no longer go to `health.db::photo_locations`; existing rows
can be moved with `scripts/migrations/migrate_photo_locations_to_registry.py`
(`--dry-run` first).

Sport tracks, stays and location history (`session_tracks`,
`location_stays`, `location_stays_geocoded`, `location_history`) are tables
in `location.db` as well. Importers write them through
`location_store.store_track_points()`, `store_stays()` and
`store_location_history()`, which apply the policy and the privacy zones.
Scripts that join them with `health.db` tables attach `location.db` as
`loc` (`modules.db.attach_location_db()`) and query `loc.session_tracks`
and so on. Installations that still have these tables in `health.db` move
them with `scripts/migrations/migrate_location_tables_to_location_db.py`:
dry run by default; `--execute` makes a backup (or checks one given with
`--backup`), copies the rows unchanged, verifies every row and a checksum,
moves the audit-log copies of these rows (they contain coordinates) and only
then drops the tables from `health.db`. `scripts/utils/check_location_columns.py`
confirms that `health.db` and `medicine.db` hold no personal coordinates;
the exceptions are environment tables keyed by the coarsened query point
(at most 2 decimal places) and outbreak reports (public places).

**Policy per importer and file type** (`importers` and `default` in
`location_privacy.json`): the policy resolves in the order importer + file
type → importer `"*"` → `default`. A policy is one of:

- `precision` 0–5: decimal places of latitude/longitude (0 ≈ 111 km,
  1 ≈ 11 km, 2 ≈ 1.1 km, 3 ≈ 110 m, 4 ≈ 11 m, 5 ≈ 1 m)
- `store: "region"`: only the ISO 3166 region, no coordinates
- `store: "none"`: nothing is stored

Importers without an entry, and a missing `location_privacy.json`, store no
location. A photo location is only stored with a real capture date (EXIF
date or `--date`).

**Privacy zones** (`zones`), like Strava: with `enabled` true, points
within `radius_m` (default 500 m) of a zone are not stored
(`inside: "hide"`, default) or stored at `zone_precision` (`"coarsen"`).
This applies only to importers whose precision is finer than
`zone_precision` (default 2, about 1 km). Zone centres are the home position
(`location.lat`/`lon` in `health_config.json`) and the entries in
`zones.centres` (coordinates per place name: a place from
`privacy_check.patient_places` by its name, an address from
`privacy_check.patient_addresses` by the full address or its town). Each
centre is shifted by a fixed offset of up to half the radius, computed from
the salt in `identity.db`, so that the edge where tracks are cut does not
reveal the place; the true centre always stays inside the zone. Configured
places without an entry get no zone; each run reports how many, without
names. There is no online geocoding, and zone centres are never stored.
Zones can be applied to entries stored before a zone existed with
`scripts/migrations/apply_privacy_zones.py`: registry entries and track
points inside a zone are deleted (or coarsened with `"coarsen"`), stays and
location history are only coarsened, never deleted, so that residence
periods and home detection keep working (dry run by default, `--execute`
to apply; irreversible, no coordinates copied into the audit log).

**Remote LLM providers** (`llm`): before a prompt goes to a remote provider
(`is_local` false), `modules/llm.py::call_llm` passes prompt and system text
through `location_store.filter_prompt_text()`. The level comes from
`llm.allow` for the calling script (the script name without `.py`, or an
explicit `caller=`), otherwise from `llm.default` (`none`):

| Level | Coordinates in the text | Configured place names |
|---|---|---|
| `none` (default) | removed | removed |
| `region` | removed | removed |
| N (0–5) | rounded to N decimal places | removed |
| `token` | replaced by a location token | removed |

The location token is an HMAC of the grid cell with the salt from
`identity.db`; without a salt there is no token and coordinates are removed.
Scripts that need location data in a prompt read it through
`location_store.for_prompt()`, which applies the same allowlist. Images are
re-encoded without metadata before they are sent to a remote provider; if
an image cannot be cleaned, it is not sent. Local providers are not
filtered.

**Exports** (`exports.allow`): `export_health.py` removes location columns
unless the export profile is listed in `exports.allow` with a level
(`region` or a precision).

**Example**:
```json
{
  "default": {"store": "none"},
  "importers": {
    "import_skin": {"*": {"precision": 2}},
    "import_lab_results": {"*": {"store": "none"}}
  },
  "llm": {"default": "none", "allow": {"analyse_travel": "region"}},
  "exports": {"allow": {"travel_analysis": "region"}}
}
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
