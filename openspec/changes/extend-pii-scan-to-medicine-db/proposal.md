## Why

Post-import sanitising exists so the data can be shared with cloud LLMs without leaking personal details, but its general PII scan and compliance check only open `health.db`. `medicine.db` holds free text from doctors and labs and only gets provider pseudonymisation, so comments and notes there are never scanned.

Reusing the existing scan is not safe. Its name pattern treats any two capitalised words as a person and overwrites them without a backup. Tested on synthetic input, it replaces common disease and lab terms with `[NAME-ENTFERNT]`, and a read-only count on a real database shows hits in lab parameter names and categories. Pointed at `medicine.db`, it would irreversibly destroy clinical data.

## What Changes

- New `medicine.db` sanitising step, called from `post_import_sanitize.run()`, so it applies to `import_all.py`, `import_staged.py` and `--sanitize-only`.
- Only an explicit allowlist of free-text columns is scanned. Clinical identifiers such as lab parameters, categories, values and drug names are never touched.
- Two tiers:
  - High-confidence matches are rewritten automatically: e-mail addresses, phone numbers, postal addresses, and names known from local config.
  - Heuristic matches such as capitalised word pairs or titles are only reported for local review and never rewritten.
- Automatic backup of `medicine.db` before the first rewrite of a run, plus a report-only dry-run mode.
- Compliance check extended to report on `medicine.db`.
- `audit_log` is never rewritten. Its copies of old values are reported as a known limit.

## Capabilities

### New Capabilities
- `medicine-pii-sanitising`: Scanning, tiered rewriting, backup and reporting of personal details in `medicine.db` free text, without altering clinical data.

### Modified Capabilities
<!-- None: no existing spec describes post-import sanitising. -->

## Impact

- **Modified code:** `scripts/utils/post_import_sanitize.py`, `scripts/utils/anonymize.py` (compliance check for the medicine schema). `find_pii_in_database()` and the `health.db` path stay unchanged.
- **New code:** a sanitising module for `medicine.db` with tests based only on synthetic text.
- **Data:** rewrites allowlisted free text in `medicine.db`, each run backed up and logged. Writes no review content into the repo.
- **Related changes:** `provider-text-scrubbing` covers provider names through a registry. Once it lands, this change should use its module instead of a second implementation. `add-pipeline-tui` gets wider coverage through `--sanitize-only`, with no extra work. `add-tamper-evident-audit-log` is the constraint behind leaving `audit_log` untouched.
