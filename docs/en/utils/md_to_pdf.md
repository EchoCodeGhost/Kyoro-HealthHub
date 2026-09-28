# md_to_pdf.py — Markdown-Dateien in PDF umwandeln (via pandoc + xelatex)

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/utils/md_to_pdf.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Converts one or more Markdown files to printable PDFs. Optimised for medical reports: clean typography, title block, date, page numbers, cross-references.

## Relevance

Provides utility functions for data processing, essential for system functionality

## Method

Calls pandoc with xelatex engine. Font, margins and metadata are set via YAML front matter or CLI flags. Without --title the filename is used as title.

## Data flow

- **Reads:** `Markdown-Datei(en)`, `(.md)`
- **Writes:** `PDF-Datei(en) (neben der Quelldatei oder in --out-dir)`

## Limitations

Requires pandoc ≥ 2.x and xelatex (texlive). Very wide tables may overflow margins — use --landscape if needed.

## Usage

```bash
python3 scripts/utils/md_to_pdf.py bericht.md
python3 scripts/utils/md_to_pdf.py analyses/manual/lab_verlauf_*.md
python3 scripts/utils/md_to_pdf.py bericht.md --out-dir exports/
python3 scripts/utils/md_to_pdf.py bericht.md --title "Labor-Befunde" --author "Kyoro"
python3 scripts/utils/md_to_pdf.py bericht.md --landscape
python3 scripts/utils/md_to_pdf.py bericht.md --font-size 10
```
