# Funktionale Kapazität — 6-Minuten-Gehtest (6MWT) Verlaufsanalyse

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/analysis/activity/analyse_functional_capacity.py`

**Evidence tier:** validated (clinical validation study exists: sensitivity/specificity or endpoints prospectively established)

## Purpose

Analyses 6-minute walk tests (6MWT) as an objective outcome measure: walking distance, HR kinetics (rest → peak → recovery), SpO2 drop, Borg exertion and PEM risk the following day.

## Relevance

Enables activity data analysis, essential for movement and fitness analysis

## Method

Reference value per Enright & Sherrill 1998 (regression equation from age, height, weight, and a configuration trait selecting between two coefficient sets — see _predicted_6mwt_m() in the source), personalised via health_config.json and the most recently known weight from body_composition/measurements. If any of these is missing, the ATS 2002 generic point estimate (~45y, 170cm, ~560m) is used as a fallback — the report always states which mode was used. MCID 30 m per Singh et al. 2014. Severity classification: < 40 % severe, 40–60 % moderate, 60–80 % mild, ≥ 80 % normal.

## Data flow

- **Reads:** `functional_tests`, `measurements`
- **Writes:** `analyses/activity/*.{md,png} (kein DB-Write)`

## Limitations

Self-administered 6MWT without standardised test conditions (corridor, instructions). Enright & Sherrill 1998 was validated on a predominantly healthy US adult cohort, not ME/CFS/Long-COVID populations. Weight is the most recently known measurement, not necessarily current. Without complete configuration (age/height/profile trait/weight), the value falls back to the generic ATS 2002 point estimate, which is only reliable for people close to 45y/170cm. n=1.

## References

- American Thoracic Society (2002). ATS Statement: Guidelines for the Six-Minute Walk Test. American Journal of Respiratory and Critical Care Medicine, 166(1):111-117. doi:10.1164/ajrccm.166.1.at1102
- Enright PL, Sherrill DL (1998). Reference Equations for the Six-Minute Walk in Healthy Adults. American Journal of Respiratory and Critical Care Medicine, 158(5):1384-1387. doi:10.1164/ajrccm.158.5.9710086
- Singh SJ, Puhan MA, Andrianopoulos V, et al. (2014). An official systematic review of the European Respiratory Society/American Thoracic Society: measurement properties of field walking tests in chronic respiratory disease. European Respiratory Journal. doi:10.1183/09031936.00150414

## Usage

```bash
python analyse_functional_capacity.py
python analyse_functional_capacity.py --help
python analyse_functional_capacity.py --from 2024-01-01 --to 2024-12-31
```
