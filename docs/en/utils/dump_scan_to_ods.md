# dump_scan_to_ods.py — Bestmögliche Tabellen-Extraktion aus OCR'ten Scans nach LibreOffice Calc

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/utils/dump_scan_to_ods.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

For documents whose layout is too irregular for automatic parser logic (e.g. old trend reports with nested multi-date comparison blocks): extracts pdfplumber's best-effort table detection per page and dumps it as its own sheet into an .ods file — for manual review/correction in LibreOffice Calc, instead of building a perfect but costly special-case parser for a single old document format.

## Relevance

Enables manual processing of hard-to-parse scans, essential for legacy data with irregular layout

## Method

Uses pdfplumber.Page.find_tables(table_settings={vertical_ strategy: text, horizontal_strategy: text}) — text-based column/row detection via whitespace gaps, no fresh OCR run (reuses the text layer ocrmypdf already embedded). If find_tables() finds nothing, the page falls back to plain text (one column) so nothing is lost. No LLM involved.

## Data flow

- **Reads:** `keine`, `Tabellen`, `(reine`, `Datei-Operation)`
- **Writes:** `keine Tabellen — nur eine .ods-Datei (ein Tabellenblatt pro Seite)`

## Limitations

No content validation — purely a best-effort dump of the detected table structure. For very irregular layouts (several nested mini-tables per page, as in the old trend reports), the column/row assignment won't necessarily be correct — that's the point: the human corrects in Calc rather than a fragile parser guessing.

## Usage

```bash
python3 dump_scan_to_ods.py --file scan.pdf
python3 dump_scan_to_ods.py --file scan1.pdf scan2.pdf --out /pfad/ausgabe.ods
```
