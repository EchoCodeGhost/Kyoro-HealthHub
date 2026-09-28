# Immunology Analysis Module — Immunologische Analyse-Skripte

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/analysis/immunology/__init__.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Enthält Analyse-Skripte für immunologische Daten

## Methode

Analyse von Entzündungsmarkern, Autoimmunreaktionen und immunologischen Mustern

## Datenfluss

- **Liest:** `immunology`, `symptoms`, `measurements`
- **Schreibt:** `immunology_analysis`

## Grenzen

Heuristische Analysen, immunologische Diagnosen erfordern Labortests

## Aufruf

```bash
python __init__.py
python __init__.py --help
python __init__.py --from 2024-01-01 --to 2024-12-31
```
