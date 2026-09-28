# health_query.py — KI-gestützte Gesundheitsdaten-Analyse

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/query/health_query.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Interactive analysis interface for the multi-source health database. Uses the configured LLM provider for natural language evaluation and SQL generation. Enables medical data queries in natural language.

## Relevance

Provides comprehensive health data queries, essential for medical analysis

## Method

Uses the configured LLM provider (Mistral, Claude, etc.) for: 1. SQL generation from natural language (SYSTEM_SQL) 2. Interpretation of SQL results (SYSTEM_INTERPRET) 3. Specialized analyses (HRV, anomalies, arrhythmia, sleep) Supports interactive mode, pre-built analyses (hrv, sleep, etc.) and free-form questions in natural language.

## Data flow

- **Reads:** `Alle`, `Tabellen`, `der`, `health.db`, `(siehe`, `SCHEMA-Konstante)`
- **Writes:** `STDERR/STDOUT (Analyseergebnisse), OUT_DIR/health_queries/ (Logs)`

## Limitations

No medical diagnoses without data support. SQL generation limited to 50 results. Queries are validated against the schema. Not suitable for real-time diagnostics. Does not replace medical assessment.

## Usage

```bash
python health_query.py                    # Interaktiver Modus
python health_query.py hrv               # HRV-Analyse
python health_query.py schlaf            # Schlafanalyse
python health_query.py "Wie war mein Sleep im März?" # Freie Frage
python health_query.py --sql "Wie war..." # Mit SQL-Output
python health_query.py healthcheck       # DB-Verbindungstest
```
