# extract_tables.py — Tabellenextraktion aus PDF-Dokumenten

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/medical/extract_tables.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Extracts tables from scanned PDF documents (e.g., medical records) using OCR technology for further processing.

## Relevance

Provides health data functions, essential for medical data processing

## Method

Uses PaddleOCR (PPStructureV3) for table detection and extraction. Converts PDF pages to images, analyzes the structure, and extracts table data. Saves results as CSV files.

## Data flow

- **Reads:** `medicine/krankenakte/*.pdf`
- **Writes:** `exports/tables/ Verzeichnis (CSV-Dateien)`

## Limitations

Depends on OCR accuracy. Complex table layouts may cause errors. Manual post-processing recommended.

## Usage

```bash
python medical/extract_tables.py
python medical/extract_tables.py --file path/to/document.pdf
```
