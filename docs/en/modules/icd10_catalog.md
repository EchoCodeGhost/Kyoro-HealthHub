# icd10_catalog.py — Lokaler ICD-10-GM-Katalog-Abgleich (Code-Existenz + amtlicher Text)

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/modules/icd10_catalog.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Checks whether an ICD-10-GM code actually exists (not merely shape-valid like ICD_RE in import_billed_diagnoses.py) and returns its official class title for comparison against an extracted free-text description -- built from a real finding: an OCR extraction had attached code F32.9 (depressive episode) to free text drawn from FOUR unrelated diagnoses, something no amount of regex-shape checking would have caught (see import_billed_diagnoses.py::_looks_bundled() for the structural heuristic; this module covers the content check a format check cannot).

## Relevance

Catches content-level misassignments (wrong/non-existent code, code↔text mismatch) that a pure format check cannot detect, essential for the reliability of imported diagnosis data

## Method

Does NOT read from the repo (the repo contains no ICD-10-GM data, see @limits), but from a local file downloaded by scripts/utils/update_icd10_catalog.py under data/reference/icd10gm/ -- format per the BfArM spec (semicolon-separated, field 7 = code without dash/star/ exclamation mark, field 2 = T/N terminal flag, field 9 = combined class title). Loaded lazily on first call and cached per process (the file has >16,000 lines, shouldn't be re-read per candidate). check_description_plausible() compares content-word sets (≥4 chars, boilerplate like "nicht näher bezeichnet" filtered via _STOPWORDS_DE) instead of a raw character ratio -- a raw difflib.SequenceMatcher ratio was tried first and discarded during testing: short German words share so many letters that even a clearly wrong pair (J42 "chronic bronchitis" vs. text "fracture of an unspecified toe") reached a ratio of 0.30 -- above any sensible threshold. No embeddings/no LLM -- deliberately simple and deterministic, since this only needs to catch gross misassignments like the F32.9 example, not fine wording differences.

## Data flow

- **Reads:** `data/reference/icd10gm/icd10gm<JAHR>syst_kodes.txt`, `(lokal`, `nicht`, `im`, `Repo`, `--`, `siehe`, `@limits)`
- **Writes:** `keine Tabellen (reine Nachschlage-/Prüffunktion)`

## Limitations

NO catalog bundled in the repo -- the ICD-10-GM download at BfArM requires each user to accept their OWN usage contract (download conditions); this cannot and should not be done once on behalf of every user of the public repo. Each installation must run update_icd10_catalog.py itself (its own form submission) or manually place the ZIP from bfarm.de. Without that local file, every function here returns None/False with a pointer to update_icd10_catalog.py, NOT a crash. Only codes from the currently downloaded year's version are recognized -- a code retired or introduced between two ICD-10-GM versions can be wrongly judged unknown/known depending on the billing year (see scripts/utils/update_icd10_catalog.py --check for the installed version). check_description_plausible() is a rough word-overlap heuristic, not a semantic comparison -- a more specific text than the terse official title (e.g. a detailed doctor's-letter sentence) can be wrongly flagged as "not plausible"; meant as a review hint, not an automatic correction.

## Usage

```bash
from modules.icd10_catalog import lookup, is_known, check_description_plausible, catalog_version
```
