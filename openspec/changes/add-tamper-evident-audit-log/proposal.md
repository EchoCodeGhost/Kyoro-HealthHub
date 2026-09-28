## Why

Kyoro-HealthHub aims to be court-admissible. The existing `import_log`
table logs import runs, but without cryptographic chaining: any row can
be altered or deleted after the fact without the system itself being
able to detect it. For a use case where data integrity may later need to
be demonstrated to a court or expert witness, that's a gap — not because
manipulation is assumed, but because "it could not have been tampered
with" carries little weight without technical proof.

This change originated from a user question about using blockchain/
Holochain to secure DB changes. After weighing the options (see
`design.md`), neither a real blockchain nor Holochain is the right
solution for a single-user local system — but the underlying need
(tamper-evident proof) is legitimate and can be solved with established,
much more lightweight means.

## What Changes

- Hash chaining for write audit events: every new log entry contains the
  hash of the previous entry plus its own payload (similar to a git
  commit chain) — making after-the-fact changes to existing entries
  detectable (the hash of subsequent entries then no longer matches).
- Periodic external anchoring of the current chain endpoint (hash of the
  latest chain) via **OpenTimestamps** (standard) — free, no wallet, no
  need to run your own blockchain node, an established legal-tech tool
  for "this data existed unchanged at time X".
- **Ethereum anchoring as an explicit opt-in alternative**, clearly
  labeled with a cost/wallet notice, following the same pattern as
  external LLM providers (never a silent default) — for users who prefer
  more publicly visible anchoring and are willing to accept the ongoing
  gas costs.
- A verification tool that checks the local chain against the last
  externally anchored verification and reports discrepancies.
- **No** use of Holochain or a custom blockchain — see `design.md` for
  the reasoning.

## Capabilities

### New Capabilities
- `tamper-evident-audit-log`: Cryptographically chained audit log for
  write database events, with optional external anchoring
  (OpenTimestamps by default, Ethereum as an opt-in alternative) to
  prove unchangedness to third parties.
