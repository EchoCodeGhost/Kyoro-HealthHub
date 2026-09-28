# Infectious Analysis Module — Infektionsbezogene Analyse-Skripte

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/analysis/infectious/__init__.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Enthält Analyse-Skripte für Infektionsdaten

## Methode

Analyse von Infektionsverläufen, Symptommustern und postinfektiösen Mustern

## Datenfluss

- **Liest:** `infectious`, `symptoms`, `measurements`
- **Schreibt:** `infectious_analysis, postinfectious_analysis`

## Grenzen

Heuristische Analysen, keine medizinische Bewertung

## Aufruf

```bash
python __init__.py
python __init__.py --help
python __init__.py --from 2024-01-01 --to 2024-12-31
```
