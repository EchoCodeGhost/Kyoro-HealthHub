# Hilo/Aktiia PDF-Blutdruckberichte → health.db

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/importers/import_hilo_pdf.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Reads monthly PDF reports from the Hilo app (Aktiia Wrist BP) and writes the contained wrist blood pressure measurements into the blood_pressure table. Dual-column layout (two measurement records per line) is automatically resolved.

## Relevance

Enables import of health data, essential for comprehensive data analysis

## Method

pdfplumber extracts words with coordinates. Lines are grouped by Y-position (tolerance 3 pt). Each line holds two records of 7 tokens: DD. Month, YY + HH:MM + SBP + DBP + HR. Date is converted from local time (cfg.home_timezone) to UTC.

## Data flow

- **Reads:** `blood_pressure`, `(MAX(date)`, `für`, `--update-Modus)`
- **Writes:**

  ```
  blood_pressure: ts TEXT, date TEXT, systolic INTEGER,
  diastolic INTEGER, pulse INTEGER, device_id TEXT,
  person TEXT, source TEXT
  hilo_monthly_summary: report_month TEXT, context TEXT,
  sys_mean INTEGER, dia_mean INTEGER, hr_mean INTEGER,
  sys_sd REAL, dia_sd REAL, hr_sd REAL,
  sys_max INTEGER, dia_max INTEGER, hr_max INTEGER,
  sys_min INTEGER, dia_min INTEGER, hr_min INTEGER,
  measurement_count INTEGER, person TEXT, source TEXT
  ```

## Limitations

No access to raw PPG waveforms — aggregate values only. Measurement mode (calibration vs. regular) is not a separate column in the PDF; all entries receive source='hilo_pdf'. Page layout: page 1 (summary) is used for monthly statistics.

## Usage

```bash
python3 import_hilo_pdf.py
python3 import_hilo_pdf.py --update
python3 import_hilo_pdf.py --file pfad/bericht.pdf
python3 import_hilo_pdf.py --inbox
```
