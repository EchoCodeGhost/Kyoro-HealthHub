# review_notes.py — Baut die menschenlesbare Review-Notiz für LLM-unterstützte Kandidaten-Extraktionen

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/modules/review_notes.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Builds the bilingual notes text (page + optional LLM-supplied location hint + the raw OCR excerpt the LLM values are based on) for importers following the extract→review→commit pattern (--extract writes candidates, a human reviews, --commit writes to the DB). Without this module, every such importer would have rewritten the same location/OCR formatting separately -- it was pulled out when the same logic was about to be repeated almost verbatim in a second importer (import_lab_trend.py) after the first (import_billed_diagnoses.py).

## Relevance

Keeps the review note (location + original text) consistent across all extract→review→commit importers, essential for making a review decision possible without going back to the original document

## Method

The raw OCR excerpt is joined with " | " instead of "\n" between lines, NOT because newlines themselves are a problem, but because the finished notes text is, in every known caller, subsequently run through scrub_patient_identity() (own identity removed before writing) -- which normalizes all whitespace (including "\n") to a single space, which would otherwise collapse a multi-line excerpt into an unreadable wall of words. An optional prefix (de, en) is placed before "page ...", for cases that need an explanatory sentence first (e.g. "the LLM couldn't find anything either"). The scrubbing itself stays the caller's responsibility, not this module's -- see @limits.

## Data flow

- **Reads:** `keine`, `Tabellen`, `(reine`, `Textverarbeitungsfunktion)`
- **Writes:** `keine Tabellen (reine Textverarbeitungsfunktion)`

## Limitations

Only assembles the text -- does NOT remove patient identity from the OCR excerpt. Callers must run the result through scrub_patient_identity() themselves before writing it to a candidate JSON or DB column (the raw OCR text AND an LLM-supplied location hint can contain the user's own identity, especially in documents about themselves). No truncation of the excerpt -- a very wide window (many lines) produces a correspondingly long notes value.

## Usage

```bash
from modules.review_notes import build_ocr_note
de, en = build_ocr_note(page=3, raw_text=window, location=result.get("fundstelle"))
notes = t(de, en)
```
