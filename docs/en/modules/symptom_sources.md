# symptom_sources.py — Vereinheitlichte Symptom-Tage über alle bekannten Quellen

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/modules/symptom_sources.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Aggregates symptom-relevant signals from all known raw and derived sources (not just the symptoms table) into a single, date-indexed structure that correlation scripts (e.g. analyse_pollen_symptoms.py) can use without their own per-source query logic.

## Relevance

Prevents each correlation script from seeing only the symptoms table and thereby systematically undercounting symptom days (Oura tags, acute-score days were previously disconnected).

## Method

Merges five sources: 1. symptoms (health.db) — manual/app logs (kyoro_st, shotsy, symptomtagebuch, womanlog, manual), category -> numeric value. 2. user_context (health.db) — Oura tags (presence-coded as 1.0 per day+tag name, category prefixed "oura:"). 3. acute_events (health.db) — daily severity score computed from vitals (score_total, symptom_count), category prefixed "acute:" — covers nearly every day regardless of manual logging, device-agnostic (Polar/Garmin/Oura, whichever supplied measurements that day). 4. session_metrics (health.db) for sessions.type='migraine' — detail values from the Migraine app (severity, aura, nausea, photophobia, vomiting, ...), category prefixed "migraine:". 5. assessments (medicine.db) — standardized instruments (e.g. MIDAS), category prefixed "assessment:". Return format matches the prior load_symptoms() pattern in analyse_pollen_symptoms.py: {date: {category: value}} — existing correlation functions (correlate(), lag analyses) work unchanged.

## Data flow

- **Reads:** `health.db:`, `symptoms`, `user_context`, `acute_events`, `sessions`, `session_metrics;`, `medicine.db:`, `assessments`
- **Writes:** `Keine Tabellen (reine Aggregationsfunktion)`

## Limitations

medicine_conn is optional — without it only the assessments source is missing (smallest contribution of the five sources). Prefixes (oura:/acute:/migraine:/ assessment:) are chosen deliberately to rule out category-name collisions with the symptoms table — must be accounted for when filtering by category name.

## Usage

```bash
from modules.symptom_sources import load_symptom_days
symptome = load_symptom_days(conn, date_from, date_to, person, medicine_conn=mconn)
```
