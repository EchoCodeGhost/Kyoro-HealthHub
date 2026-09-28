# export_analyses_to_ods.py — Master-Exporter für alle Infektionsanalysen

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/analysis/infectious/export_analyses_to_ods.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Konvertiert Ausgabedateien aller Infektionsanalyse-Scripts in

## Relevanz

Unterstützt die infektionsbezogene Datenanalyse und Entscheidungsfindung durch systematische Aufbereitung von Wearable- und Symptomdaten

## Methode

Liest JSON/CSV/MD-Ausgaben aus analyses/*/ und schreibt .ods-Dateien via odfpy. Unterstützt outbreak_exposure, pathogen_exposure, postinfectious_diagnose, acute_response und combined-Export.

## Datenfluss

- **Liest:** `analyses/infectious/`, `(outbreak_exposure_*.md`, `pathogen_exposure_*.md`, `acute_response_*.md)`, `analyses/postinfectious/`
- **Schreibt:** `analyses/*/..._tabellen.ods, analyses/infectious_analysen_kombiniert.ods`

## Grenzen

Erfordert odfpy. Keine DB-Verbindung — liest nur Analysedateien.

## Aufruf

```bash
python3 export_analyses_to_ods.py
python3 export_analyses_to_ods.py --type outbreak_exposure
python3 export_analyses_to_ods.py --type all --output alle_infektionen.ods
python3 export_analyses_to_ods.py --recent-only
```
