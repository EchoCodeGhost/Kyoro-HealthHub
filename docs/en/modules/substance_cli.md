# substance_cli.py — CLI-Helfer für Substanz-Tracker

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/modules/substance_cli.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Provides common CLI functions for substance trackers (medications, environmental substances, treatments). Each tracker has its own fields and a separate JSON file under ~/.config/kyoro/.

## Relevance

Provides substance processing functions, essential for pharmaceutical analysis

## Method

This module provides recurring mechanics: prompt with suggestions, date parsing, loading/saving, status/period formatting for table view, person selection.

## Data flow

- **Reads:** `~/.config/kyoro/*.json`, `(verschiedene`, `Tracker-Dateien)`
- **Writes:** `~/.config/kyoro/*.json (verschiedene Tracker-Dateien)`

## Limitations

Internal helper module. Intended for use through substance tracker scripts only.

## Usage

```bash
python substance_cli.py
python substance_cli.py --help
python substance_cli.py --from 2024-01-01 --to 2024-12-31
```
