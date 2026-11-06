# name_redaction.py — Personennamen in Freitext erkennen und entfernen

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/modules/name_redaction.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Detects person names in text (names with salutation or title, names after field labels such as "Name:", known names of the person and relatives, common first and last names) and replaces them with a placeholder. Complements address_redaction for images and PDFs.

## Relevance

Prevents names of patients, relatives and clinicians in findings and photos from reaching storage, exports or external services

## Method

Regular expressions for: salutation/title plus name (Dr., Prof., Dr. med., salutation words …), field label plus name (Name, Patient, Versicherte, "Name, Vorname"), listed first name plus capitalised word, capitalised word plus listed last name. Known names come from health_config.json (privacy_check.patient_names), from identity.db (person_name_map: name and aliases) and from the caller; every name part of three or more letters is removed as a whole word, case-insensitively. Adjacent matches merge into one placeholder.

## Data flow

- **Reads:** `~/.config/kyoro/health_config.json`, `(privacy_check.patient_names`, `optional)`, `identity.db`, `(person_name_map`, `optional)`, `scripts/utils/name_lists/name_lists.json`
- **Writes:** `Keine (reine Textfunktionen)`

## Limitations

Heuristic, not a guarantee: names without salutation, title, field label or entry in the known names (e.g. "Max Muster called") are not detected. Short name parts (under three letters) are not removed individually. Known names that are also ordinary words remove those words too. Poor OCR can miss names. Names of practices and laboratories are not a goal of this module.

## Usage

```bash
from modules.name_redaction import redact_names, find_name_spans
redact_names("Dr. med. Muster, Kardiologie")
redact_names("Notiz zu Erika", extra_names=["Erika Mustermann"])
```
