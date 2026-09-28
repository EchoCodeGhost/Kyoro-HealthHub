# import_tracks.py — GPX → session_tracks (+ neue Sessions falls kein Match)

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/importers/import_tracks.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Importiert GPX-Track-Daten in die session_tracks Tabelle und erstellt bei Bedarf neue Sessions

## Relevanz

Ermöglicht den Import von Gesundheitsdaten, essentiell für die umfassende Datenanalyse

## Methode

Verarbeitet GPX-Dateien aus verschiedenen Quellen (Garmin GPSMAP, Polar Flow, Apple Health, Garmin InReach). Jede GPX-Datei wird einem bestehenden Training-Session ueber Zeitueberlappung (±30 min) zugeordnet. Falls kein Match: neue Session wird mit ID Format gpx_YYYY-MM-DD_stem angelegt. Track-Punkte werden bei >3000 Punkten downgesampelt. Koordinaten werden anonymisiert (round_coords).

## Datenfluss

- **Liest:** `GPX-Dateien`, `aus`, `garmin_gpsmap`, `polar_gpx`, `apple_health_export/workout-routes`, `garmin_gdpr/INREACH`, `Verzeichnissen`
- **Schreibt:** `sessions, session_tracks, import_log`

## Grenzen

Abhaengig von GPX-Datei Struktur. Zeit-Matching funktioniert nur bei korrekter Timezone. Downsampling kann Details verlieren. run()/import_tracks_dir() reichten person schon vorher korrekt durch (Fallback: _main_person(conn)); main() hatte aber kein --person-Flag — jetzt ergaenzt.

## Aufruf

```bash
python import_tracks.py
python import_tracks.py --dir /pfad/zu/gpx
python import_tracks.py --person PER-xxxxxxxx
```
