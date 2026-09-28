# process_inbox.py — Inbox-Prozessor für Import-Dateien

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/process_inbox.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Recognizes and routes files from imports/_inbox/ to the appropriate importers. Enables simple file drop without manual assignment.

## Relevance

Provides health data functions, essential for medical data processing

## Method

Supports ZIP archives (Apple Health, Polar GDPR, Garmin GDPR, Oura CSV) and single files (symptom history, WomanLog, Bearable, HRV4Training, Ecowitt, HealthManager Pro, RENPHO, Wellue O2Ring, ECGLogger, Omron, FDDB (diary_*.csv, userhistory_*.csv, combined complete_*.csv export), Hilo blood-pressure reports, PDF lab results, Migraine app, Shotsy, Kubios screenshots, Kubios TXT, GPX). ECGLogger and Omron are detected via header sniffing (filenames are app-generic, no fixed pattern). Files are moved to _inbox/processed/ after processing.

## Data flow

- **Reads:** `imports/_inbox/`, `Verzeichnis`
- **Writes:** `Verschiedene imports/*/ Verzeichnisse, imports/_inbox/processed/`

## Limitations

Detection is based on filename patterns. Unknown formats are silently skipped.

## Usage

```bash
python3 scripts/process_inbox.py              # alle Dateien in _inbox/
python3 scripts/process_inbox.py --dry-run    # zeigt was passieren würde
python3 scripts/process_inbox.py --import     # danach import_all.py --update
python3 scripts/process_inbox.py --file a.zip
```
