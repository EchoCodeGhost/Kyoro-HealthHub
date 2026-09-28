# Oura Ring CSV-Export → health.db

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/importers/import_oura_csv.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Importiert Daten aus Oura Ring CSV-Exporten (data.zip) als Ergänzung zur API. Bietet granularere Rohdaten und zusätzliche Metriken, die nicht über die offizielle API verfügbar sind.

## Relevanz

Ermöglicht den Import von Schlaf- und Erholungsdaten aus Oura-Ringen, essentiell für die Schlafanalyse

## Methode

Liest die data.zip-Datei aus imports/oura/ oder einem expliziten Pfad. Importiert: Zyklusdaten (Phasen, Fruchtbarkeit), Tages-Tags, Rohdaten (Temperatur, Tagesstress, Schlafmodell), Metriken (VO2max, Workouts, Kontrazeption, OMSS-Score) und Aufenthaltsdaten. Workouts landen zusätzlich (gefiltert nach Aktivitätstyp, s. mirror_workouts_to_sessions) in sessions/session_metrics, damit sie wie Polar-Trainings in trainingload-basierte Trigger (compute_pem.py) einfließen können — oura_workouts selbst bleibt die vollständige, ungefilterte Rohablage.

## Datenfluss

- **Liest:** `{imports/oura/}/data.zip`, `(Oura`, `CSV`, `Export)`
- **Schreibt:**

  ```
  health.db (oura_cycle_insights, oura_period_starts,
  oura_cycle_predictions, oura_tags, oura_temperature_raw,
  oura_daytime_stress, oura_sleep_model, oura_vo2max, oura_workouts,
  oura_contraception, oura_survey, location_stays, sessions,
  session_metrics, ...)
  ```

## Grenzen

Ergänzt die API-Daten, ersetzt sie nicht. Einige Tabellen werden nur erstellt, wenn Daten vorhanden sind. Keine medizinische Interpretation. training_load für gespiegelte Oura-Workouts ist eine grobe kalorienbasierte Näherung (s. OURA_TRAINING_LOAD_CAL_FACTOR), nicht herzfrequenzbasiert wie bei Polar/Garmin — nur als Trigger-Signal, nicht als exakt vergleichbare Trainingslast zu verstehen. Oura hat unter allen Quellen die niedrigste Prioritätsstufe (s. TRAINING_LOAD_SOURCE_PRIORITY, modules/base.py) — bei Überlappung mit Polar oder Garmin verliert Oura seinen training_load unabhängig von der Importreihenfolge, auch wenn die andere Quelle erst später importiert wird.

## Aufruf

```bash
python import_oura_csv.py                        # neueste data.zip in imports/oura/
python import_oura_csv.py --file /pfad/data.zip  # expliziter Path
python import_oura_csv.py --rebuild              # Tables leeren + neu aufbauen
```
