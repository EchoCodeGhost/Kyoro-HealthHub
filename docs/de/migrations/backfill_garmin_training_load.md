# backfill_garmin_training_load.py — Adds training_load to already-imported

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/migrations/backfill_garmin_training_load.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Wendet die in import_garmin.py::import_activities() eingebaute training_load-Ableitung (aus aerobic/anaerobic Training Effect) und die Quellen-Prioritätsauflösung (s. claim_training_load_slot, modules/base.py — Garmin schlägt Polar/Oura bei Überlappung) nachträglich auf bereits importierte Garmin-Sessions an. Die Importer-Änderung greift nur für künftige Läufe.

## Relevanz

Stellt sicher, dass bereits vor diesem Fix importierte Garmin-Aktivitäten denselben Sport-Trigger-Status bekommen wie künftig importierte

## Methode

Liest jede type='training' AND source_app='garmin_connect' Session ohne generische 'other'-Sportart, holt aerobic_training_effect/anaerobic_training_effect aus session_metrics, ruft claim_training_load_slot auf (verdrängt dabei ggf. training_load einer überlappenden, niedriger priorisierten Polar-/Oura-Session) und schreibt training_load. Idempotent — Sessions mit bereits gesetztem training_load werden übersprungen.

## Datenfluss

- **Liest:** `health.db`, `(sessions`, `session_metrics)`
- **Schreibt:**

  ```
  health.db (session_metrics.training_load for Garmin sessions;
  possibly DELETEs training_load from lower-priority overlapping
  Polar/Oura sessions via claim_training_load_slot)
  ```

## Grenzen

Betrifft nur type='training' AND source_app='garmin_connect'. compute_pem.py (beide Modi) sollte danach neu berechnet werden.

## Aufruf

```bash
python3 scripts/migrations/backfill_garmin_training_load.py --dry-run
python3 scripts/migrations/backfill_garmin_training_load.py
```
