## 0. Precondition

- [x] 0.1 Confirm `add-guided-anamnesis-interview` is implemented and the `anamnese_findings`/`anamnese_sessions` tables exist in `health.db` before starting any task below — this change reads from that table.

## 1. Non-interactive append functions in the four target scripts

- [x] 1.1 `manage_family_history.py`: add `add_entry_noninteractive(entry: dict) -> None` — validates against the existing `RELATIVES`/`SIDES`/`STATUSES` choice lists (same validation the interactive `cmd_add` uses), writes via the existing `load()`/`save()` pattern. Existing `cmd_add()` unchanged.
- [x] 1.2 `manage_travel_history.py`: same pattern — `add_entry_noninteractive(entry: dict) -> None`, reuses existing validation/`save()`. Existing `cmd_add()` unchanged.
- [x] 1.3 `manage_exposure_history.py`: two non-interactive functions mirroring the existing interactive pair — `add_animal_contact_noninteractive(entry: dict) -> dict` and `add_occupational_exposure_noninteractive(entry: dict) -> dict`, reusing existing `load()`/`save()`. Existing `cmd_animal_add()`/`cmd_occupation_add()` unchanged.
- [x] 1.4 `manage_known_risk_exposures.py`: `add_entry_noninteractive(entry: dict) -> None` — MUST validate `entry["slug"]` against the current known syndrome-slug set from `analyse_outbreak_exposure.py` before writing (spec requirement "known_risk_exposures.json promotion requires a valid current slug"); raise a clear, catchable error (not a silent no-op) if the slug doesn't validate, so the caller in group 3 can surface that to the user.
- [x] 1.5 Unit tests for all five new functions (1.1, 1.2, 1.3 ×2, 1.4) using synthetic entries, no real personal data in fixtures — confirm each writes the same shape of entry as its interactive counterpart would, confirm the known-risk-exposures function rejects an invalid slug. `tests/unit/test_manage_noninteractive_append.py`.

## 2. Promotion candidate detection

- [x] 2.1 Implement the track → target-store mapping (design.md decision 3) as a small, explicit lookup table (not inferred from track name string matching) — used by both group 3 (CLI) and any future non-interactive caller. `TRACK_TO_TARGETS` in `promote_anamnese_findings.py`.
- [x] 2.2 For occupational/animal-contact/exposure-travel tracks, implement the "chronic vs. one-off" judgment that decides whether `known_risk_exposures.json` is additionally offered as a secondary target — reuse whatever signal the interview's own extraction already captures for this (e.g. a duration/date-range on the finding) rather than re-deriving it from free text at promotion time. `is_chronic_exposure()`.
- [x] 2.3 Implement idempotency tracking (design.md decision 5, open question): add a mechanism (column on `anamnese_findings` or a small mapping table — pick one, document the choice here) that records which finding/target pairs have already been promoted, so a second `--promote` run on the same session doesn't re-offer or duplicate them. **Decision: small mapping table** — `anamnese_promotions(finding_id, target_type, promoted_at)`, `UNIQUE(finding_id, target_type)` — a column on `anamnese_findings` couldn't represent one finding promoted to several targets (e.g. a chronic occupational exposure going to both `exposure_history.json` and `known_risk_exposures.json`).

## 3. `--promote` CLI mode

- [x] 3.1 Add `--promote <session_id>` to the anamnesis-interview review/export helper (`add-guided-anamnesis-interview` task 4.1) — iterates not-yet-promoted findings for the session, using the mapping from 2.1/2.2.
- [x] 3.2 For each finding/target pair: display the complete entry that would be written (all fields, human-readable, in the session's interview language), then prompt for explicit y/n confirmation (spec requirement "Human-confirmed, per-finding promotion") — never write without this step.
- [x] 3.3 On confirmation: call the matching non-interactive function from group 1, then mark the finding/target pair as promoted (2.3).
- [x] 3.4 On decline: skip that target for that finding, continue to the next proposed promotion — a decline is not an error and does not stop the run.
- [x] 3.5 When a finding has no applicable target under the current mapping, skip it silently in `--promote` output (it already surfaces via the plain-Markdown export from task 4.1) — do not print a confusing "nothing to promote" message per such finding.
- [x] 3.6 Person-column handling: any `person`/subject value copied from `anamnese_findings` into a target JSON entry (e.g. a family-history finding's subject) MUST be resolved back to its human-readable form via `identity_resolver.resolve_display_name()` before writing — the target JSON files are local-only config, not `health.db`, and are expected to contain human-readable labels (e.g. `"Mutter"`), consistent with how the existing interactive `cmd_add` flows already populate them.

## 4. Tests & dogfooding

- [x] 4.1 Integration test: run the full flow with synthetic `anamnese_findings` rows (no real personal data) — confirm entries land correctly in each of the four target JSON files, confirm re-running `--promote` does not duplicate them. `tests/unit/test_promote_anamnese_findings.py` — built against the real `create_schema.py` `SCHEMA` (an earlier version of this test hand-rolled its own schema with an extra `slug` column that masked a real "no such column: slug" crash against the actual project schema — fixed both the schema and the test).
- [x] 4.2 Integration test: a finding with an invalid/stale `known_risk_exposures.json` slug is correctly excluded with a clear message, not silently dropped or written invalid. `test_invalid_slug_finding_excluded_not_silently_written`.
- [ ] 4.3 Manual dogfooding: after `add-guided-anamnesis-interview` has produced at least one real session with real findings, run `--promote` for real and confirm the promoted entries actually show up correctly in a subsequent `analyse_outbreak_exposure.py`/`export_arzt_komplett.py` run — this is the actual acceptance check for this change's purpose (interview findings reaching the existing analysis/export pipelines), not just "the JSON file has a new entry."

## 5. Privacy & compliance

- [x] 5.1 `python3 scripts/utils/check_source_privacy.py` exits 0 against all modified/new files.
- [x] 5.2 `python3 scripts/check_compliance.py` reviewed for the new code; any new findings resolved or approved via baseline with justification. No new findings from this change (pre-existing violations in unrelated files, verified unrelated).
- [x] 5.3 Confirm none of the four target `.json` files or the new functions ever log/print a raw person pseudonym (`PER-...`) where a resolved display name should appear (ties to task 3.6).

## 6. Documentation

- [ ] 6.1 Short section in the anamnesis-interview's own documentation (once it exists, per `add-guided-anamnesis-interview` task 7.1) pointing to `--promote` as the way findings reach the existing structured stores.
- [x] 6.2 `python3 tools/gen_docs.py` for all modified scripts → `OK`.
- [x] 6.3 `openspec validate add-anamnese-findings-promotion --strict` green before archiving.
