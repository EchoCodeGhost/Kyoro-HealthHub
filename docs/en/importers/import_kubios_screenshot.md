# Kubios HRV Screenshot-Import

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/importers/import_kubios_screenshot.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Imports Kubios HRV Mobile screenshots via OCR

## Relevance

Enables import of health data, essential for comprehensive data analysis

## Method

Reads Kubios HRV Mobile screenshots (PNG) via OCR and imports the values into kubios_hrv_resting. Supports: - Kubios HRV Mobile "RESTING HRV" result screen - macOS screenshots - Any PNG screenshots (date from file metadata) All values are extracted, including PNS/SNS index.

## Data flow

- **Reads:** `PNG-Screenshots`
- **Writes:** `kubios_hrv_resting`

## Limitations

OCR may be inaccurate. Dependent on screenshot quality.

## Usage

```bash
python import_kubios_screenshot.py               # scannt imports/kubios/ (Default)
python import_kubios_screenshot.py --file screenshot.png
python import_kubios_screenshot.py --dir ~/Downloads/kubios/
python import_kubios_screenshot.py --file screenshot.png --dry-run
```
