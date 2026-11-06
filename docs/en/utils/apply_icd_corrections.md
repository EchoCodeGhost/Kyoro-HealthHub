# apply_icd_corrections.py — ICD-10-GM-Text-Mismatches in einer Kandidaten-JSON automatisch korrigieren (neue Datei)

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/utils/apply_icd_corrections.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Applies the text mismatches found by check_icd_codes.py automatically: description is replaced with the official ICD-10-GM class title, the old value is kept in notes. NEVER writes the input file, always a new output file -- the correction is a proposal meant to still be reviewed before --commit (the replaced/flagged rows stay identifiable, see icd_catalog_flag).

## Relevance

Automates the mechanical part of the ICD review work (text replacement), while keeping every change traceable, essential for making the volume of text mismatches manageable

## Method

Per diagnoses row: an unknown or non-terminal code is NOT auto-corrected (there is no safe automatic fix -- the correct code resp. fifth digit is unknown), only flagged with icd_catalog_flag="unknown_code"/"non_terminal" and a warning appended to notes, so they're still findable while reviewing the new file (e.g. "grep icd_catalog_flag"). Two cases are auto-corrected, each replacing description with lookup(code)["title"] and appending the old value to notes (nothing is lost, it only looks overwritten at first glance): text mismatches (code known and terminal, but description shares no content word with the official title -- icd_catalog_flag="text_mismatch_corrected") AND bundled/ contaminated rows (description contains the matching diagnosis PLUS text from unrelated diagnoses -- icd_catalog_flag="bundled_corrected"; checked BEFORE the text- mismatch check, since check_description_plausible() would wrongly call such a case plausible). Rows with the "(nicht automatisch zuordenbar)" placeholder are skipped (no text to replace). medications rows are copied through unchanged (the ICD catalog only applies to diagnoses). EVERY flagged row is also downgraded to status="needs_review", even if it was certainty=0.9/confirmed before -- found in a real case: two L70.0 rows with a practice address instead of diagnosis text were "confirmed", because the original heuristic (date+text+ no neighboring code) is blind to exactly this type of error; without this downgrade, the correction would just hide the error (the text now looks consistent) instead of surfacing it for review.

## Data flow

- **Reads:** `Kandidaten-JSON`, `(Default:`, `imports/manual/billed_diagnoses_candidates.json);`, `data/reference/icd10gm/`, `(über`, `modules.icd10_catalog)`
- **Writes:**

  ```
  Neue Kandidaten-JSON (Default: <eingabe>_icd_corrected.json) --
  NIE die Eingabedatei
  ```

## Limitations

Only corrects description, NEVER icd_code itself -- if the actual error was the code (not the text), the wrong code stays and description gets "corrected" to that code's (equally wrong) official title. The result then looks consistent but is still wrong -- hence still "reviewable", not meant for automatic commit.

## Usage

```bash
python3 apply_icd_corrections.py
python3 apply_icd_corrections.py --file imports/manual/andere_kandidaten.json --out imports/manual/andere_korrigiert.json
```
