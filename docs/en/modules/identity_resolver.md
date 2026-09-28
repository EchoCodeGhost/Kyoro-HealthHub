# identity_resolver.py — Zentrales Identifier-Pseudonym-Resolver-Modul

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/modules/identity_resolver.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Centralized pseudonym resolution for device and person identifiers. Extends the existing serial-number pseudonymization pattern to cover device_id and person. Single access point for all identity resolution.

## Relevance

Provides identity resolution functions, essential for data integration

## Method

Deterministic SHA-256-based pseudonym generation with prefixes: - DEV-XXXXXXXX for device IDs - PER-XXXXXXXX for person IDs The hash is combined with a random, once-generated salt stored locally in identity.db (salt:kind:real_value). Without a salt, device_id/person would be vulnerable to a dictionary attack: both columns have extremely low cardinality (a few dozen known device model strings, 'self'/'partner'), so an unsalted hash could be broken by anyone with access to health.db (explicitly including a remote-connected AI tool, see proposal.md) simply by trying every known candidate value — exactly the threat this change is meant to prevent. Stores mappings in ~/.config/kyoro/identity.db and provides forward (real→pseudo) and reverse (pseudo→real) resolution plus human-readable display names for reports.

## Data flow

- **Reads:** `~/.config/kyoro/identity.db`, `(device_id_map`, `person_map`, `device_serial_map)`, `~/.config/kyoro/registry.json`, `(für`, `sensor_type`, `Lookup`, `in`, `resolve_display_name)`
- **Writes:** `~/.config/kyoro/identity.db (neue Einträge in device_id_map, person_map)`

## Limitations

Local-only resolution; no network access. Pseudonyms are deterministic but not cryptographically secure — designed for privacy, not security.

## Usage

```bash
from modules.identity_resolver import resolve_device, resolve_person, reverse_resolve, resolve_display_name
dev_pseudo = resolve_device("polar_v3")  # -> "DEV-8abb425f"
person_pseudo = resolve_person("self")   # -> "PER-6173fec1"
real_value = reverse_resolve(dev_pseudo) # -> "polar_v3"
display_name = resolve_display_name(dev_pseudo) # -> "polar_v3 (optical_wrist_gps)"
```
