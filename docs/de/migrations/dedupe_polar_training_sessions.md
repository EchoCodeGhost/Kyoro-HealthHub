# dedupe_polar_training_sessions.py — Removes duplicate and phantom Polar

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/migrations/dedupe_polar_training_sessions.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Bereinigt `sessions`-Zeilen (type='training', source_app='polar_connect') aus zwei behobenen Import-Bugs: (1) Duplikate, weil die Session-ID bislang aus dem Dateinamen statt der stabilen Polar-`identifier.id` gebildet wurde (s. import_polar.py::training_session_identifier) — jeder Re-Sync/Re-Export desselben physischen Trainings erzeugte einen neuen Dateinamen und damit eine neue sessions-Zeile, INSERT OR IGNORE griff nicht, weil die IDs verschieden waren. (2) Phantom-Zeilen aus training-target-*.json — geplante, laut eigenem 'done': false NIE durchgeführte Trainingsziele aus Polars Trainingstagebuch, die der frühere zu breite Datei-Glob ('training*.json') ebenfalls als echte Sessions importierte.

## Relevanz

Bereinigt aufgeblähte Trainings-Auslöser (training_load), die in abgeleitete Auswertungen wie den PEM Evidence Score einfließen

## Methode

Phase 1: löscht alle Zeilen mit id LIKE 'polar_training_training-target-%' (immer training_load=NULL, kein stopTime/deviceId — nie echte Ereignisse). Phase 2: gruppiert die verbleibenden Zeilen nach (person, date, ts_start, ts_end) — zwei real unabhängige Trainings starten und enden nicht auf dieselbe Sekunde, das ist ein robuster Duplikat-Schlüssel. Aus jeder Gruppe (>1 Zeile) wird eine Zeile behalten (bevorzugt: device_id beginnt mit 'DEV-', sonst kleinste id als deterministischer Tie-Breaker), die übrigen inkl. ihrer session_metrics gelöscht.

## Datenfluss

- **Liest:** `health.db`, `(sessions`, `session_metrics)`
- **Schreibt:**

  ```
  health.db (DELETE auf sessions + session_metrics für Duplikat- und
  Phantom-Zeilen)
  ```

## Grenzen

Betrifft nur type='training' AND source_app='polar_connect' — andere Quellen (Apple Health etc.) nutzen eine andere ID-Bildung und sind von den behobenen Bugs nicht betroffen. Nach dem Lauf sollte compute_pem.py (beide Modi) neu berechnet werden, da tl_d (SUM(training_load) pro Tag) sich ändern kann.

## Aufruf

```bash
python3 scripts/migrations/dedupe_polar_training_sessions.py --dry-run
python3 scripts/migrations/dedupe_polar_training_sessions.py
```
