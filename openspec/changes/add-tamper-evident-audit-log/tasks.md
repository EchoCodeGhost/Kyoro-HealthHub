## 1. Hash chain (local, always active)

- [ ] 1.1 Schema extension: add `prev_hash`, `entry_hash` columns to `import_log` (migration in `utils/create_schema.py`)
- [ ] 1.2 Implement hash computation: `sha256(prev_hash || canonical_serialization_of_row)` on every new log entry
- [ ] 1.3 Handle the genesis case (first entry, no `prev_hash` present)
- [ ] 1.4 Verification function: walk the entire chain, recompute hashes, report discrepancies

## 2. External anchoring — opt-in, default: off

- [ ] 2.1 Config field `clinical.audit_anchor.enabled` (default `false`) + `clinical.audit_anchor.methods` (list, e.g. `["opentimestamps"]`, `["ethereum"]`, or both at once `["opentimestamps", "ethereum"]` — independent, parallel anchors, not exclusive)
- [ ] 2.2 `scripts/utils/anchor_audit_log.py` — separate, manually/cron-triggered script, not part of `import_all.py`/`compute_all.py`
- [ ] 2.3 OpenTimestamps integration: send the current chain-endpoint hash to the OTS calendar server, store the `.ots` receipt locally
- [ ] 2.4 OpenTimestamps upgrade function: periodically check/update `.ots` receipts for full Bitcoin confirmation
- [ ] 2.5 Ethereum integration (only if `method=ethereum`): send the hash as a transaction to the configured wallet/RPC endpoint, store the transaction ID locally
- [ ] 2.6 Before any Ethereum activation: explicit cost/gas warning, no automatic first-time activation

## 3. Verification tooling

- [ ] 3.1 `scripts/utils/verify_audit_log.py` — checks the local chain + (if present) the latest external anchor, reports discrepancies
- [ ] 3.2 Human-readable report: "Chain locally consistent up to row N, externally anchored on date X via method Y"

## 4. Documentation

- [ ] 4.1 `docs/AUDIT_LOG.md` + `_DE`: how it works, activation, limits (a purely local chain without an anchor proves nothing to third parties)
- [ ] 4.2 Link from `docs/BACKUP.md`/`_DE` (integrity vs. availability are different properties)
- [ ] 4.3 README mention in the same style as other opt-in network features

## 5. Review

- [ ] 5.1 Check against existing privacy/local-first conventions (no silent network access)
- [ ] 5.2 `check_source_privacy.py` and docstring conventions (`@tier`, `@relevance`, `@limits`) followed for all new scripts
