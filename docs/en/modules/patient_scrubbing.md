# patient_scrubbing.py — Entfernt die eigene Identität der Nutzerin aus Freitext

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/modules/patient_scrubbing.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Removes the configured user's own name, own birthdate, a "<number> years" pattern, and the German insurance-member- number format from free text before it is written to a table or intermediate file -- unlike provider_scrubbing.py (unknown third-party names, heuristic), the user's own identity is known exactly from config, so this is exact matching, not a heuristic.

## Relevance

Prevents the user's own identity from landing unpseudonymized in tables or intermediate files, essential for the privacy of every free-text-processing importer

## Method

Name: all word orderings (including "lastname, firstname") are removed exactly (case-insensitive). Birthdate: the config's ISO form plus the DD.MM.YYYY variant (with and without leading zeros) are removed exactly. Years-lived count: the pattern "<number> years(old)?"/"<number> Jahre(alt)?" is removed regardless of the current exact value (changes yearly, an exact match would already be wrong next year). Insurance member number: the German standard format (1 letter + 9 digits, optionally space-separated) is removed by pattern, regardless of whether the user's own number is configured anywhere.

## Data flow

- **Reads:** `health_config.json`, `(user.name`, `user.birthdate)`
- **Writes:** `keine Tabellen (reine Textverarbeitungsfunktion)`

## Limitations

No NER -- only detects the exactly configured values plus the two documented patterns (years-lived count, insurance-number format). A differently spelled name (nickname, OCR typo) is not detected. The insurance-number pattern can also match an unrelated number that happens to share the same shape (1 letter + 9 digits isn't unique) -- accepted risk, since removing it here is less harmful than missing it.

## Usage

```bash
from modules.patient_scrubbing import scrub_patient_identity
clean_text = scrub_patient_identity(raw_text)
```
