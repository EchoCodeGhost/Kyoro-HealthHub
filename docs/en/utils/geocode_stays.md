# geocode_stays — Reverse Geocoding für GPS-Aufenthalte und Reisevorschläge

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/utils/geocode_stays.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Performs reverse geocoding for GPS coordinates from location_stays and session_tracks. Reads latitude/longitude, queries Nominatim (OpenStreetMap, free service) and writes results to location_stays_geocoded. Additionally detects non-home stays from GPS tracks (workouts far from home) and suggests new entries for travel_history.

## Relevance

Enables geocoding of location data, essential for spatial analysis

## Method

Uses Nominatim API (https://nominatim.openstreetmap.org/reverse) with rate limiting (1.1 seconds between requests). GPS coordinates are rounded to 2 decimal places (approx. 1.1km accuracy) via round_coords() from utils.anonymize for privacy. Determines climate zone based on coordinates and country code. Home area defined as radius of 0.3 degrees (approx. 30km). Session tracks are grouped and averaged by date for cluster detection.

## Data flow

- **Reads:** `health.db.location_stays`, `health.db.session_tracks`, `health.db.sessions`, `~/.config/kyoro/travel_history.json`
- **Writes:**

  ```
  health.db.location_stays_geocoded, health.db.location_stays.timezone,
  ~/.config/kyoro/travel_history.json (bei Bestätigung durch Benutzer)
  ```

## Limitations

Nominatim has rate limits (max 1 request/second) - script respects this. Only stays with valid GPS coordinates are processed. Travel suggestions require user confirmation before adding to travel_history. Note: Coordinates are used for geocoding, results are stored in database. Note: City and country names are used for geocoding but not stored.

## Usage

```bash
python scripts/utils/geocode_stays.py
python scripts/utils/geocode_stays.py --force
python scripts/utils/geocode_stays.py --suggest-travel
python scripts/utils/geocode_stays.py --no-stays --suggest-travel
# --force: Alle Aufenthalte neu kodieren (überschreibt bestehende)
# --suggest-travel: GPS-Tracks nach Auslandsaufenthalten durchsuchen
# --no-stays: location_stays überspringen, nur GPS-Tracks verarbeiten
```
