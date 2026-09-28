# Kognitive Kurztests → health.db (cognitive_tests)

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/importers/import_cognitive_tests.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Imports results of cognitive short tests

## Relevance

Enables import of health data, essential for comprehensive data analysis

## Method

Imports cognitive test data into the cognitive_tests table. Supported test formats: - reaction_time (reaction time in ms) - sdmt (Symbol Digit Modalities Test) - digit_span (digit span forward/backward) - spatial_memory (spatial memory) - stroop (Stroop interference) - n_back (N-Back Working Memory Score) - pvt (Psychomotor Vigilance Task) - go_nogo (Go/No-Go inhibition control) App exports are automatically detected and converted.

## Data flow

- **Reads:** `CSV-Dateien`, `aus`, `~/Kyoro-HealthHub/imports/cognitive/`
- **Writes:** `cognitive_tests`

## Limitations

Dependent on test app export format.

## Usage

```bash
python3 import_cognitive_tests.py              # alle CSVs
python3 import_cognitive_tests.py --update     # nur neue Daten
python3 import_cognitive_tests.py --manual     # interaktive Eingabe
python3 import_cognitive_tests.py --template   # CSV-Vorlage ausgeben
```
