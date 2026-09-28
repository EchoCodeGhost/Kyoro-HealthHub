# Master-Analyse — führt alle analyse_*.py-Skripte aus.

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/analyse_all.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Central execution of all analysis scripts and manages output

## Relevance

Enables comprehensive health data analysis, essential for holistic health assessment

## Method

Recursively scans all analyse_*.py scripts in analysis/ directory, creates dedicated output directory for each script: <analyses_dir>/<YYYY-MM-DD>/<scriptname>/ Plots (PNG/PDF) and text output (Markdown) are saved there. stdout + stderr are saved as <scriptname>.log. Supports filtering by date, script names, and dry-run mode.

## Data flow

- **Reads:** `Alle`, `Tabellen`, `die`, `von`, `den`, `einzelnen`, `Analyse-Skripten`, `gelesen`, `werden`
- **Writes:** `Analyseergebnisse in <analyses_dir>/<YYYY-MM-DD>/<scriptname>/`

## Limitations

No direct validation of results. Dependent on individual analysis scripts.

## Usage

```bash
python analyse_all.py                        # alle Skripte, mit KI-Kommentaren (Standard)
python analyse_all.py --no-llm                # ohne KI-Kommentare
python analyse_all.py --from 2026-01-01      # Datums-Filter
python analyse_all.py --only afib,sleep      # nur bestimmte (Namensbestandteil)
python analyse_all.py --skip cgm,h7          # bestimmte überspringen
python analyse_all.py --date 2026-05-31      # wird an Skripte weitergegeben die --date kennen
python analyse_all.py --dry-run              # zeigt was laufen würde, ohne Ausführung
```
