# scrub_media.py — Metadaten, Adressen, Namen, Nummern und Orte aus Bildern und PDFs melden oder entfernen

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/utils/scrub_media.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Command line for modules.media_redaction: shows which metadata (EXIF, GPS, PDF info, XMP, attachments, JavaScript) and which addresses and names are in files, and writes cleaned copies. All local, originals stay unchanged.

## Relevance

Makes image and PDF cleaning usable without an import, e.g. before sharing files

## Method

Subcommands: report (show metadata, optionally export as JSON), scrub (clean one file), scrub-dir (folder recursively into a target folder), check (exit code 1 if metadata, addresses or names are found). Values are only printed with --show-values. Addresses are never reported in cleartext, only as a count.

## Data flow

- **Reads:** `Bild-`, `und`, `PDF-Dateien`, `~/.config/kyoro/health_config.json`, `(optional)`
- **Writes:** `Bereinigte Kopien am Zielort, optional JSON-Report (--json-out)`

## Limitations

Never overwrites the original (target must be a different path). Without OCR/poppler only metadata removal runs and a warning is printed. Exit codes: 0 clean, 1 findings, 2 tools missing or error (with --strict).

## Usage

```bash
python -m utils.scrub_media report befund.pdf foto.jpg
python -m utils.scrub_media report ordner/ --json-out report.json
python -m utils.scrub_media scrub befund.pdf sauber/befund.pdf
python -m utils.scrub_media scrub-dir eingang/ ausgang/ --strict
python -m utils.scrub_media check ordner/
python -m utils.scrub_media scrub foto.jpg out.jpg --address "Musterstraße 12, 12345 Musterstadt" --name "Erika Mustermann"
```
