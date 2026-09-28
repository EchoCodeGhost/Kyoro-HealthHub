# debug_page.py — Testlauf für einzelne PDF-Seite

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/medical/debug_page.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Tests table extraction for a single PDF page using OpenVINO VLMPipeline or LLM provider. Useful for debugging and development.

## Relevance

Provides health data functions, essential for medical data processing

## Method

Extracts a specified page from a PDF, converts to image, and processes it through the VLMPipeline. Supports language and provider selection.

## Data flow

- **Reads:** `PDF-Dateien`, `(z.B.`, `medicine/krankenakte/*.pdf)`
- **Writes:** `STDOUT (extrahierte Tabellen als Markdown)`

## Limitations

Single page only. Requires OpenVINO or LLM provider.

## Usage

```bash
python medical/debug_page.py 1
python medical/debug_page.py 5 --lang de --provider openvino
```
