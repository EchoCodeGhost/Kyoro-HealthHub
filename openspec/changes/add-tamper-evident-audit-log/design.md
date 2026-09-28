## Context

Kyoro-HealthHub is local-first: databases, raw data, and configuration
stay local, a remote LLM provider is opt-in, never a silent default
(see README "External AI providers"). The user asked whether DB changes
should additionally be recorded on a blockchain (specifically Holochain,
alternatively Ethereum) to strengthen tamper-evidence for a
court-admissibility goal.

## Goals / Non-Goals

**Goals:**
- Make after-the-fact changes to historical audit-log entries
  technically detectable (hash chaining).
- Provide a way to prove the state of the chain at a point in time to
  third parties (not just to the system itself) — a purely local hash
  chain is not enough for that: whoever controls the entire local chain
  could theoretically reconstruct it completely. External anchoring (a
  hash gets anchored somewhere the user does not control themselves) is
  the actual security gain.
- Keep this external anchoring as lightweight as possible: free, no
  permanently running service, no wallet as a default requirement.
- Make every external communication explicit opt-in and clearly labeled,
  in the same spirit as the existing remote-LLM-provider convention.

**Non-Goals:**
- No custom blockchain and no Holochain network. Reasoning: Holochain's
  core promise is distributed trust through **multiple** independent
  peers that validate each other. In a single-user local system, those
  other peers don't exist — the security model provides no added value
  here over a simple local hash chain, but would require a permanently
  running additional network service. That contradicts the local-first
  principle without delivering a corresponding security gain.
- No real-time/live anchor on every single write operation — with
  Ethereum that would carry real, ongoing per-anchor costs, and with
  OpenTimestamps it's unnecessary (batching at intervals is part of the
  protocol and is not a drawback).
- No replacement of existing encryption (SQLCipher) or backups (see
  `docs/BACKUP_DE.md`) — this change adds integrity proof, it replaces
  neither confidentiality nor availability of the data.

## Decisions

- **Hash chain:** every new audit entry stores
  `sha256(previous_hash || own_payload)`. Initially applied to
  `import_log` events (write meta-events: what was imported/changed when
  by which script) — not to every individual measurement row, to keep
  write load low. Extending this to clinically write-critical tables
  (e.g. `clinical.events`, `skin_lesions` histology updates) is a
  possible follow-up, but not part of this first implementation.
- **External anchoring is opt-in as a whole, default: off.** Just like
  with remote LLM providers, there is no silent network access — the
  hash chain itself is always kept locally, regardless of whether
  anchoring is enabled.
- **When enabled: any combination of two independent anchors, both
  explicitly configured, not exclusive.** Enabling both at the same time
  is supported and sensible — two independent external proofs are more
  robust than one (if one becomes unavailable or is challenged, the
  other still stands).
  - **OpenTimestamps (recommended as the base):** free, no wallet, no
    own node, an already-established legal-tech pattern for "proof of
    existence at time X" (e.g. for priority proofs). Uses the Bitcoin
    blockchain as an anchor in the background, without the user needing
    to interact with it directly.
  - **Ethereum (additional or alternative option):** for users who want
    more publicly visible/active anchoring. Requires explicit
    configuration (own wallet/RPC endpoint), a clear cost warning (gas
    fees are volatile and recur with every anchor).
  - "Recommended" refers only to cost/complexity, not availability —
    both are implemented and documented at equal rank.
- **No mandatory internet access for normal operation.** Anchoring runs
  are an explicit, separate step (e.g.
  `scripts/utils/anchor_audit_log.py`), not part of `import_all.py` or
  `compute_all.py`. If internet access is unavailable, the system keeps
  working as usual — only anchoring is delayed.

## Risks / Trade-offs

- [Risk] A purely local hash chain without external anchoring proves
  nothing to third parties (the user themselves could rebuild the whole
  chain) → Mitigation: external anchoring is the actual core of this
  change, not an optional add-on; documentation must make that clear, to
  avoid false confidence in pure chain integrity without an anchor.
- [Risk] OpenTimestamps anchoring needs a periodic internet connection
  (calendar server + later Bitcoin confirmation) → Mitigation:
  asynchronous, not time-critical; an anchor can be caught up even weeks
  later without losing intermediate chain integrity.
- [Risk] Ethereum gas costs are volatile and hard for laypeople to
  estimate → Mitigation: explicit cost warning before activation, no
  automatic/silent use.
- [Trade-off] Additional implementation and maintenance burden for a
  feature that only shows its value in an actual legal dispute/expert
  review — justified given the project's explicit court-admissibility
  goal, but deliberately deferred to after release, so as not to delay
  the actual release.
