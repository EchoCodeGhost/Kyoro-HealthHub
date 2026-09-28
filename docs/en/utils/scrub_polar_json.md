# scrub_polar_json — PII aus Polar JSON-Rohdaten entfernen

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/utils/scrub_polar_json.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Cleans Polar JSON raw files in imports/polar/ directory from personally identifiable information. Replaces: real device serials with pseudo IDs (SN-XXXXXXXX), Polar account owner IDs with pseudo UIDs (UID-XXXXXXXX). Removes: name/email from account-data files, sensitive data from fitness-test. Renames filenames containing the real owner ID.

## Relevance

Provides data cleaning and anonymization functions, essential for data privacy

## Method

Loads pseudonymization mappings from identity.db (device_serial_map and account_pseudo_map). Processes all JSON files in Polar directory recursively. Replaces values recursively in the JSON structure. Removes specific fields (account-data username/firstName/ lastName/email, sensitive fitness-test fields). Renames files containing real IDs. Idempotent: already pseudonymized values remain unchanged. Dry-run mode available.

## Data flow

- **Reads:** `imports/polar/*.json`, `identity.db.device_serial_map`, `identity.db.account_pseudo_map`
- **Writes:** `imports/polar/*.json (bereinigte Dateien und umbenannte Dateinamen)`

## Limitations

Only processes JSON files in the specified Polar directory. Only replaces values found in the mappings.

## Usage

```bash
python -m utils.scrub_polar_json
python -m utils.scrub_polar_json --dry-run
python -m utils.scrub_polar_json --polar-dir /path/to/polar
# --dry-run: Zeigt Änderungen ohne sie durchzuführen
# --polar-dir: Pfad zum Polar-Import-Verzeichnis angeben
# Standard: imports/polar/
```
