# anonymize — Zentrale Anonymisierungs- und Pseudonymisierungs-Hilfsfunktionen

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/utils/anonymize.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Central module for all anonymization and pseudonymization helper functions. All functions that touch externally transmitted or stored location/identity data should go through this module to have a single place to adjust precision or scrubbing rules.

## Relevance

Enables anonymization of health data, essential for data privacy and compliance requirements

## Method

Provides functions for: GPS coordinate rounding (default: 2 decimal places ≈ 1.1km grid), device serial number pseudonymization (SN-XXXXXXXX format with SHA-256 hash in identity.db), email address replacement, phone/fax number detection and pseudonymization, insurance number and name pseudonymization, birthdate replacement, name pseudonymization (first name, last name), address and city name replacement, database compliance checks, Apple Health sourceName scrubbing and HealthKit <Me> attribute scrubbing. Stores all pseudonymizations in a separate identity.db for consistency.

## Data flow

- **Reads:** `identity.db.device_serial_map`
- **Writes:** `identity.db.device_serial_map`

## Limitations

GPS precision limited to 2 decimal places (approx. 1.1km accuracy) - can be adjusted if needed. Pseudonymization is deterministic (same input → same output) but not reversible. Identity database (identity.db) is created with restrictive permissions (600). Compliance checks may produce false positives requiring manual review.

## Usage

```bash
from utils.anonymize import round_coords, pseudonymize_device_serial, scrub_text_field
from utils.anonymize import check_anonymization_compliance, print_compliance_report
# GPS-Koordinaten rundet
lat_rounded, lon_rounded = round_coords(52.5200, 13.4050)
# Geräte-Seriennummer pseudonymisieren
pseudo = pseudonymize_device_serial('ABC123XYZ', 'polar_m430')
# Compliance-Check durchführen
issues = check_anonymization_compliance('data/health.db')
print_compliance_report(issues)
```
