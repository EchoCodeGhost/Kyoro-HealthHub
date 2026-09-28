# exclude_autodetected_polar_training_load.py — Removes training_load from

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/migrations/exclude_autodetected_polar_training_load.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Wendet die in import_polar.py::import_polar_trainings() eingebaute Ausschluss-Logik (kein training_load für startTrigger= TRAINING_START_AUTOMATIC_TRAINING_DETECTION) nachträglich auf bereits importierte sessions-Zeilen an — die Importer-Änderung greift nur für künftige Läufe, bestehende Zeilen behalten ihren alten training_load-Wert, bis dieses Skript einmal läuft.

## Relevanz

Verhindert, dass automatisch erkannte Alltagsaktivität als Sport-Trigger in abgeleitete Auswertungen (PEM Evidence Score) einfließt

## Methode

Liest jede training-session_*.json erneut, prüft is_polar_auto_detected(); wo True, wird die passende sessions-Zeile über (date, ts_start, ts_end) gesucht — nicht über die dateinamen-basierte id, die vor dem Identifier-Fix (s. import_polar.py::training_session_identifier) noch in der DB steht. Existiert dort eine training_load-Zeile in session_metrics, wird diese gelöscht und durch auto_detected=1.0 ersetzt (Audit-Trail, warum training_load fehlt). Idempotent — bereits bereinigte Zeilen werden übersprungen.

## Datenfluss

- **Liest:** `{polar_dir}/training-session_*.json`, `sessions`, `session_metrics`
- **Schreibt:**

  ```
  health.db (DELETE training_load / INSERT auto_detected in
  session_metrics for auto-detected sessions)
  ```

## Grenzen

Betrifft nur type='training' AND source_app='polar_connect'. compute_pem.py (beide Modi) sollte danach neu berechnet werden.

## Aufruf

```bash
python3 scripts/migrations/exclude_autodetected_polar_training_load.py --dry-run
python3 scripts/migrations/exclude_autodetected_polar_training_load.py
```
