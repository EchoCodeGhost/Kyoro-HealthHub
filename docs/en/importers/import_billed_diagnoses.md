# Abgerechnete Diagnosen- und Medikamentenhistorie (ICD-10 + Apotheken-Verordnungen, OCR-Scan) → medicine.db

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/importers/import_billed_diagnoses.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Extracts ICD-10-coded entries AND pharmacy prescription blocks from an OCR'd health-insurer benefits overview (scanned + ocrmypdf) and imports them in two stages (extraction → human review → commit) into the existing diagnoses resp. medications tables.

## Relevance

Enables import of a decades-long, scanned ICD-10-coded and medication history, essential for a complete medical history

## Method

Stage 1 (--extract): reads .txt or .pdf (via pdftotext), finds ICD-10 codes via regex as well as Apotheke/PZN/Verordnung anchors, assigns date/code/descriptive text resp. PZN/drug name via a line-window and type-based heuristic (label order in the OCR text is not reliably fixed). Diagnoses are often billed as a start/end period, medications have separate prescription/ dispensing dates -- find_date_candidates() looks for TWO label types in parallel (beginn/ende resp. verordnung/abgabe) and choose_date() picks independently per label type. Ambiguous cases only go to an EXCLUSIVELY LOCAL LLM (openvino/ovms/ollama/lmstudio/llamacpp/ exo/mlx — cloud providers are hard-rejected) if --llm-fallback is passed. Without --llm-fallback (default), ambiguous cases are NOT sent to an LLM — they're marked as a low-certainty candidate directly. Deliberate deviation from the original plan: the local LLMs available on this machine are too slow for a full run at this document's scale (hundreds of matches); no match is discarded, only the automatic disambiguation step is skipped. For diagnoses, the LLM-fallback prompt additionally asks for the correct ICD-10 code (OCR occasionally confuses digits/letters, e.g. "O" for "0") -- a different but regex-valid code overrides the one found by the anchor. For both types, the prompt also asks for a brief location hint (label/neighboring line) so a human can relocate the spot in the original document. certainty=0.6 entries therefore carry in notes: the page number, that location hint (if the LLM supplied one), and the full raw OCR window excerpt the LLM was given -- not just a "LLM was involved" remark, but the material the LLM based its values on, so the review decision is possible without going back to the original document. Stage 2 (--commit) reads the (possibly hand-corrected) candidate JSON and writes each entry to the table named by "table". The raw scanner filename (which may embed a device/batch/timestamp identifier) is pseudonymized via identity_resolver.resolve_sourcefile() before being written to the candidate JSON, never stored in cleartext.

## Thresholds

| Value | Meaning |
|---|---|
| `certainty = 0.9 (diagnoses)` | date+text+no neighboring code unambiguous -- status=confirmed, without LLM |
| `certainty = 0.7 (medications)` | date+drug name+no neighboring PZN unambiguous -- status=confirmed, without LLM |
| `certainty = 0.6` | ambiguous, but --llm-fallback supplied a value -- status=needs_review, notes contains location+original OCR |
| `certainty = 0.3` | ambiguous and unresolved (without --llm-fallback OR even by the LLM) -- status=needs_review |

## Data flow

- **Reads:** `diagnoses`, `medications`, `(für`, `Duplikat-Vermeidung`, `via`, `UNIQUE-/`, `PRIMARY-KEY-Constraint`, `nur`, `Stufe`, `2)`
- **Writes:**

  ```
  imports/manual/billed_diagnoses_candidates.json (Stufe 1; "source_file"
  enthält bereits das Pseudonym, nicht den rohen Scanner-Dateinamen
  -- siehe identity_resolver.resolve_sourcefile());
  diagnoses: date TEXT (Beginn), date_to TEXT (Ende, meist NULL --
  siehe @limits), icd_code TEXT, description TEXT, status TEXT,
  certainty REAL, source TEXT, notes TEXT, provider_pseudonym TEXT
  (via scripts/modules/provider_scrubbing.py);
  medications: ts TEXT, date TEXT (Verordnung), date_abgabe TEXT
  (Abgabe, meist NULL -- siehe @limits), medication_id TEXT,
  drug_name TEXT, is_chronic INTEGER, source TEXT, notes TEXT,
  prescriber_pseudonym TEXT (Verordner-Nummer, ebenfalls über
  identity_resolver pseudonymisiert statt im Klartext behalten)
  (Stufe 2)
  ```

## Limitations

The treating provider is only kept pseudonymized (provider_pseudonym), never in cleartext, and only as precisely as scrub_provider_text()'s registry/heuristics allow — an unknown name without a title/address stays unresolved (NULL). No cost column for diagnoses. date_to/ date_abgabe are only filled when an "Ende"/"Abgabe" label sits unambiguously nearby OR the LLM fallback supplies them -- in this document type those label words are rare column headers (roughly 1 per 30 entries), not a per-entry marker, so both fields stay NULL for almost all deterministically-resolved entries. For medications, no dosage is present in the source document (dose_value/dose_unit/route stay NULL). OCR errors in codes/PZN are only corrected if --llm-fallback ran AND the LLM returned a regex-valid differing value (icd_code for diagnoses, medication_id for medications) -- without --llm-fallback, or when the LLM also misses the error, the (possibly wrong) regex-anchored value stands. Duplicate protection for medications relies only on (ts, person, source). Without --llm-fallback, all ambiguous cases stay at certainty=0.3/needs_review even though an LLM could in principle resolve some of them — this is deliberate (see @method), not a limitation a human review pass should skip.

## Usage

```bash
python3 import_billed_diagnoses.py --extract --file /pfad/zur/datei.txt
python3 import_billed_diagnoses.py --extract --file /pfad/zur/datei.pdf
python3 import_billed_diagnoses.py --extract --file /pfad/zur/datei.pdf --llm-fallback
python3 import_billed_diagnoses.py --commit
python3 import_billed_diagnoses.py --commit --file imports/manual/andere_kandidaten.json
```
