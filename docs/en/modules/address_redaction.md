# address_redaction.py — Postadressen in Freitext erkennen und entfernen

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/modules/address_redaction.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Detects German postal addresses in text (street with house number, postal code with town, P.O. box) and replaces them with a placeholder. Known personal addresses can additionally be stored locally so that unusual spellings are caught reliably.

## Relevance

Prevents home addresses in texts, PDFs and images from reaching external services or exports

## Method

Regular expressions for three forms: compound street names with a street suffix (…straße, …str., …weg, …allee, …gasse, …platz, …ring, …damm, …ufer, …steig, …pfad, …chaussee, …promenade) plus house number; prepositional streets (Am …, An der …, Im …, In der …, Auf dem …, Zum …, Zur …) plus house number; postal code (5 digits, optionally with D-) plus town name. Matches separated only by comma, space or line break are merged into one placeholder. Configured addresses from health_config.json (privacy_check.patient_addresses) are converted to tolerant patterns (ß/ss, Str./Straße, whitespace) and checked in addition. Quantities (mg, ml, days, steps …) after numbers do not trigger a match.

## Data flow

- **Reads:** `~/.config/kyoro/health_config.json`, `(privacy_check.patient_addresses`, `optional)`
- **Writes:** `Keine (reine Textfunktionen)`

## Limitations

Heuristic, not a guarantee: streets without a common suffix and without a preposition (e.g. "Hauptmarkt 3"), addresses in other languages and badly garbled OCR text are only caught reliably via configured addresses. Town names without a postal code are not removed. A five-digit number before a capitalised word may be mistaken for a postal code; common units and quantity words are excluded. Removes addresses of practices and laboratories as well as private ones.

## Usage

```bash
from modules.address_redaction import redact_addresses, find_address_spans
redact_addresses("Musterstraße 12, 12345 Musterstadt")   # -> "[ADRESSE-ENTFERNT]"
find_address_spans("Am Mühlberg 5")                       # -> [Span(0, 14, 'street')]
```
