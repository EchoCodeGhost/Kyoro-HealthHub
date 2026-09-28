## ADDED Requirements

### Requirement: Hash-chained audit log
Every new entry in `import_log` SHALL store a hash computed from the
hash of the previous entry and its own payload
(`sha256(prev_hash || own_payload)`).

#### Scenario: A new log entry is written
- **WHEN** an importer/compute script writes a new `import_log` entry
- **THEN** `entry_hash` is computed from `prev_hash` (the hash of the
  previous entry) and its own payload, and stored

#### Scenario: A historical entry is changed after the fact
- **WHEN** a historical `import_log` entry is changed after the fact
  (value, timestamp, etc.)
- **THEN** its stored `entry_hash` no longer matches the newly computed
  hash, and the verification function MUST detect and report this
  discrepancy

### Requirement: External anchoring is opt-in
External anchoring of the chain endpoint SHALL be disabled by default
and SHALL only become active after explicit configuration by the user.

#### Scenario: Default installation without configuration
- **WHEN** Kyoro-HealthHub runs without explicit anchor configuration
- **THEN** no external network communication for anchoring purposes
  takes place — the hash chain is kept exclusively locally

#### Scenario: User enables external anchoring
- **WHEN** the user sets `clinical.audit_anchor.enabled = true` and
  configures at least one method in `clinical.audit_anchor.methods`
- **THEN** anchoring is only performed via the explicitly configured
  methods, never via an unconfigured method

### Requirement: Multiple anchor methods possible simultaneously
The configuration SHALL allow enabling OpenTimestamps and Ethereum
simultaneously as independent, parallel anchors — the methods are not
exclusive to each other.

#### Scenario: Both methods enabled
- **WHEN** `clinical.audit_anchor.methods` contains both
  `opentimestamps` and `ethereum`
- **THEN** the current chain-endpoint hash is anchored independently via
  both methods, and both receipts (OTS file, Ethereum transaction ID)
  are stored locally

### Requirement: Ethereum requires an explicit cost warning
Before the first activation of Ethereum anchoring, the user SHALL be
shown an explicit notice about volatile, recurring gas costs.

#### Scenario: First activation of Ethereum as an anchor method
- **WHEN** the user adds `ethereum` to
  `clinical.audit_anchor.methods` for the first time
- **THEN** a warning about cost/wallet requirements MUST be shown before
  the first anchoring takes place

### Requirement: Verification tool
A script SHALL exist that checks the local hash chain against itself
and (if present) against the last external anchor.

#### Scenario: Verification without a discrepancy
- **WHEN** the local chain is consistent and matches the last external
  anchor
- **THEN** the verification tool reports "consistent up to row N,
  anchored on date X via method Y"

#### Scenario: Verification with a discrepancy
- **WHEN** a break is found in the local chain
- **THEN** the tool reports the exact row from which the chain no
  longer matches the last known external anchor
