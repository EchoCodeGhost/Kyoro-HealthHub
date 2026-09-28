# Medical-Motion PDF-Berichte → health.db

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/importers/import_medical_motion.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Reads monthly reports from the Medical Motion app (CE-certified system) and writes pain region data, wellbeing scores and categories into dedicated tables. Basis for time series analysis.

## Relevance

Enables import of health data, essential for comprehensive data analysis

## Method

pdfplumber extracts text page by page. Page 1: report period via regex; scores via OCR (pdf2image + pytesseract, crop Y=455–525 pt). Page 2: ICD-10 codes via regex, exercise stats via token matching. Pages 3–4 (pain cards): VLM call (OpenRouter, vision-capable model) with color scale reference from intern/mm_farbskala/; scores stored in pain_score. Skippable via --no-vlm. Pages 5–11: region names via word- coordinate grouping (Y-tolerance 3 pt), split left/right at page midpoint.

## Data flow

- **Reads:** `mm_report_meta`, `(MAX(report_to)`, `für`, `--update-Modus)`
- **Writes:**

  ```
  mm_report_meta: report_from TEXT, report_to TEXT,
  wellbeing_score_start INTEGER, wellbeing_label_start TEXT,
  wellbeing_score_end INTEGER, wellbeing_label_end TEXT,
  pain_score_start INTEGER, pain_label_start TEXT,
  pain_score_end INTEGER, pain_label_end TEXT,
  pain_trend TEXT, exercise_days_done INTEGER,
  exercise_days_total INTEGER, exercises_done INTEGER,
  exercises_skipped INTEGER, longest_streak INTEGER,
  surgery_regions TEXT, source_file TEXT, person TEXT;
  mm_pain_regions: report_to TEXT, region TEXT,
  region_label TEXT, pain_score INTEGER, duration TEXT,
  pain_type TEXT, timing TEXT, person TEXT, source TEXT;
  mm_diagnoses: report_to TEXT, icd_code TEXT,
  description TEXT, person TEXT
  ```

## Limitations

Pages 3–4 (pain cards) are pure vector graphics — per-region pain scores are not available as text; OCR extraction requires pdf2image + tesseract. Exercise stats are absent when the user gave no feedback ("Keine Angabe"). VLM scoring requires openrouter_api_key and vision-capable model (e.g. claude-sonnet-4-6 or gpt-4o); without API key, pain_score is set to NULL. PDF layout changes may break parsing.

## Usage

```bash
python3 import_medical_motion.py
python3 import_medical_motion.py --update
python3 import_medical_motion.py --file imports/_inbox/mm_report_05072026.pdf
python3 import_medical_motion.py --inbox
python3 import_medical_motion.py --no-vlm
```
