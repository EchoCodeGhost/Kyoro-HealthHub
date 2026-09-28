# reduce_gps_precision — Rundet nachträglich zu hochauflösende GPS-Punkte in session_tracks

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/utils/reduce_gps_precision.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Rundet bestehende `session_tracks`-Koordinaten mit mehr als 5 Nachkommastellen auf 5 Nachkommastellen (~1,1 m Raster) herab. Neue Importe runden bereits beim Schreiben (siehe `import_tracks.py`, `round_coords(..., precision=5)`); dieses Skript schließt die Lücke für Altdaten, die vor Einführung des Roundings oder über einen Pfad ohne `round_coords()`-Aufruf importiert wurden.

## Relevanz

Bietet Hilfsfunktionen für die Datenverarbeitung, essentiell für die Systemfunktionalität

## Methode

Identifiziert betroffene Zeilen mit derselben SQL-Bedingung wie `check_anonymization_compliance()` (utils/anonymize.py, `high_precision_gps`), rundet lat/lon via `round_coords(precision=5)` und schreibt sie zurück. Erstellt vor Änderungen ein Rolling-Backup der DB-Datei (überschrieben bei jedem Lauf), analog zu `scrub_pii.py`.

## Datenfluss

- **Liest:** `session_tracks`, `(lat`, `lon)`
- **Schreibt:** `session_tracks (lat, lon gerundet), health.db.gps_precision_backup (Rolling-Backup)`

## Grenzen

Behandelt nur `session_tracks` — die einzige Tabelle, die `check_anonymization_compliance()` auf GPS-Präzision prüft. Andere Tabellen mit lat/lon-Spalten (z.B. `location_history`) sind nicht Teil dieses Checks und werden hier nicht behandelt.

## Aufruf

```bash
python scripts/utils/reduce_gps_precision.py --dry-run
python scripts/utils/reduce_gps_precision.py
python scripts/utils/reduce_gps_precision.py --no-backup
```
