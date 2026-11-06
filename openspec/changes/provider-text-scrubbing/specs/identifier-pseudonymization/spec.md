## MODIFIED Requirements

### Requirement: Central resolver module for all identifier pseudonyms
All resolution between real identifiers (device, person, provider, and
in future other locally-identifying values such as a Home Assistant
instance or weather station) and their pseudonyms SHALL go exclusively
through a single module (`scripts/modules/identity_resolver.py`). No
other script SHALL read or write `identity.db` or `registry.json`
directly for identity resolution — analogous to `modules/db.py` as the
sole DB access point.

#### Scenario: New code path needs a pseudonym resolution
- **WHEN** a script needs to know which pseudonym belongs to a real
  device, person, provider, or other locally-identifying value
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
`health.db`/`medicine.db` or in the git repository. `resolve()` and
`_generate_pseudonym()` SHALL accept `kind="provider"` in addition to
the existing `"device"` and `"person"` kinds, using the canonical
provider-registry key (from `scripts/modules/provider_scrubbing.py`) as
the real value — this is a purely additive branch; the existing
`"device"`/`"person"` code paths are unchanged.

#### Scenario: Repeated import of the same device
- **WHEN** the same real device identifier is resolved a second time
  (e.g. on a repeated import)
- **THEN** `identity_resolver.resolve()` returns exactly the same
  pseudonym as the first time, so that `INSERT OR IGNORE` deduplication
  keeps working

#### Scenario: Database export or repo commit
- **WHEN** `health.db`, `medicine.db`, or a file in the git repository
  is inspected
- **THEN** it contains no real device, person, or provider identifier
  anywhere, only pseudonyms

#### Scenario: Repeated resolution of the same provider
- **WHEN** the same canonical provider-registry key is resolved via
  `identity_resolver.resolve("provider", <key>)` a second time (e.g. the
  same doctor mentioned in two different imported documents)
- **THEN** it returns exactly the same pseudonym as the first time

#### Scenario: Unknown kind is still rejected
- **WHEN** `resolve()` or `_generate_pseudonym()` is called with a
  `kind` other than `"device"`, `"person"`, or `"provider"`
- **THEN** it raises `ValueError`, unchanged from the existing behavior
