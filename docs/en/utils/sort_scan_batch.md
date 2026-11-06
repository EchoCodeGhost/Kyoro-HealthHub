# sort_scan_batch.py — Triage/Splitter für gemischte, gescannte Dokumentstapel

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/utils/sort_scan_batch.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Takes large, OCR'd batch PDFs (e.g. from a document scanner with several different document types scanned back-to-back) and splits them into individual, category-sorted PDF files. Also detects near-duplicate pages (the same sheet scanned twice).

## Relevance

Enables local pre-sorting of mixed scan batches without any AI involvement, essential for privacy when triaging large document volumes

## Method

Purely rule-based, NO LLM (local or cloud) involved — runs entirely without document content passing through any AI. Extracts page text via pdftotext (poppler-utils, must already be installed), classifies each page via keyword/regex heuristics (laborbefund/laboranforderung/arztbrief/genetik/abrechnung/ ueberweisungstraeger/trennblatt-or-ocr-junk/unclear), detects near-duplicates via Jaccard similarity on word shingles (threshold configurable, loose by default due to OCR noise), groups consecutive same-category pages within one source file into a logical document, and splits each into its own output file with pikepdf. Expects already-OCR'd PDFs (see @limits) — does not perform OCR itself.

## Data flow

- **Reads:** `keine`, `Tabellen`, `(reine`, `Datei-Operation)`
- **Writes:**

  ```
  keine Tabellen — nur Dateien: <out-dir>/<kategorie>/*.pdf
  + sortierung_bericht.txt (Status/Pfade, keine Inhalts-Snippets)
  ```

## Limitations

Expects already-OCR'd PDFs (searchable text) — run `ocrmypdf` first (see requirements.txt/onboard.py for install hint). Grouping only happens WITHIN one input file — a logical document split exactly across two input PDFs' boundary is not auto-merged (flagged in the report as an edge case at page 1/last page instead). Classification is heuristic, not a substitute for actual review — always check the result before further processing. No file is ever deleted; even "irrelevant" categories (bank transfer forms, separator sheets) only move to their own subfolder, never to the trash.

## Usage

```bash
python3 sort_scan_batch.py --file scan1_ocr.pdf scan2_ocr.pdf
python3 sort_scan_batch.py --file scan_ocr.pdf --out-dir /pfad/sortiert
python3 sort_scan_batch.py --file scan_ocr.pdf --similarity-threshold 0.6
python3 sort_scan_batch.py --lang en --file scan_ocr.pdf
```
