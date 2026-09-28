# scrub_apple_xml — Apple Health Export.xml PII-Bereinigung

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/utils/scrub_apple_xml.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Removes personally identifiable information (PII) from Apple Health Export.xml files. Rewrites the file in-place or writes to a specified output path. Removes: personal names from sourceName attributes and other PII from the <Me> element.

## Relevance

Provides data cleaning and anonymization functions, essential for data privacy

## Method

Uses fast regex-based line processing (no full XML parsing) to handle files of any size without loading them into memory. Specific regex patterns for: sourceName attributes, <Me> element attributes (HKCharacteristicTypeIdentifierDateOfBirth, HKCharacteristicTypeIdentifierBiologicalSex, etc.). Replaces values with neutral default values or empty strings. Supports dry-run mode (--check) for preview without changes.

## Data flow

- **Reads:** `Apple`, `Health`, `Export.xml`, `(Standardpfad`, `aus`, `health_config.json)`
- **Writes:** `Apple Health Export.xml (in-place) oder angegebene Ausgabedatei`

## Limitations

Processes files line by line - very large files may take longer. Only replaces known PII patterns - unknown patterns are not detected. Original file is overwritten (backup recommended).

## Usage

```bash
python scripts/utils/scrub_apple_xml.py
python scripts/utils/scrub_apple_xml.py --check
python scripts/utils/scrub_apple_xml.py --out /path/to/clean.xml
python scripts/utils/scrub_apple_xml.py --xml /path/to/Export.xml --check
# --check: Probelauf — keine Änderungen (zählt nur Treffer)
# --out: Ausgabedatei (Standard: in-place Überschreiben)
# --xml: Pfad zur Export.xml (Standard: aus health_config.json)
```
