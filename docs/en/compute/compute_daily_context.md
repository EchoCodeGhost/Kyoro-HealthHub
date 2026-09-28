# compute_daily_context.py — Tages-Kontexttabelle aggregieren

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/compute/compute_daily_context.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Materialises a wide daily context table (one row per date+person) aggregated from all health data domains.

## Relevance

Enables calculation of daily context data, essential for long-term analysis

## Method

Date spine from all populated tables; per-domain Python dicts; merge by date; INSERT OR IGNORE. Symptoms and medications aggregated as JSON. Travel: cfg.travel_history date ranges checked against the spine, travel_active=1 if the date falls within a trip. Infection proximity: cfg.events_of_type('infection', 'reinfection') — days_since_infection is the signed day distance to the NEAREST infection/reinfection event (negative = event is still in the future), NULL if no infection events are configured. No fixed "acute phase" window assumed — interpreting closeness is left to downstream analysis to avoid picking an unjustified window length.

## Data flow

- **Reads:** `health_canonical`, `sessions`, `session_metrics`, `cgm_readings`, `blood_pressure`, `af_evidence_scores`, `body_composition`, `pollen`, `air_quality`, `weather_station`, `symptoms_canonical`, `medications`, `cfg.travel_history`, `cfg.events_of_type('infection'`, `'reinfection')`, `pem_evidence_scores`, `oura_daytime_stress`, `nutrition_daily`, `daily_energy_summary`
- **Writes:** `daily_context`

## Limitations

Consumer wearables without clinical validation. Missing days → NULL (no imputation). CGM TIR only if ≥67 readings/day (≥70 % at 15-min sampling, Battelino 2019 doi:10.2337/dc18-1581). Multiple sleep sessions per day → session with longest duration selected as primary; all metrics from that session. oura_daytime_stress has no person column → not populated.

## References

- (keine Algorithmen aus Literatur — nur Aggregation)

## Usage

```bash
python compute_daily_context.py
python compute_daily_context.py --help
python compute_daily_context.py --from 2024-01-01 --to 2024-12-31
```
