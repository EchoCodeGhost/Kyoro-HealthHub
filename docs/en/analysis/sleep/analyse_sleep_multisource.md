# Sleep-Multisource-Analyse (v2)

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/analysis/sleep/analyse_sleep_multisource.py`

**Evidence tier:** calibrated (literature-based + parameters tuned to personal baselines, no external validation)

## Purpose

Combines and compares sleep architecture from Polar, Sleep Cycle and Apple Watch with bedroom environment data for a multi-source sleep analysis.

## Relevance

Enables sleep analysis, essential for sleep research and health monitoring

## Method

Aggregates session_metrics of sleep sessions per source; Pearson correlation between sleep parameters; environment data limited to the actual sleep window via home_environment_ts.

## Data flow

- **Reads:** `sessions`, `session_metrics`, `sleep_hypnogram`, `home_environment_ts`
- **Writes:** `analyses/sleep/*.{md,png}`

## Limitations

Sleep staging quality depends on each device algorithm (proprietary, not AASM-certified). Cross-source comparison is indicative only; no gold-standard validation.

## References

- Iber C, Ancoli-Israel S, Chesson AL, Quan SF (2007). The AASM Manual for the Scoring of Sleep and Associated Events: Rules, Terminology and Technical Specifications (1st ed.). American Academy of Sleep Medicine, Westchester, IL. (kein DOI verfügbar, Handbuch)
- Goldstone A, Baker FC, de Zambotti M (2018). Actigraphy in the digital health revolution: still asleep? Sleep, 41(9). doi:10.1093/sleep/zsy120

## Usage

```bash
python analyse_sleep_multisource.py
python analyse_sleep_multisource.py --help
python analyse_sleep_multisource.py --from 2024-01-01 --to 2024-12-31
```
