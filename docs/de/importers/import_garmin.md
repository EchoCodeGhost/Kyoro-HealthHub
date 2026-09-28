# Garmin Connect → health.db

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/importers/import_garmin.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Importiert Daten aus Garmin Connect in die health.db. Unterstützt Schlaf, Herzfrequenz, HRV, Stress, Body Battery, SpO2, Atmung und tägliche Zusammenfassungen.

## Relevanz

Ermöglicht den Import von Gesundheits- und Aktivitätsdaten aus Garmin-Geräten, essentiell für die umfassende Analyse von Wearable-Daten

## Methode

Liest Garmin-Daten aus den von garmin_download.py erstellten Dateien. Schlaf → sessions + session_metrics, Herzfrequenz/HRV/Stress → measurements, tägliche Daten → measurements, Aktivitäten (via import_activities) → sessions + session_metrics inkl. training_load (aus Garmins eigenem aerobic/anaerobic Training Effect, HF-basiert), außer für generische 'other'-Aktivitäten oder wenn eine andere Quelle dasselbe Zeitfenster bereits abdeckt/verworfen hat (s. claim_training_load_slot, modules/base.py). Konfiguration über ~/.config/kyoro/garmin_config.json (geteilt mit garmin_download.py).

## Datenfluss

- **Liest:** `Garmin-Exportdateien`, `(JSON/CSV)`
- **Schreibt:** `health.db (sessions, session_metrics, measurements)`

## Grenzen

Keine Validierung der Garmin-Datenqualität. Abhängig von der Korrektheit des Garmin-Exports. Keine medizinische Interpretation. training_load für Aktivitäten ist eine grobe Näherung aus dem Trainingseffekt-Wert (s. GARMIN_TRAINING_LOAD_EFFECT_FACTOR), nicht direkt mit Polars training_load vergleichbar, nur als gleichwertiges Trigger-Signal gedacht.

## Aufruf

```bash
python3 import_garmin.py               # from 2024-01-01
python3 import_garmin.py --update      # only new data
python3 import_garmin.py --from 2025-01-01 --to 2025-12-31
python3 import_garmin.py --from 2026-05-01 --only sleep,bb,steps
```
