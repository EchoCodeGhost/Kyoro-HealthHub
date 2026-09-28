# tables_llm.py — Tabellenextraktion via Vision Language Model

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/medical/tables_llm.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Extracts tables from scanned PDF documents using Vision Language Model (VLM). Uses the central call_llm() function with image support.

## Relevance

Provides health data functions, essential for medical data processing

## Method

Process: 1) Convert PDF pages to images, 2) Process each image via call_llm() with image_b64 parameter, 3) LLM delivers tables as Markdown, 4) Intermediate saving after each page. Provider selection from health_config.json.

## Data flow

- **Reads:** `PDF-Dateien`, `(z.B.`, `medicine/krankenakte/*.pdf)`
- **Writes:** `exports/tables/ Verzeichnis (Markdown/CSV-Dateien)`

## Limitations

Depends on VLM accuracy. Manual post-processing may be needed for complex layouts.

## Usage

```bash
python medical/tables_llm.py
python medical/tables_llm.py --lang en
```
