# import_fundus.py — Fundusfotos (DCM/JPEG) importieren, anonymisieren, VLM-Analyse

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/importers/import_fundus.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Imports fundus photos and performs VLM analysis

## Relevance

Enables import of health data, essential for comprehensive data analysis

## Method

Pipeline: 1. Convert DCM to JPEG (PII fully removed, via dicom_utils) 2. Save JPEG in data/fundus/ (filename without personal data) 3. Save metadata in medicine_imaging.db 4. Optional: VLM analysis via OpenRouter (--analyse)

## Data flow

- **Reads:** `DCM/JPEG-Dateien`
- **Writes:** `data/fundus/, medicine_imaging.db`

## Limitations

VLM analysis may be inaccurate. Dependent on image quality. --person used to be hardcoded to OWN_PERSON_ID (no override possible) — important for a shared device (e.g. a fundus camera in an eye clinic), where the device/file origin alone says nothing about the person pictured. Now settable via --person.

## Usage

```bash
python3 scripts/importers/import_fundus.py <datei_oder_verzeichnis> [--analyse] [--lang de|en]
python3 scripts/importers/import_fundus.py /path/to/fundus/ --analyse
python3 scripts/importers/import_fundus.py rechts.dcm links.dcm --analyse
python3 scripts/importers/import_fundus.py scan.dcm --person PER-xxxxxxxx
```
