## 1. Classification

- [ ] 1.1 Classify every `TEXT` column of the medicine schema as allowlisted or excluded, and add the constant
- [ ] 1.2 Add the test that fails on unclassified `TEXT` columns
- [ ] 1.3 Test `modules/name_redaction` on synthetic clinical terms, and fall back to exact config names if it is not precise enough
- [ ] 1.4 Check every LLM and export path for reads of `audit_log`, and record the answer in the design

## 2. Sanitising step

- [ ] 2.1 Implement the high-confidence tier from the existing address, e-mail and phone building blocks, without `scrub_sensitive_health_data()`
- [ ] 2.2 Implement the heuristic tier, which only produces review entries
- [ ] 2.3 Implement the encrypted backup before the first rewrite, with retention and restrictive permissions; a failed backup blocks rewriting
- [ ] 2.4 Implement report-only mode
- [ ] 2.5 Log counts to `medicine.db`'s `import_log`, and write the review report to an untracked path
- [ ] 2.6 Call the step from `post_import_sanitize.run()` and report failures through its return value
- [ ] 2.7 Extend the compliance check to `medicine.db`, including the `audit_log` count, with no false violations for tables missing from the schema

## 3. Tests

- [ ] 3.1 With synthetic text only: clinical terms stay unchanged in allowlisted and excluded columns, high-confidence matches are replaced, the rest of the text stays intact
- [ ] 3.2 Backup: failure blocks rewriting, no backup without a rewrite, the backup opens with the same key, a restore gives the original values
- [ ] 3.3 Output contains no matched text, and `audit_log` is unchanged apart from trigger entries
- [ ] 3.4 Confirm that the `health.db` path and `find_pii_in_database()` behave as before

## 4. Rollout on real data

- [ ] 4.1 Run report-only on the real `medicine.db`; have the report reviewed locally, without values leaving the machine
- [ ] 4.2 Decide `lab_manual.labor` and the remaining columns based on that review
- [ ] 4.3 Enable rewriting, run once, and compare clinical columns before and after for an exact match
- [ ] 4.4 Run `check_source_privacy.py`, `check_no_dates.py`, `check_docstrings.py` and the full test suite, all clean
