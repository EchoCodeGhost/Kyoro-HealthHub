# Mehrdimensionales Energiemanagement — Domänenanalyse.

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/analysis/activity/analyse_energy_domains.py`

**Evidence tier:** heuristic (deliberate design from domain knowledge, no formal literature or validation basis)

## Purpose

Analyses multidimensional energy management: physical HR load combined with subjective scores for sensory, cognitive and social burden, plus next-day correlations with HRV and reaction patterns.

## Relevance

Enables activity data analysis, essential for movement and fitness analysis

## Method

Reads total load from compute_gesamtpensum-generated daily_energy_summary; domain scores from activity_log (0-10, subjective). Traffic-light thresholds (yellow >= 400, red >= 700) configurable, not formally validated. Data sources: daily_energy_summary, daily_hr_zones, activity_log, sessions, measurements (hrv_rmssd)

## Scoring

```
Level: grün <400 / gelb 400–699 / rot ≥700 (Gesamtpensum-Einheiten)
Domänen-Gewichte: körperlich 1,0 / kognitiv 0,8 / sozial 0,7 / sensorisch 0,6
Schwellen und Gewichte sind konfigurierbar (health_config.json)
Basis: projektintern — kein publizierter Schwellenwert
```

## Data flow

- **Reads:** `daily_energy_summary`, `daily_hr_zones`, `activity_log`, `sessions`, `measurements`, `(hrv_rmssd)`, `pem_evidence_scores`
- **Writes:** `analyses/activity/*.{md,png} (kein DB-Write)`

## Limitations

Heuristic method: Subjective domain scores (sensory, cognitive, social) are not standardised and strongly dependent on self-assessment. Total load formula is project-internal, no published validation. n=1. All thresholds (yellow/red) are heuristic.

## References

- Jason LA, Brown M, Brown A, Evans M, Flores S, Grant-Holler E, Sunnquist M (2013). Energy conservation/envelope theory interventions. Fatigue: Biomedicine, Health & Behavior. doi:10.1080/21641846.2012.733602
- Davenport TE, Stevens SR, VanNess MJ, Snell CR, Little T (2010). Conceptual Model for Physical Therapist Management of Chronic Fatigue Syndrome/Myalgic Encephalomyelitis. Physical Therapy, 90(4):602-614. doi:10.2522/ptj.20090047

## Usage

```bash
python analyse_energy_domains.py
python analyse_energy_domains.py --help
python analyse_energy_domains.py --from 2024-01-01 --to 2024-12-31
```
