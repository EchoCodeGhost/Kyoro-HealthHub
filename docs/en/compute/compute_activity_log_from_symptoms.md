# PWA-Symptome → activity_log — Brücke für die Belastungsdomänen-Kette.

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/compute/compute_activity_log_from_symptoms.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Bridges the daily sensory/cognitive/social/physical/emotional exertion scales from the symptoms table (PWA and other sources such as blue-ME) into activity_log, so the long-finished compute_gesamtpensum.py → daily_energy_summary → analyse_energy_domains.py chain gets real data outside the wearable-based physical domain too.

## Relevance

Closes the exertion-domain gap (sensory/cognitive/social) that an earlier consult pacing evaluation flagged as blocking

## Method

Reads sensorischer_overload → sensory_load, kognitive_last → cognitive_load, soziale_last → social_effort (daily mean if multiple entries of the same symptom exist for one day). Both spellings found in the symptom history are recognized (the raw id like "sensorischer_overload" and the older human-readable label like "Sensorischer Overload") — the schema switched to plain ids in June 2026, older entries still carry the label form. Additionally: koerperlicheBelastungen → physical_load_subjective, emotionaleBelastungen → emotional_load (blue-ME raw field names, see import_blue_me.py). physical_load_subjective complements the wearable-based physical_load in daily_energy_summary (both feed in separately weighted, see compute_gesamtpensum.py) rather than replacing it, since self-report covers days with no detectable training session/HR rise (e.g. personal hygiene during severe fatigue), while the wearable signal conversely covers days without a self-report entry. masking_aufwand is deliberately NOT treated as equivalent to sensorischer_overload (different concepts: sensory overload vs. the effort of social adaptation), but contributes partially (factor 0.3) to social_effort, since masking is a social adaptation behaviour. INSERT OR REPLACE per (date, person) — activity_log has only one row per day per its schema (source is not part of the primary key), so re-running this fully replaces its own prior bridge output, without touching rows written by other sources (e.g. the manual YAML workflow) as long as their days don't overlap.

## Data flow

- **Reads:** `symptoms`
- **Writes:** `activity_log`

## Limitations

Heuristic method: the masking weighting factor (0.3) is an own choice, not a published value. Days without a PWA entry are left untouched (no fallback to 0 — 0 would be a false measurement, not a missing one).

## Usage

```bash
python3 scripts/compute/compute_activity_log_from_symptoms.py
python3 scripts/compute/compute_activity_log_from_symptoms.py --lang en
```
