# SQL-Spalten-Check gegen das reale Schema

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/check_sql_columns.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Finds SELECT statements querying columns that do not exist in the target table. This is the failure class behind the CLAUDE.md rule "code that parses is not code that runs": such statements compile, pass every docstring and compliance gate, and only fail at runtime — or, worse, invisibly, when swallowed by an except block.

## Relevance

Closes the gap between "compiles" and "runs". analyse_all only catches the part of this failure class that actually crashes; the half swallowed by try/except silently produces incomplete analyses — with health data, wrong results without any indication.

## Method

Reads the real schema from sqlite_master (tables AND views) of the configured database, then scans all .py under scripts/ for simple "SELECT col, col FROM table" patterns and compares the column list against PRAGMA table_info. Deliberately conservative: statements with JOINs, alias prefixes, expressions, aggregate functions or f-string interpolation are skipped, since they cannot be decomposed reliably without a real SQL parser. Few trustworthy hits beat a long list of false positives nobody reads.

## Data flow

- **Reads:** `scripts/**/*.py`, `health.db`, `(nur`, `sqlite_master`, `+`, `PRAGMA`, `table_info)`
- **Writes:** `STDOUT/STDERR (Fehlermeldungen)`

## Limitations

SELECT only, no INSERT/UPDATE. Not an SQL parser but a deliberately narrow heuristic — statements with JOINs, aliases, expressions or dynamically assembled SQL are not checked, so completeness is not guaranteed. Checked against ONE concrete database: tables that only a never-run importer creates are absent there and get skipped rather than reported.

## Usage

```bash
python3 scripts/check_sql_columns.py
python3 scripts/check_sql_columns.py --db /pfad/zu/health.db
python3 scripts/check_sql_columns.py --path scripts/analysis --quiet
```
