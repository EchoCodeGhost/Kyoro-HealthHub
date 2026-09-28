# Mehrdimensionaler Energiehaushalt — Gesamtpensum.

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/compute/compute_gesamtpensum.py`

**Evidence tier:** heuristic (deliberate design from domain knowledge, no formal literature or validation basis)

## Purpose

Combines physical HR load (daily_hr_zones.tagespensum) with subjective domain scores (activity_log: sensory, cognitive, social, plus subjective-physical and emotional) into a weighted total energy budget. Classifies each day into three load levels: green / yellow / red.

## Relevance

Enables calculation of total workload, essential for activity analysis

## Method

gesamtpensum = tagespensum × w_physical + physical_load_subjective × scale × w_physical_subjective + sensory_load × scale × w_sensory + cognitive_load × scale × w_cognitive + social_effort × scale × w_social + emotional_load × scale × w_emotional. Weights and scale factor from health_config.json (clinical.pacing). Days without activity_log entry receive the physical component only, days without daily_hr_zones entry (e.g. wearable sync lag) only the subjective one — the day list is the union of both sources, not a plain LEFT JOIN from daily_hr_zones, otherwise self-report-only days would be missing entirely. physical_load_subjective (self-report, e.g. blue-ME koerperlicheBelastungen) is added ON TOP OF tagespensum (objective, HR zones/sport), not instead of it — covers days with no detectable training session/HR rise but real physical exertion (e.g. personal hygiene during severe fatigue), see also compute_activity_log_from_symptoms.py.

## Scoring

```
gesamtpensum = tagespensum * w_physisch + physical_load_subjective * scale * w_physisch_subjektiv +
               sensory_load * scale * w_sensorisch + cognitive_load * scale * w_kognitiv +
               social_effort * scale * w_sozial + emotional_load * scale * w_emotional
```

## Thresholds

| Value | Meaning |
|---|---|
| `grün` | gesamtpensum < yellow threshold (default 800) — recovery possible |
| `gelb` | between yellow and red threshold (default 800–1400) — elevated risk |
| `rot` | gesamtpensum ≥ red threshold (default 1400) — high risk |

## Data flow

- **Reads:** `daily_hr_zones`, `activity_log`
- **Writes:**

  ```
  daily_energy_summary: date, person, physical_load,
  physical_load_subjective, sensory_load, cognitive_load,
  social_effort, emotional_load, gesamtpensum, level
  ```

## Limitations

Heuristic method: Subjective scores (1–10) are not validated; no reference norms. Scale factor (default 30) is arbitrary — calibrate from personal data after a few weeks in health_config.json. Same applies to the new weights w_physical_subjective/w_emotional (default 0.6/0.7, modelled on w_sensory/w_social, not a published value). No data flow into compute_arrhythmia, compute_ppi_dfa etc.

## References

- Davenport TE, Stevens SR, VanNess MJ, Snell CR, Little T (2010). Conceptual model for physical therapist management of chronic fatigue syndrome/myalgic encephalomyelitis. Physical Therapy, 90(4):602-614. doi:10.2522/ptj.20090047
- Jason LA, Brown M, Brown A, Evans M, Flores S, Grant-Holler E, Sunnquist M (2013). Energy conservation/envelope theory interventions. Fatigue: Biomedicine, Health & Behavior, 1(1-2):27-42. doi:10.1080/21641846.2012.733602

## Usage

```bash
python compute_gesamtpensum.py
python compute_gesamtpensum.py --recompute
```
