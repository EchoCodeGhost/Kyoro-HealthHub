# Cycle Analysis Module — Zyklus-Analyse-Skripte

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/analysis/cycle/__init__.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Enthält Analyse-Skripte für Menstruationszyklus-Daten

## Methode

Analyse von Zykluslänge, Ovulation, Hormonverläufen und zyklusbedingten Symptomen

## Datenfluss

- **Liest:** `cycle`, `symptoms`, `measurements`
- **Schreibt:** `cycle_analysis, ovulation_prediction`

## Grenzen

Heuristische Analysen basierend auf subjektiven Daten

## Aufruf

```bash
python __init__.py
python __init__.py --help
python __init__.py --from 2024-01-01 --to 2024-12-31
```
