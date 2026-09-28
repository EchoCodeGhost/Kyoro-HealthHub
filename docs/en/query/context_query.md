# context_query.py — user_context abfragen mit optionaler Verknuepfung

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/query/context_query.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Enables querying of context data (notes, tags, annotations) from user_context table, optionally linked with other data on the same day

## Relevance

Provides context queries for health data, essential for data analysis

## Method

Supports various filters: by date (--from, --to), source (--source), tag (--tag), free text search (--search). Two modes: standard query (user_context) and linked query (--tag). With --with-context, same-day entries are displayed. With --sources, available sources are listed. Results are sorted by date descending.

## Data flow

- **Reads:** `user_context`, `canonical`, `Daten`, `Tabellen`
- **Writes:** `STDOUT (Abfrageergebnisse)`

## Limitations

Depends on data availability in user_context. No data manipulation.

## Usage

```bash
python3 context_query.py
python3 context_query.py --from 2026-06-01
python3 context_query.py --source hrv4training --symptoms
python3 context_query.py --context "Erschoepfung" --threshold 2
python3 context_query.py --tag mindful_session --from 2026-01-01
python3 context_query.py --search "schlecht geschlafen"
python3 context_query.py --sources
```
