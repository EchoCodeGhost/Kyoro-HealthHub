# Gefäßgesundheit — Überblick vaskulärer Parameter aus Wearable-Quellen

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/analysis/cardiovascular/analyse_vascular_health.py`

**Evidence tier:** heuristic (deliberate design from domain knowledge, no formal literature or validation basis)

## Purpose

Overview analysis of vascular wearable parameters: SpO2, resting HR, activity, skin temperature, respiratory rate, pulse wave velocity, body weight and Oura recovery score.

## Relevance

Enables cardiovascular analysis, essential for cardiac diagnostics

## Method

Monthly aggregation and trend calculation per parameter; comparison against clinical reference ranges (ESC 2018 PWV <10 m/s, resting HR 50–90 bpm); Pearson correlation between parameters.

## Scoring

```
SpO2: normal >=95% | mild 90-95% | moderate 85-90% | severe <85%
PWV: normal <10 m/s | elevated 10-12 m/s | high >12 m/s (ESC 2018)
Resting HR: normal 60-100 bpm | bradycardic <60 | tachycardic >100 (AHA)
```

## Data flow

- **Reads:** `measurements`, `daily_stress`, `oura_temperature_raw`, `oura_daytime_stress`, `body_composition`
- **Writes:** `analyses/cardiovascular/*.{md,png}`

## Limitations

Heuristic method: Wearable-based PWV (Polar PTT) is not clinically validated for vascular stiffness; ESC reference applies to applanation tonometry (Mancia 2013). Validated norms: SpO2 <95% (WHO/ESC), resting HR 60-100 bpm (AHA), respiratory rate 12-20/min, WHtR >=0.5 (Ashwell 2016). Visceral fat thresholds (>13 elevated, >17 high) are device-manufacturer classifications, not WHO/clinical standards. Analysis is descriptive without causal hypotheses.

## References

- Williams B, Mancia G, Spiering W et al. (2018). 2018 ESC/ESH Guidelines for the management of arterial hypertension. European Heart Journal, 39(33):3021-3104. doi:10.1093/eurheartj/ehy339
- Mancia G, Fagard R, Narkiewicz K et al. (2013). 2013 ESH/ESC Guidelines for the management of arterial hypertension. European Heart Journal, 34(28):2159-2219. doi:10.1093/eurheartj/eht151 (PWV-Klassifikation)
- Ashwell M, Gibson S (2016). Waist-to-height ratio as an indicator of 'early health risk'. BMJ Open, 6(3):e010159. doi:10.1136/bmjopen-2015-010159 (WHtR ≥0.5)

## Usage

```bash
python analyse_vascular_health.py
python analyse_vascular_health.py --help
python analyse_vascular_health.py --from 2024-01-01 --to 2024-12-31
```
