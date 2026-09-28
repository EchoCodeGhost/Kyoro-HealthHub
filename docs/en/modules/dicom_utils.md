# dicom_utils — DICOM-Dateien lesen, anonymisieren und konvertieren

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/modules/dicom_utils.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Provides functions for reading, anonymizing, and converting DICOM files. Reusable for all DICOM sources (fundus, ECG waveforms, etc.).

## Relevance

Provides DICOM functions, essential for medical imaging

## Method

PII stripping removes all person-specific and institution data as well as sensitive information from DICOM metadata. Based on DICOM PS3.15 Annex E (Basic Application Level Confidentiality).

## Data flow

- **Reads:** `DICOM-Dateien`, `(z.B.`, `medicine/imaging/*.dcm)`
- **Writes:** `Anonymisierte DICOM-Dateien, konvertierte Bilder`

## Limitations

Anonymization does not remove embedded pixel data. Only JPEG output is supported.

## References

- DICOM PS3.15 Annex E (Basic Application Level Confidentiality)

## Usage

```bash
python dicom_utils.py
python dicom_utils.py --help
python dicom_utils.py --from 2024-01-01 --to 2024-12-31
```
