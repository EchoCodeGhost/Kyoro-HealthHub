# media_redaction.py — Metadaten, sichtbare Adressen und Namen aus Bildern und PDFs entfernen

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/modules/media_redaction.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Reports (export) and removes metadata in images (EXIF incl. GPS) and PDFs (info, XMP, embedded JPEGs, attachments, JavaScript, forms) and blacks out postal addresses, person names, phone/insurance numbers as well as GPS coordinates and personal place names in the visible content. Everything runs locally.

## Relevance

Prevents home addresses, names and metadata from findings and photos from reaching storage, exports or external services

## Method

Report: Pillow reads EXIF tags, pikepdf reads info/XMP/attachments/actions/ annotations. Values are only output on request, otherwise tag names and counts. Redaction: words with positions come from the PDF text layer (pdftotext -bbox-layout) or via OCR (Tesseract, language deu). Address, name, number and place ranges (modules.address_redaction, name_redaction, identifier_redaction, location_redaction) are mapped onto the word boxes and covered with black rectangles on a rendered page image. Affected PDF pages are replaced by the image page so no text layer with an address, name, number or place remains. The output is then verified (text layer and OCR). Findings contain only counts, never the removed text.

## Data flow

- **Reads:** `Bilddateien`, `(JPEG`, `PNG`, `HEIC`, `mit`, `pillow-heif)`, `PDF-Dateien`, `~/.config/kyoro/health_config.json`, `(privacy_check.patient_addresses`, `privacy_check.patient_names`, `optional)`, `identity.db`, `(person_name_map`, `optional)`
- **Writes:** `Bereinigte Bild- und PDF-Dateien (Zieldatei muss angegeben werden)`

## Limitations

Optional tools: pytesseract + tesseract (OCR), pdf2image + poppler (rendering, word boxes). If missing, only metadata removal runs and a warning is reported. Detection is heuristic (see address_redaction); poor OCR can miss addresses and names. Affected PDF pages become images (no longer searchable, larger file). Redaction is real pixel coverage, not an annotation layer. Names are only detected with salutation/title/field label or from the list of known names (see name_redaction); numbers only in common notations (see identifier_redaction).

## Usage

```bash
from modules.media_redaction import report_image, report_pdf, scrub_image, scrub_pdf_full
report_pdf(Path("befund.pdf"))
scrub_pdf_full(Path("befund.pdf"), Path("sauber.pdf"))
scrub_image(Path("foto.jpg"), Path("sauber.jpg"))
```
