# HR zone distribution and daily exertion budget.

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/compute/compute_hr_zones.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Distributes heart-rate samples across five zones and computes a daily exertion budget for pacing under dysautonomia/Post-Exertional Malaise (PEM).

## Relevance

Enables heart rate zone analysis, essential for training control

## Method

Four bpm thresholds define five zones (recovery → red zone). The daily budget weights higher-zone samples disproportionately. Thresholds and weights come from clinical.pacing.zone_thresholds_bpm/zone_weights (health_config.json) — ideally taken from a lactate/graded-exercise test, otherwise falling back to percentages of max_hr (clinical.max_hr or traditional rule of thumb). Zone-based pacing is a heuristic method for exertion management in chronic conditions.

## Scoring

```
zones (0..4)   Zone0 <z1 | Zone1 z1-z2 | Zone2 z2-z3 | Zone3 z3-z4 | Zone4 >=z4
budget         sum(zone_samples * zone_weight)
default config zone_thresholds_bpm=[90,105,110,115], zone_weights=[0,1,3,8,20]
```

## Data flow

- **Reads:** `measurements`, `(metric='heart_rate')`
- **Writes:** `daily_hr_zones: samples per zone + daily budget per day and person`

## Limitations

Not a fitness/training model. Zone thresholds are person-specific pacing parameters, not validated clinical cut-offs; meaningfulness depends on correct configuration. Heuristic method.

## References

- Carruthers BM, van de Sande MI, De Meirleir KL et al. (2011). Myalgic encephalomyelitis: International Consensus Criteria. Journal of Internal Medicine, 270(4):327-338. doi:10.1111/j.1365-2796.2011.02428.x
- Institute of Medicine (2015). Beyond Myalgic Encephalomyelitis/Chronic Fatigue Syndrome: Redefining an Illness. National Academies Press, Washington, DC. doi:10.17226/19012
- Ziaks L et al. (2024). Adaptive Approaches to Exercise Rehabilitation for Postural Tachycardia Syndrome and Related Autonomic Disorders. Archives of Rehabilitation Research and Clinical Translation, 6(4):100366. doi:10.1016/j.arrct.2024.100366 (stützt den grundsätzlichen Ansatz personenspezifischer statt starrer Zonengrenzen, nicht die konkreten Zahlenwerte)

## Usage

```bash
python compute_hr_zones.py
python compute_hr_zones.py --from 2025-01-01 --to 2025-12-31
```
