# identifier-pseudonymization Specification

## Purpose
Documents how Kyoro-HealthHub keeps device and person identifiers out of
`health.db`/`medicine.db` and the public repository: a single resolver
module maps real-world identifiers (device serials, person/relationship
names, and future local-identifying values) to deterministic, locally
stored pseudonyms, so no human-readable identifier ever reaches stored
data or code that could be shared or inspected by an external tool.

## Requirements
### Requirement: Central resolver module for all identifier pseudonyms
All resolution between real identifiers (device, person, and in future
other locally-identifying values such as a Home Assistant instance or
weather station) and their pseudonyms SHALL go exclusively through a
single module (`scripts/modules/identity_resolver.py`). No other script
SHALL read or write `identity.db` or `registry.json` directly for
identity resolution — analogous to `modules/db.py` as the sole DB access
point.

#### Scenario: New code path needs a pseudonym resolution
- **WHEN** a script needs to know which pseudonym belongs to a real
  device, person, or other locally-identifying value
- **THEN** it calls `identity_resolver.resolve(kind, real_value)`
  instead of writing its own query against `identity.db`/`registry.json`

#### Scenario: Code review finds scattered identity-DB access
- **WHEN** a code review finds a script that opens `identity.db` or
  `registry.json` directly outside of `identity_resolver.py`
- **THEN** this counts as a convention violation that MUST be fixed
  before merge

### Requirement: Pseudonyms are deterministic and stored locally
Pseudonyms SHALL be derived deterministically from the real value
(SHA-256-based, analogous to `pseudonymize_device_serial()`), so that
repeated resolution of the same real value always yields the same
pseudonym. The mapping between real value and pseudonym SHALL be stored
exclusively locally (`~/.config/kyoro/identity.db`), never in
`health.db`/`medicine.db` or in the git repository.

#### Scenario: Repeated import of the same device
- **WHEN** the same real device identifier is resolved a second time
  (e.g. on a repeated import)
- **THEN** `identity_resolver.resolve()` returns exactly the same
  pseudonym as the first time, so that `INSERT OR IGNORE` deduplication
  keeps working

#### Scenario: Database export or repo commit
- **WHEN** `health.db`, `medicine.db`, or a file in the git repository
  is inspected
- **THEN** it contains no real device or person identifier anywhere,
  only pseudonyms

### Requirement: Device-type routing via `sensor_type`, not via the device pseudonym
Code that previously distinguished between device types based on the
semantic device identifier (e.g. chest-strap ECG vs. optical wrist PPG
for algorithm selection) SHALL instead distinguish via `sensor_type`
from the `device_registry` lookup, resolved through `identity_resolver`.
The pseudonym itself SHALL NOT allow any inference about the device
type.

#### Scenario: Arrhythmia algorithm selection
- **WHEN** a compute script needs to decide which heart-rhythm algorithm
  fits a `ppi_raw` row
- **THEN** it resolves the device pseudonym via `identity_resolver` to
  `sensor_type` and chooses the algorithm based on `sensor_type`, not
  based on a hardcoded device-pseudonym comparison
