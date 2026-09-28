# sleep_norms.py — Einheitliche Normbereiche für Schlafstadien (Tiefschlaf, REM)

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/modules/sleep_norms.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Provides ONE shared, cited set of norm ranges for deep-sleep (N3) and REM percentage of total sleep time, used by all analysis scripts instead of each maintaining its own (and contradictory) values.

## Relevance

Deep-sleep and REM percentage are established markers of sleep quality and architecture; one shared, cited norm range prevents the same measured value from being assessed differently (and sometimes contradictorily) depending on which script reports it.

## Method

Pure constants, no computation. Before this consolidation, analyse_sleep_stages.py used 13-18% (deep) / 18-23% (REM), while analyse_sleep_respiration.py used 15-25% / 20-25% for the same fact — two assessments of the same finding. The ranges fixed here (deep 13-23%, REM 18-25%) are chosen so the empirical population mean from the largest published PSG meta-analysis of healthy adults to date (Boulos et al. 2019, n=5273: deep 20.4%, 95% CI 19.0-21.8%; REM 19.0%, 95% CI 18.5-19.6%) falls inside the range — the REM lower bound in particular was deliberately set to 18% (rather than the 20% figure circulating in older textbook summaries): a "normal range" that excludes the empirically measured population mean is by definition miscalibrated.

## Data flow

- **Reads:** `keine`
- **Writes:** `keine`

## Limitations

Boulos et al. 2019 reports the 95% CI of the pooled population MEAN across studies, not the spread between individuals/nights — as an individual prediction interval this CI would be too narrow. The ranges defined here are therefore deliberately wider than the CI and are meant for comparing a personal value averaged over multiple nights against the population mean, not for judging a single night. Wearable sleep staging (Apple Watch, Oura) also has lower accuracy than the PSG that Boulos et al. 2019 is based on.

## References

- Boulos MG, Jairam T, Kendzerska T, Im J, Mekhael A, Murray BJ (2019). Normal polysomnography parameters in healthy adults: a systematic review and meta-analysis. Lancet Respiratory Medicine, 7(6):533-543. doi:10.1016/S2213-2600(19)30057-8 (Tabelle 2 der Publikation: Tiefschlaf/N3 20,4 % [95%-CI 19,0-21,8 %], REM 19,0 % [95%-CI 18,5-19,6 %], Gesamtstichprobe n=5273 gesunde volljährige Personen, 108-158 gepoolte Kontrollgruppen je Parameter.)

## Usage

```bash
from modules.sleep_norms import (
    DEEP_NORM_MIN, DEEP_NORM_MAX, REM_NORM_MIN, REM_NORM_MAX,
)
```
