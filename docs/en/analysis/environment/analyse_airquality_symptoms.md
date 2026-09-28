# Luftqualität × Symptome & Migräne

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/analysis/environment/analyse_airquality_symptoms.py`

**Evidence tier:** heuristic (deliberate design from domain knowledge, no formal literature or validation basis)

## Purpose

Investigates associations between air quality parameters (PM2.5, PM10, NO2, O3, AQI) and symptom categories as well as migraine attacks with lag analysis.

## Relevance

Enables correlation of air quality data with individual symptoms, essential for identifying environment-related health triggers and developing personalized prevention strategies

## Method

Spearman rank correlation without multiple-testing correction; Personen-Whitney U for group comparisons; custom p-value thresholds without prior published validation.

## Scoring

```
Air quality levels: good 0-50 | moderate 51-100 | unhealthy 101-150 | very unhealthy 151-200 | hazardous >200 (AQI)
Lag analysis: 0-3 days before migraine/symptom onset
Correlation strength: |r| <0.2 weak | 0.2-0.4 moderate | 0.4-0.7 strong | >0.7 very strong
```

## Data flow

- **Reads:** `air_quality`, `symptoms`, `sessions`
- **Writes:** `analyses/environment/*.{md,png} (kein DB-Write)`

## Limitations

Heuristic method: No confounder control, no multiple-testing correction. n=1, consumer sensor data for air quality. Correlations are exploratory only.

## References

- World Health Organization (2006). Air quality guidelines for particulate matter, ozone, nitrogen dioxide and sulfur dioxide: global update 2005, summary of risk assessment. Geneva: WHO. https://iris.who.int/handle/10665/69477
- Brook RD, Rajagopalan S, Pope CA et al. (2010). Particulate Matter Air Pollution and Cardiovascular Disease. Circulation, 121(21):2331-2378. doi:10.1161/CIR.0b013e3181dbece1

## Usage

```bash
python analyse_airquality_symptoms.py
python analyse_airquality_symptoms.py --help
python analyse_airquality_symptoms.py --from 2024-01-01 --to 2024-12-31
```
