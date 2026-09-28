# imaging_utils.py — Bildformat-Normalisierung mit PII-Stripping

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/modules/imaging_utils.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Normalizes smartphone image formats and removes PII from EXIF metadata.

## Relevance

Provides imaging functions, essential for medical image analysis

## Method

Input: HEIC/HEIF, JPEG, PNG, MOV/MP4. Output: JPEG without EXIF PII. Removes GPS, device serial, owner name, MakerNote. Device serial is pseudonymized before removal (→ identity.db). DateTimeOriginal is extracted and returned.

## Data flow

- **Reads:** `Bilddateien`, `(HEIC/HEIF`, `JPEG`, `PNG`, `MOV/MP4)`
- **Writes:** `Normalisierte JPEG-Dateien`

## Limitations

Requires Pillow (mandatory), pillow-heif (recommended for HEIC), ImageMagick (fallback for HEIC), opencv-python (for MOV/MP4).

## Usage

```bash
python imaging_utils.py
python imaging_utils.py --help
python imaging_utils.py --from 2024-01-01 --to 2024-12-31
```
