# konsil_pdf.py — Konsil-Gutachten als PDF rendern

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/utils/konsil_pdf.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Renders the markdown assessments of a consultation run into print-ready PDFs: one combined volume with cover page and table of contents, plus one PDF per individual assessment.

## Relevance

Enables print-ready hand-off of consultation assessments to physicians, essential for clinician communication

## Method

Markdown -> HTML (python-markdown, tables extension) -> PDF via headless Chrome (--print-to-pdf). Chrome already exists on macOS, so no LaTeX/wkhtmltopdf dependency is needed. Page breaks between assessments via CSS.

## Data flow

- **Reads:** `analyses/<datum>/konsil/*.md`
- **Writes:** `analyses/<datum>/konsil/pdf/*.pdf`

## Limitations

Requires Google Chrome at one of the known paths. Without Chrome the HTML is still written and its path reported so it can be printed manually.

## Usage

```bash
python3 scripts/utils/konsil_pdf.py analyses/2026-08-02/konsil
python3 scripts/utils/konsil_pdf.py analyses/2026-08-02/konsil --einzeln
```
