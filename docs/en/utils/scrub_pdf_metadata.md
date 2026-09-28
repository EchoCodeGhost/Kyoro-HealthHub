# scrub_pdf_metadata.py — Entfernt PII-Metadaten aus PDF-Dateien

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/utils/scrub_pdf_metadata.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Strips document and image metadata from PDFs before archiving to originals/.

## Relevance

Provides data cleaning and anonymization functions, essential for data privacy

## Method

Removes the /Info dictionary (Author, Creator, Producer, Title, Subject, Keywords, CreationDate, ModDate) and the XMP metadata stream. Embedded JPEG images (DCTDecode) are extracted, run through imaging_utils.strip_exif_pii (removes GPS, device serial, owner name, MakerNote), and written back without EXIF.

## Data flow

- **Reads:** `PDF-Dateien`
- **Writes:** `PII-freie PDF-Dateien`

## Limitations

Only JPEG-encoded embedded images (DCTDecode) are checked for EXIF; other encodings (e.g. FlateDecode raw pixels from normal OCR scans) typically carry no EXIF and are left untouched. Form fields/annotations with their own metadata are not checked. pikepdf stamps its own Producer signature on save (software info, not PII).

## Usage

```bash
python scrub_pdf_metadata.py eingang.pdf ausgang.pdf
python scripts/utils/scrub_pdf_metadata.py imports/_inbox/befund.pdf data/staging/befund_scrubbed.pdf
```
