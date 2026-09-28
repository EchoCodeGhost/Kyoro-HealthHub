# Sleep Cycle CSV → health.db (sessions, session_metrics)

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/importers/import_sleep_cycle.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Import von Schlafdaten aus der Sleep Cycle App (iOS) für Schlafanalysen

## Relevanz

Ermöglicht den Import von Gesundheitsdaten, essentiell für die umfassende Datenanalyse

## Methode

Parsen von Semikolon-separierten CSV-Dateien mit Schlafmetriken. Erstellt sessions-Einträge (type='sleep') und speichert Metriken in session_metrics. Unterstützt Update-Modus zum Ergänzen neuer Nächte.

## Datenfluss

- **Liest:** `~/Kyoro-HealthHub/data/sleep_cycle/sleepdata*.csv`
- **Schreibt:** `health.db:sessions, health.db:session_metrics, health.db:user_context, health.db:import_log`

## Grenzen

Verarbeitet nur sleepdata*.csv Dateien. Zeitstempel werden von lokaler zu UTC konvertiert. Historische Daten werden nicht überschrieben (INSERT OR IGNORE).

## Aufruf

```bash
python3 import_sleep_cycle.py           # all CSVs
python3 import_sleep_cycle.py --update  # only neue Nights ergänzen
```
