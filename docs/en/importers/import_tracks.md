# import_tracks.py — GPX → location.db::session_tracks (+ neue Sessions falls kein Match)

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/importers/import_tracks.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Imports GPX track data into location.db::session_tracks and creates new sessions in health.db if no match found

## Relevance

Enables import of health data, essential for comprehensive data analysis

## Method

Processes GPX files from various sources (Garmin GPSMAP, Polar Flow, Apple Health, Garmin InReach). Each GPX file is matched to an existing training session via time overlap (±30 min). If no match: new session is created with ID format gpx_YYYY-MM-DD_stem. Track points are downsampled when exceeding 3000 points. Precision and privacy zones are applied by location_store.store_track_points() per location_privacy.json.

## Data flow

- **Reads:** `GPX-Dateien`, `aus`, `garmin_gpsmap`, `polar_gpx`, `apple_health_export/workout-routes`, `garmin_gdpr/INREACH`, `Verzeichnissen`
- **Writes:** `health.db: sessions, import_log; location.db: session_tracks`

## Limitations

Depends on GPX file structure. Time matching only works with correct timezone. Downsampling may lose details. run()/import_tracks_dir() already threaded person through correctly (fallback: _main_person(conn)); main() had no --person flag — now added.

## Usage

```bash
python import_tracks.py
python import_tracks.py --dir /pfad/zu/gpx
python import_tracks.py --person PER-xxxxxxxx
```
