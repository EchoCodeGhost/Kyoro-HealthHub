# Polar GDPR Export → health.db

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/importers/import_polar.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Importiert Daten aus Polar GDPR-Exporten (JSON-Dateien) in die health.db. Unterstützt Trainingsdaten, tägliche Aktivität, 24/7 Herzfrequenz, PPI-Daten, Fitness-Assessments, HRV-Daten, Schlafdetails und orthostatische Tests.

## Relevanz

Ermöglicht den Import von Herzfrequenz- und Aktivitätsdaten aus Polar-Geräten, essentiell für die kardiale Analyse

## Methode

Liest JSON-Dateien aus dem Polar-Verzeichnis (Konfiguration: polar_dir). Jede Datei wird geparst und die Daten in die entsprechenden Tabellen geschrieben. Unterstützt mehrere Polar-Geräte aus der device_registry. Mapping: trainings → sessions + session_metrics, daily_activity → measurements, ppi → ppi_raw, nightly_hrv → polar_nightly_hrv, etc. --update/--from/--to filtern jetzt tatsächlich (jede Parse-Funktion bekommt date_from/date_to und überspringt Einträge außerhalb des Fensters) — vorher waren diese Flags reine No-op-Argumente, jeder Lauf hat immer den kompletten Bestand neu geparst (INSERT OR IGNORE hat das nur unsichtbar gemacht, nicht schneller). Alle Dateien werden trotzdem weiterhin geöffnet/geparst, um ihr eingebettetes Datum zu prüfen — kein Dateiname-basiertes Pre-Filtering, also kein I/O-Geschwindigkeitsgewinn, nur weniger unnötige DB-Schreibversuche. --update ermittelt date_from aus dem spätesten bereits importierten Datum über sessions/measurements/ppi_raw/polar_nightly_hrv/ polar_sleep_hypnogram/polar_sleep_wake hinweg (nicht nur eine Tabelle — manche Datentypen landen nie in sessions).

## Datenfluss

- **Liest:** `{polar_dir}/*.json`, `(Polar`, `GDPR`, `Export)`
- **Schreibt:**

  ```
  health.db (sessions, session_metrics, measurements, ppi_raw,
  assessments, polar_nightly_hrv, polar_sleep_hypnogram,
  polar_sleep_wake, polar_skin_contact, polar_hrv_spot)
  ```

## Grenzen

Keine Validierung der Polar-Datenqualität. Abhängig von der Korrektheit des GDPR-Exports. Keine medizinische Interpretation. vo2max stammt aus physicalInformation.vo2Max — Polars eigenem täglichem Profil-Snapshot, keine tagesaktuelle Einzelmessung wie bei Apple/Garmin. Kann über Monate exakt denselben Wert wiederholen, wenn Polars Algorithmus mangels ausreichend strukturierter Trainingsdaten keine neue Schätzung berechnet (beobachtet: 2626 Werte 2017-2026, seit Ende Mai 2026 durchgängig 18,0 — kein Kyoro-Bug, sondern Polar-seitiges Verhalten). Nicht unreflektiert mit anderen Geräten mitteln/vergleichen. --archive verschiebt ALLE *.json-Dateien im Verzeichnis nach originals/ — läuft deshalb NUR bei vollem Bestand (kein --update/--from/--to gesetzt), sonst übersprungen mit Hinweis. Sonst könnte eine wegen des Datumsfilters übersprungene, nie erfolgreich importierte Datei mit archiviert werden.

## Aufruf

```bash
python import_polar.py
python import_polar.py --update
python import_polar.py --from 2026-08-01 --to 2026-08-31
python import_polar.py --dir /pfad/zu/polar/daten
```
