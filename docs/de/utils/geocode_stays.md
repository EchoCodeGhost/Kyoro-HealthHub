# geocode_stays — Reverse Geocoding für GPS-Aufenthalte und Reisevorschläge

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/utils/geocode_stays.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Führt Reverse Geocoding für GPS-Koordinaten aus location_stays und session_tracks durch. Liest Breiten- und Längengrade, fragt Nominatim (OpenStreetMap, kostenloser Dienst) und schreibt die Ergebnisse in location_stays_geocoded. Erkennt zusätzlich Nicht-Heimaufenthalte aus GPS-Tracks (Workouts weit entfernt vom Zuhause) und schlägt neue Einträge für travel_history vor.

## Relevanz

Ermöglicht die Geokodierung von Aufenthaltsdaten, essentiell für die räumliche Analyse

## Methode

Verwendet Nominatim-API (https://nominatim.openstreetmap.org/reverse) mit Rate-Limit (1,1 Sekunden zwischen Anfragen). GPS-Koordinaten werden auf 2 Dezimalstellen gerundet (ca. 1,1 km Genauigkeit) durch round_coords() aus utils.anonymize für Datenschutz. Ermittelt Klimazone basierend auf Koordinaten und Ländercode. Heimbereich wird als Radius von 0,3 Grad (ca. 30 km) definiert. Session-Tracks werden nach Datum gruppiert und gemittelt für Cluster-Erkennung.

## Datenfluss

- **Liest:** `health.db.location_stays`, `health.db.session_tracks`, `health.db.sessions`, `~/.config/kyoro/travel_history.json`
- **Schreibt:**

  ```
  health.db.location_stays_geocoded, health.db.location_stays.timezone,
  ~/.config/kyoro/travel_history.json (bei Bestätigung durch Benutzer)
  ```

## Grenzen

Nominatim hat Rate-Limits (max. 1 Anfrage/Sekunde) - das Skript respektiert dies. Nur Aufenthalte mit gültigen GPS-Koordinaten werden verarbeitet. Reisevorschläge erfordern Benutzerbestätigung vor dem Hinzufügen zu travel_history. Beachte: Koordinaten werden für Geocoding verwendet, Ergebnisse werden in Datenbank gespeichert.

## Aufruf

```bash
python scripts/utils/geocode_stays.py
python scripts/utils/geocode_stays.py --force
python scripts/utils/geocode_stays.py --suggest-travel
python scripts/utils/geocode_stays.py --no-stays --suggest-travel
# --force: Alle Aufenthalte neu kodieren (überschreibt bestehende)
# --suggest-travel: GPS-Tracks nach Auslandsaufenthalten durchsuchen
# --no-stays: location_stays überspringen, nur GPS-Tracks verarbeiten
```
