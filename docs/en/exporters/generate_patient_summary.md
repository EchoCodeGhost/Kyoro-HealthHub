# generate_patient_summary.py - Patienten-Übersicht als OpenOffice-Writer-Dokument

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/exporters/generate_patient_summary.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Summarizes the manually maintained Kyoro config JSON files (family history, prior conditions, medications, vaccinations, surgeries) plus current medication status from medicine.db in a print-ready ODT flow-text document.

## Relevance

Reduces repeated by-hand intake-form filling at every appointment

## Method

Reads the same JSON sources as export_arzt_komplett.py, builds heading + bullet-list sections via odfpy (OpenDocumentText) instead of spreadsheet tabs. No personal content in source code - all content comes from KYORO_CONFIG_DIR at runtime.

## Data flow

- **Reads:** `~/.config/kyoro/family_history.json`, `clinical_events.json`, `medication_history.json`, `medicine.db::medications`
- **Writes:** `<output>.odt - Patientenübersicht als Fließtext`

## Limitations

Sections without a structured Kyoro source (emergency contact, disability status, advance directive, implants) are emitted as fill-in placeholders, not auto-populated. --language switches the document's own text; entries from config and medicine.db stay in the language they were entered in.

## Usage

```bash
python3 scripts/exporters/generate_patient_summary.py
python3 scripts/exporters/generate_patient_summary.py --output intern/patientenuebersicht.odt
python3 scripts/exporters/generate_patient_summary.py --language en
```
