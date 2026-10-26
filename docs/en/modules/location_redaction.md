# location_redaction.py — GPS-Koordinaten und persönliche Ortsnamen in Text erkennen und entfernen

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/modules/location_redaction.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Detects GPS coordinates in text (decimal degrees, degrees/minutes/seconds, coordinates with a label) and personal place names (home town, work town, other stored places) and replaces them with placeholders. Complements address_redaction, name_redaction and identifier_redaction for images, PDFs and cloud calls.

## Relevance

Prevents whereabouts and location data in findings, reports and photos from reaching storage, exports or external services

## Method

Coordinates: decimal degree pairs with at least five decimals (48.13514, 11.58198) or four with a compass letter (N 48.1351 E 11.5820), degrees/minutes/seconds with a compass letter (48°08'06"N 11°34'55"E) and numbers after labels such as GPS, Koordinaten, Lat, Lon, Breitengrad. Place names: only places from the local configuration (health_config.json: privacy_check.patient_places), places from the stored addresses (the town after the postal code in privacy_check.patient_addresses) and places given by the caller. No general gazetteer is used so that states, countries, travel destinations and endemic regions stay available for the analysis.

## Data flow

- **Reads:** `~/.config/kyoro/health_config.json`, `(privacy_check.patient_places`, `privacy_check.patient_addresses`, `optional)`
- **Writes:** `Keine (reine Textfunktionen)`

## Limitations

Heuristic, not a guarantee: place names that are neither configured nor derived from an address stay (e.g. holiday places, employer sites). Places that are also ordinary words remove those words too. Coordinates without a label or compass letter and with fewer than five decimals or in unusual formats (UTM, geohash, plus codes) are not detected. Coordinates in image metadata are removed by scrub_pdf_metadata/imaging_utils; this module covers visible and sent text.

## Usage

```bash
from modules.location_redaction import redact_locations
redact_locations("Aufnahme bei 48.13514, 11.58198 in Musterstadt", extra_places=["Musterstadt"])
```
