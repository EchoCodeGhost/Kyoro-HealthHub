## 1. Sources

- [ ] 1.1 Read the licence pages of the German candidates (Cologne, Berlin, other cities) and choose those with a confirmed, compatible licence; prefer data covering older generations
- [ ] 1.2 Confirm the licence of the US Social Security dataset at its publisher, and optionally check UK sources
- [ ] 1.3 Write `scripts/utils/name_lists/SOURCES.md` with publisher, URL, licence and attribution; report any coverage gap instead of using an unclear source

## 2. Build

- [ ] 2.1 Implement `scripts/utils/build_name_lists.py`: input path as an argument, frequency cut-off, minimum length, exclusions, sorted output, refusal without a source entry
- [ ] 2.2 Create `name_exclusions.txt` from a German word list check of all candidates and from clinical terms in the repo's lab and syndrome data
- [ ] 2.3 Tests with synthetic input: identical output on repeat builds, no counts in the output, exclusions applied, source rule enforced

## 3. Detection

- [ ] 3.1 Add one loader for the bundled lists that fails visibly when a file is missing or unreadable
- [ ] 3.2 Replace first-name regex matching in `name_redaction.py` with per-word lookup, keeping overlapping and merged spans working
- [ ] 3.3 Remove the first-name data from `scrub_pii.py` and `anonymize.py`, and change `find_pii_in_database()` so a single common word cannot trigger a rewrite
- [ ] 3.4 Update `utils/name_lists/README.md`, `name_validation.py` where needed, and affected docstrings
- [ ] 3.5 Tests with synthetic text: clinical phrases give no span, excluded name with a title gives a span, single common name gives no span, three-word name merges, missing file gives an error; existing redaction tests keep passing

## 4. Rollout on real data

- [ ] 4.1 Run the old and new comparison on real local databases and reports, with counts only in the output, and set the frequency cut-off from the result
- [ ] 4.2 Have newly matched words reviewed locally, and extend the exclusions; no matched text leaves the machine
- [ ] 4.3 Add a test that a name from `privacy_check.patient_names` is detected whether or not it is on a bundled list
- [ ] 4.4 Measure matching time on a long text, and confirm it does not get worse than the current list
- [ ] 4.5 Run `check_source_privacy.py`, `check_no_dates.py`, `check_docstrings.py`, `check_commit_message_privacy.py` on the commit message, and the full test suite, all clean
