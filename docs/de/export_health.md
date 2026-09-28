# export_health.py — Themenspezifische Gesundheitsdaten-Exporte

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/export_health.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Exportiert kuratierte Gesundheitsdaten-Pakete aus health.db und medicine.db

## Relevanz

Bietet Gesundheitsdatenfunktionen, essentiell für die medizinische Datenverarbeitung

## Methode

Exportiert Daten aus health.db und medicine.db als CSV oder JSON basierend auf Profil-Definitionen. Jede Profil-Query wird anhand ihrer FROM-Tabelle automatisch an die richtige Datenbank geroutet (lab_manual/lab_results/medications/assessments -> medicine.db, alles andere -> health.db; siehe MEDICINE_DB_TABLES). Profil-Definitionen liegen als JSON-Dateien unter scripts/exporters/profiles/. Unterstützt Filterung nach Datum, Person und Ausgabeformat.

## Datenfluss

- **Liest:** `health.db`, `medicine.db`, `Profil-Definitionen`, `aus`, `scripts/exporters/profiles/`
- **Schreibt:** `Exportierte CSV/JSON-Dateien in exports/-Verzeichnis`

## Grenzen

Datenauswahl basiert auf Profilen. Keine automatische Anonymisierung.

## Aufruf

```bash
python export_health.py --profile cardiology --from 2026-01-01 --format csv
python export_health.py --profile general_practitioner --last 365d --person self
python export_health.py --profile research --person all --format json
python export_health.py --list                  # alle verfügbaren Profile
```
