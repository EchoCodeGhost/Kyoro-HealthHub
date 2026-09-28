# Body composition & Weightsverlauf

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/analysis/metabolic/analyse_body_composition.py`

**Evidence tier:** heuristic (deliberate design from domain knowledge, no formal literature or validation basis)

## Purpose

Analyses weight, body fat percentage, muscle mass and waist circumference from FDDB, Apple Health and Beurer over multiple years, plus associations with blood glucose and training data.

## Relevance

Enables metabolic analysis, essential for metabolic health

## Method

Descriptive statistics and visual time series; no formally validated body fat reference ranges implemented. Beurer bioimpedance segmental values are displayed without device calibration verification.

## Scoring

```
BMI: Untergewicht <18,5 / Normal 18,5–24,9 / Übergewicht 25–29,9 / Adipositas ≥30
WHR: erhöht ≥0,90 (Personengruppen) / ≥0,85 (Personengruppen)
WHtR: erhöht ≥0,50
HbA1c: erhöht >5,7%  |  Nüchternglukose: erhöht ≥6,1 mmol/L
Basis: BMI/WHR = WHO (doi:https://iris.who.int/handle/10665/42330), WHtR = Ashwell & Gibson 2016
(doi:10.1136/bmjopen-2015-010159), HbA1c = ADA 2023, IFG = WHO 2006.
Viszeralfett >13, Segmentasymmetrie-Schwellen: projektintern (Beurer-Skala).
```

## Data flow

- **Reads:** `body_composition`, `(incl.`, `source='renpho_csv')`, `measurements`, `blood_glucose`, `nutrition_daily`, `sessions`, `session_metrics`
- **Writes:** `analyses/metabolic/*.{md,png} (kein DB-Write)`

## Limitations

Heuristic method: Validated components: BMI (WHO 2000), WHR (WHO 2008), WHtR ≥ 0.50 (Ashwell & Gibson 2016, doi:10.1136/bmjopen-2015-010159), HbA1c > 5.7% (ADA 2023), fasting glucose ≥ 6.1 mmol/L (WHO 2006 IFG). Heuristic components: visceral fat index > 13 (Beurer BF990-proprietary, not transferable to other devices), segmental asymmetry thresholds (2.0% fat / 1.5% muscle), metabolic time period (Beurer-proprietary). Bioimpedance readings vary greatly with hydration status. Multiple devices (FDDB, Apple, Beurer) may show systematic offsets. No reference population. Glucose average may include postprandial values — not a fasting-only measure.

## References

- WHO (2000). Obesity: preventing and managing the global epidemic. Technical Report Series 894. doi:https://iris.who.int/handle/10665/42330
- WHO (2008). Waist circumference and waist-hip ratio. WHO Expert Consultation.
- Ashwell M, Gibson S (2016). Waist-to-height ratio as an indicator of 'early health risk'. doi:10.1136/bmjopen-2015-010159
- ADA (2023). Standards of Care in Diabetes — Classification and assessment. doi:10.2337/dc23-S002
- WHO (2006). Definition and assessment of diabetes mellitus and intermediate hyperglycaemia. ISBN 978 92 4 159493 6

## Usage

```bash
python analyse_body_composition.py
python analyse_body_composition.py --help
python analyse_body_composition.py --from 2024-01-01 --to 2024-12-31
```
