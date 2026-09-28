# FibriCheck-PDF-Bericht → health.db

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/importers/import_fibricheck.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Imports FibriCheck heart-rhythm reports (smartphone-based PPG spot checks, reviewed by the FibriCheck expert panel) from PDF exports into a structured table.

## Relevance

Enables inclusion of independent PPG heart-rhythm spot checks (e.g. suspected extrasystoles/bigeminy), essential as an external comparison source alongside continuous wearable-based detection.

## Method

Reads the PDF text (pdfplumber), extracts measurement timestamp, review timestamp, result classification (free text + normalised code via a keyword mapping), average heart rate, activity context, reported symptoms, recording device, algorithm version, and expert-panel review status. No OCR needed — FibriCheck PDFs are text-based, not scanned. PDF is archived PII-scrubbed afterwards, same as import_lab_results.py.

## Data flow

- **Reads:** `PDF-Dateien`, `(FibriCheck-Berichte)`
- **Writes:**

  ```
  fibricheck_sessions: ts, ts_reviewed, date, result_code,
  result_text, hr_avg_bpm, activity_context, symptoms_reported,
  recording_device, algorithm_version, panel_reviewed, person,
  source_file
  ```

## Limitations

Smartphone camera PPG, not an ECG lead — same methodological limitation as other optical sources in the project (s. compute_arrhythmia.py). FibriCheck is CE-marked and reports are counter-checked by an expert panel, but that does not replace a 12-lead ECG examination (disclaimer in the report itself). result_code mapping only covers previously seen phrasings — new/ unknown result text lands as 'unknown' with the raw text kept in result_text, never silently mis-mapped.

## Usage

```bash
python import_fibricheck.py bericht.pdf
python import_fibricheck.py *.pdf
python import_fibricheck.py --person PER-XXXXXXXX bericht.pdf
```
