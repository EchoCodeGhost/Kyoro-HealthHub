# HRV4Workout → health.db (hrv4training_daily)

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/importers/import_hrv4training.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Importiert HRV4Workout CSV-Exporte

## Relevanz

Ermöglicht den Import von Gesundheitsdaten, essentiell für die umfassende Datenanalyse

## Methode

Importiert den CSV-Export aus der HRV4Workout-App in hrv4training_daily. Export-Path in der App: Profiles -> Export -> "Export CSV". Typische columns: Date, HRV4T, Morning Readiness, RMSSD, HR, day, Comment, + beliebige Kontext-Variablen (Sleep, Erschoepfung, etc.).

## Datenfluss

- **Liest:** `HRV4Workout`, `CSV-Dateien`
- **Schreibt:** `hrv4training_daily`

## Grenzen

Abhaengig von App-Version und Exportformat.

## Aufruf

```bash
python import_hrv4training.py --file export.csv
python import_hrv4training.py --dir ~/Downloads/
python import_hrv4training.py --file export.csv --dry-run
```
