# Gangbild & Neurologie (Apple Watch)

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/analysis/neurology/analyse_gait.py`

**Evidence tier:** heuristic (deliberate design from domain knowledge, no formal literature or validation basis)

## Purpose

Analyses Apple Watch gait parameters (walking steadiness, asymmetry, speed, step length) as long-term neurofunction markers with correlation to HRV and energy.

## Relevance

Enables neurological analysis, essential for nervous system diagnostics

## Method

Daily average of Apple Health metrics; Spearman correlation with HRV/symptoms. Reference values: steadiness ≥ 75 % = OK (Apple's own definition), speed > 1.2 m/s = normal (literature reference). No independent laboratory validation.

## Scoring

```
Walking steadiness: >=75% OK | 60-75% low | <60% very low (Apple definition)
Walking speed: >1.2 m/s normal | 0.8-1.2 m/s borderline | <0.8 m/s community-limited
Asymmetry: lower = better balance
Correlation strength: |r| <0.2 weak | 0.2-0.4 moderate | 0.4-0.7 strong | >0.7 very strong
```

## Data flow

- **Reads:** `measurements`, `(walking_steadiness`, `walking_asymmetry`, `walking_speed`, `walking_step_length)`, `daily_stress`, `symptoms`
- **Writes:** `analyses/neurology/*.{md,png} (kein DB-Write)`

## Limitations

Heuristic method: Gait parameters from consumer wearable are less precise than laboratory gait measurements. Walking steadiness algorithm is proprietary. Confounding by activity type (walking vs. running). n=1.

## References

- Fritz S, Lusardi M (2009). White Paper: "Walking Speed: the Sixth Vital Sign". Journal of Geriatric Physical Therapy, 32(2):2-5. doi:10.1519/00139143-200932020-00002 (walking speed functional limits: <0.8 m/s = community-limited)
- Bohannon RW 1997, Gait Posture 7(2):167-168 (normal comfortable speed ~1.2 m/s)

## Usage

```bash
python analyse_gait.py
python analyse_gait.py --help
python analyse_gait.py --from 2024-01-01 --to 2024-12-31
```
