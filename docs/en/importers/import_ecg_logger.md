# ECGLogger (Matti Mononen) → health.db

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/importers/import_ecg_logger.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Imports ECG traces and RR intervals from ECGLogger exports into health.db. Enables arrhythmia detection with actual ECG images, QRS detection for precise RR intervals, and AFib morphology analysis.

## Relevance

Enables import of ECG data, essential for cardiological analysis

## Method

ECGLogger records with Polar H7/H10 at 130 Hz (7.69 ms/sample). Supported formats: ECG-CSV (time_ms, ecg_mV, 130 Hz raw signal), RR-TXT (one RR value per line in ms), Kubios-HRM (Polar-compatible). Storage: ecg_logger_sessions (session metadata + QRS statistics), ecg_logger_ecg (raw ECG samples for plots/medical reports), ppi_raw (RR intervals, source='ecg_logger') — all three now use the actually passed-in person (CLI --person or the run() parameter, via resolve_person()) instead of being hardcoded to OWN_PERSON_ID. Provides both run(conn, data_path, lang, person) per the project convention and the full main() CLI (--tags/--notes/--dry-run/ --plot) — both call the same _import_files() core loop, no duplicated logic.

## Data flow

- **Reads:** `ECGLogger`, `Export`, `(CSV/TXT`, `Polar`, `H7/H10)`
- **Writes:** `health.db (ecg_logger_sessions, ecg_logger_ecg, ppi_raw)`

## Limitations

No validation of ECG data quality. No automatic arrhythmia detection. No medical evaluation from ECG data. Important for shared devices (e.g. a clinic sensor used across multiple people): the device id alone says nothing about the person — --person must be set explicitly on each run, otherwise the config default (own person) applies.

## Usage

```bash
python import_ecg_logger.py --file session.csv
python import_ecg_logger.py --file session.csv --plot        # EKG-Strip erzeugen
python import_ecg_logger.py --dir ~/Downloads/ecglogger/
python import_ecg_logger.py --file session.csv --dry-run
python import_ecg_logger.py --file session.csv --tags "tachykardie,aufstehen"
python import_ecg_logger.py --file session.csv --person PER-xxxxxxxx
```
