## Context

`post_import_sanitize.run()` has four steps. `_scrub()` and `_check()` open only `health.db`; `_pseudonymize_providers()` covers both databases. On `health.db` the scan is low risk, because its table list is narrow (`source_app`, `source`, `notes`).

Findings that shape this design:

- `scrub_sensitive_health_data()` ends with the pattern `\b[A-Z][a-z]+\s[A-Z][a-z]+\b` and replaces each match. Synthetic tests show it replaces disease names and lab terms. In German clinical text most capitalised word pairs are nouns, not people.
- `_scrub()` writes without a backup or prompt, and the replacement cannot be undone.
- A read-only count on a real `medicine.db` shows matches in `lab_manual.parameter` and `lab_manual.kategorie`, which are clinical identifiers, and in true free-text columns such as `lab_manual.kommentar`, `medications.notes` and `assessments.details`.
- `lab_manual.labor` also matches the long-digit pattern. Whether these are order numbers or something harmless is unknown and has to be reviewed locally.
- Audit triggers record old values in `audit_log`, which has its own matches. Rewriting a row therefore moves the old text to `audit_log` rather than removing it from the file.

## Goals / Non-Goals

**Goals:**
- Personal details in `medicine.db` free text are found on every sanitising run.
- No clinical value, parameter name, category or drug name is ever changed.
- Every rewrite is recoverable and traceable.

**Non-Goals:**
- Changing the `health.db` scan.
- Rewriting `audit_log`.
- Sanitising import files or `medicine_imaging.db`.
- A review UI. Review output is a local report.

## Decisions

### 1. Column allowlist instead of a table scan

A constant maps each table to its free-text columns, starting with `lab_manual.kommentar`, `lab_results.observations`, `medications.notes`, `medications.injection_site` and `assessments.details`. The remaining `diagnoses` text columns and `lab_manual.labor` are decided from the schema and a local review. A test fails if a new `TEXT` column in the medicine schema is neither allowlisted nor explicitly excluded, so new columns cannot be silently skipped or silently rewritten.

*Alternative:* scanning all text columns with a blocklist. Rejected: a new clinical column would be rewritten by default, which is the worse failure.

### 2. Two tiers, and heuristics never rewrite

| Tier | Patterns | Action |
|---|---|---|
| High confidence | E-mail, phone with a clear format, postal address, names from local config | Rewrite |
| Heuristic | Capitalised word pairs, titles, long digit runs | Report only |

The high-confidence tier reuses the existing building blocks (`modules/address_redaction`, the e-mail and phone handling in `anonymize.py`) but not `scrub_sensitive_health_data()` as a whole, because it includes the name pattern. Whether `modules/name_redaction` is precise enough on clinical text gets tested first. If not, only exact names from config are used.

*Alternative:* adding a medical term list to the name pattern. Rejected: such a list is never complete, and a missing term means irreversible data loss.

### 3. Backup and dry run

Before the first rewrite of a run, the database is copied using SQLite's backup API, next to the database with restrictive permissions, keeping a fixed number of copies. If the backup fails, nothing is rewritten and the step counts as failed. A report-only mode lists what would change, and it is run on real data before rewriting is enabled.

Encrypted databases need the backup to stay encrypted, which is a test case.

### 4. Reporting without leaking

Rewrites are logged to `medicine.db`'s `import_log` with table, column and count, never with values. Heuristic matches go into a local report under `intern/` or the configured analyses directory, with table, row ID and matched text. The terminal output, which the TUI also shows, carries counts only.

### 5. `audit_log` stays untouched

The tamper-evident design depends on `audit_log` not being rewritten. Old values remain there after a rewrite. The compliance check reports this count so the limit is visible, and a decision follows in Open Questions.

## Risks / Trade-offs

- **[False negatives]** Names in free text that are not in config are reported but not removed → Accepted: a review item is recoverable, destroyed clinical text is not.
- **[Rewrite damages clinical text anyway]** → High-confidence patterns only, allowlisted columns only, plus a backup and the dry run on real data before enabling.
- **[Personal details stay in `audit_log`]** → Reported, see Open Questions.
- **[Backups multiply sensitive data]** → Same location and protection as the database, with a fixed retention.
- **[Runtime on each import]** → `medicine.db` is small, and the scan covers few columns.

## Migration Plan

1. Run in report-only mode on real data and review the result locally.
2. Finalise the allowlist and enable rewriting.
3. Rollback: restore from the backup, and remove the step call.

## Open Questions

- Does an LLM path or export read `audit_log`? If yes, its old values are a real leak and need a separate decision. If no, reporting is enough.
- What are the long digit runs in `lab_manual.labor`? This decides the column's tier.
- Should the review report be able to mark entries as checked, so they do not reappear on each run?
