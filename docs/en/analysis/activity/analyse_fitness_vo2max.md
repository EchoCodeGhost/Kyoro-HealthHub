# Fitness & VO2max-Trend

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/analysis/activity/analyse_fitness_vo2max.py`

**Evidence tier:** heuristic (deliberate design from domain knowledge, no formal literature or validation basis)

## Purpose

Analyses aerobic capacity (VO2max) over time from Polar Own Index, two independent Garmin estimation methods (activity-based and biometric) and Oura as a marker for fitness changes.

## Relevance

Enables activity data analysis, essential for movement and fitness analysis

## Method

Collects device-specific VO2max estimates (Polar orthostatic test, Garmin get_training_status().mostRecentVO2Max.generic [activity-based, source_app=garmin_connect] and Garmin fitnessAgeData.biometricVo2Max [biometric, source_app=garmin_gdpr], Oura model) without cross-device or cross-method validation; the two Garmin estimates diverge by ~10 points over the same period and are never averaged, always reported separately. For garmin_connect, only a value change counts as a measurement, since repeated fetches could re-write the same value under a new date. ACSM reference values for classification (>45 / 38–45 / 30–38 / 23–30 / <23 ml/min/kg).

## Scoring

```
VO2max classes (ACSM): >45 excellent | 38-45 very good | 30-38 good | 23-30 fair | <23 poor
Polar Own Index: EXCELLENT | VERY_GOOD | GOOD | ACCEPTABLE | NEEDS_IMPROVEMENT
```

## Data flow

- **Reads:** `assessments`, `measurements`, `oura_vo2max`, `daily_stress`
- **Writes:** `analyses/activity/*.{md,png} (kein DB-Write)`

## Limitations

Heuristic method: VO2max estimates from consumer devices have measurement uncertainties of ±10–20 %. Polar Own Index and the two Garmin methods use different algorithms and, as shown by the divergence between the two Garmin estimates of the same device, have limited reliability. No spiroergometry reference. n=1. Plot reference lines (25 / 35 ml/min/kg) are generic orientation values — ACSM norms are time period- and sex-specific.

## References

- ACSM Guidelines for Exercise Testing and Prescription, 11th ed. 2022
- Myers J, Prakash M, Froelicher V, Do D, Partington S, Atwood JE (2002). Exercise Capacity and Mortality among Men Referred for Exercise Testing. New England Journal of Medicine, 346(11):793-801. doi:10.1056/NEJMoa011858
- Tanaka H, Monahan KD, Seals DR (2001). Age-predicted maximal heart rate revisited. Journal of the American College of Cardiology, 37(1):153-156. doi:10.1016/S0735-1097(00)01054-8
- Gulati M, Black HR, Shaw LJ, et al. (2005). The Prognostic Value of a Nomogram for Exercise Capacity in Women. New England Journal of Medicine, 353(5):468-475. doi:10.1056/nejmoa044154

## Usage

```bash
python analyse_fitness_vo2max.py
python analyse_fitness_vo2max.py --help
python analyse_fitness_vo2max.py --from 2024-01-01 --to 2024-12-31
```
