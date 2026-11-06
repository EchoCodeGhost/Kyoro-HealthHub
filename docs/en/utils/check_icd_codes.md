# check_icd_codes.py — ICD-10-GM-Code↔Text-Review-Checker für Kandidaten-JSON

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/utils/check_icd_codes.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Scans a candidate JSON from import_billed_diagnoses.py (stage 1, before --commit) and reports per diagnoses row whether icd_code actually exists AND whether description content-wise matches that code's official title -- the actual "ICD checker" that neither import_billed_diagnoses.py's ICD_RE (format only) nor its _looks_bundled() (structural signal "several diagnoses merged together" only) can provide: a code↔text misassignment involving only ONE (not several) diagnosis would otherwise stay invisible.

## Relevance

Surfaces code↔text misassignments that would otherwise only be caught by chance while skimming (as in the F32.9 case), essential before --commit

## Method

Per diagnoses row (table=="diagnoses"): modules.icd10_catalog.is_known()/ lookup()/.check_description_plausible()/.check_bundled_contamination(). Five report categories: UNKNOWN CODE (code doesn't exist in the loaded ICD-10-GM year -- catches e.g. OCR-confused digits that still match the regex shape), NON-TERMINAL CODE (code exists but only as a category header without a fifth digit -- per metadata field 13/14 not valid for encoding, e.g. "F60.3" instead of "F60.31"), BUNDLED/CONTAMINATED (checked BEFORE text mismatch: description contains the diagnosis matching the code, but also text from unrelated diagnoses -- check_description_plausible() alone would call this "plausible", since the matching words do sit somewhere in the middle of the longer text), TEXT MISMATCH (code exists, but description shares no content word with the official title -- rows with the "(nicht automatisch zuordenbar)" placeholder are skipped, since there's no text to compare at all), and, if no catalog is installed, a single pointer to update_icd10_catalog.py instead of silent zero hits. Changes NOTHING in the candidate file -- pure report, the decision (fix the text, fix the code, ignore as a false positive) stays with the user.

## Data flow

- **Reads:** `imports/manual/billed_diagnoses_candidates.json`, `(Default`, `oder`, `--file);`, `data/reference/icd10gm/`, `(über`, `modules.icd10_catalog)`
- **Writes:** `keine Tabellen (reiner Report nach stdout)`

## Limitations

Only detects what modules.icd10_catalog can detect -- see its @limits (word-overlap heuristic, not a semantic comparison; only codes from the installed year). A mismatch report is a hint, not an automatic correction -- some genuine diagnosis texts (e.g. a full doctor's-letter sentence instead of the terse official short title) can share no content word by chance and get reported as a false positive.

## Usage

```bash
python3 check_icd_codes.py
python3 check_icd_codes.py --file imports/manual/andere_kandidaten.json
```
