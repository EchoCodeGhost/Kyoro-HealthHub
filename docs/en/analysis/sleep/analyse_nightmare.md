# analyse_nightmare.py — Alptraum-Alarm-Analyse (Kyoro SleepGuard)

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/analysis/sleep/analyse_nightmare.py`

**Evidence tier:** experimental (exploratory, no stable conceptual foundation, hypothesis-generating)

## Purpose

Analyses nightmare alarms from the Kyoro SleepGuard watch app: frequency, time-of-night distribution, HR delta, and clinical RBD screening flag.

## Relevance

Enables sleep analysis, essential for sleep research and health monitoring

## Method

Reads nightmare_hr / nightmare_baseline from measurements; aggregates per night; detects consecutive nights (≥3 = RBD flag); compares next-morning HRV between alarm and quiet nights.

## Data flow

- **Reads:** `measurements`, `(nightmare_hr`, `nightmare_baseline`, `rmssd`, `hrv_rmssd)`
- **Writes:** `analyses/sleep/nightmare_report.txt, analyses/sleep/nightmare_analysis.png`

## Limitations

HR-based nightmare detection is heuristic; elevations can also arise from normal sleep tachycardia. Wearable HR has PPG artefacts. Not a substitute for polysomnography.

## References

- Schenck CH, Boeve BF, Mahowald MW (2013). Delayed emergence of a parkinsonian disorder or dementia in 81% of older men initially diagnosed with idiopathic rapid eye movement sleep behavior disorder: a 16-year update on a previously reported series. Sleep Medicine, 14(8):744-748. doi:10.1016/j.sleep.2012.10.009
- Postuma RB, Gagnon JF, Vendette M, Fantini ML, Massicotte-Marquez J, Montplaisir J (2009). Quantifying the risk of neurodegenerative disease in idiopathic REM sleep behavior disorder. Neurology, 72(15):1296-1300. doi:10.1212/WNL.0b013e3181a52fbe

## Usage

```bash
python3 scripts/analysis/sleep/analyse_nightmare.py
python3 scripts/analysis/sleep/analyse_nightmare.py --lang en
```
