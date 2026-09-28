# fix_resting_hr_mislabeled_metrics.py — Renames two mislabeled resting-HR

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/migrations/fix_resting_hr_mislabeled_metrics.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Zwei Importer schrieben Werte unter generischen/falschen Metriknamen, die inhaltlich keine tageweise gemessene Ruhe-Herzfrequenz sind: (1) import_oura.py importierte Ouras readiness.contributors.resting_heart_rate -- ein 0-100-Skalen-Score, kein bpm-Wert -- faelschlich mit Einheit 'bpm' als 'readiness_hr_resting'; (2) import_polar.py importierte Polars physicalInformation.restingHeartRate -- ein selten aktualisiertes Profil-Feld fuer Polars eigene HF-Zonen-Berechnung, keine Tagesmessung -- unter dem generischen Namen 'resting_hr', identisch zu echten Tagesmessungen anderer Geraete (z.B. Garmin). Beide Importer sind bereits korrigiert (neue Metriknamen fuer kuenftige Importe); diese Migration zieht bereits importierte Datenbanken nach, damit compute_canonical.build_resting_hr() nicht laenger fehlerhafte Werte in health_canonical.resting_heart_rate einspeist.

## Relevanz

Verhindert, dass zwei fehlklassifizierte Wearable-Felder weiterhin als echte Ruhe-Herzfrequenz in abgeleitete Tabellen einfliessen -- Datenqualitaet, nicht Funktion.

## Methode

Zwei gezielte UPDATE-Statements auf measurements: (1) metric='readiness_hr_resting' AND source_app='oura_app' -> metric='readiness_contrib_resting_hr', unit=NULL; (2) metric='resting_hr' AND source_app='polar_connect' -> metric='polar_profile_resting_hr' (unit bleibt 'bpm', ist ein echter bpm-Wert, nur kein Tagesmesswert). Garmins 'resting_hr'-Zeilen (source_app='garmin_gdpr') bleiben unveraendert -- das sind echte Tagesmessungen. Idempotent: prueft vorher Zeilenzahl, Wiederholung ist ein No-Op.

## Datenfluss

- **Liest:** `health.db`, `(measurements)`
- **Schreibt:**

  ```
  health.db (measurements.metric, measurements.unit only --
  no values changed)
  ```

## Grenzen

Nach dem Lauf muessen compute_canonical.py und compute_daily_context.py neu ausgefuehrt werden, damit die abgeleiteten Tabellen die Korrektur widerspiegeln -- diese Migration aendert nur measurements.

## Aufruf

```bash
python3 scripts/migrations/fix_resting_hr_mislabeled_metrics.py --dry-run
python3 scripts/migrations/fix_resting_hr_mislabeled_metrics.py
python3 scripts/compute/compute_canonical.py
python3 scripts/compute/compute_daily_context.py
```
