# Hohe Heart rate-Ereignisse — Kontextklassifikation

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/analysis/cardiovascular/analyse_high_hr.py`

**Evidence tier:** heuristic (deliberate design from domain knowledge, no formal literature or validation basis)

## Purpose

Analyses Apple Watch High HR events for frequency, time-of-day patterns, temporal trends and likely context (orthostatic, post-exertional, arrhythmia-correlated, unexplained) — not limited to resting tachycardia/autonomic dysregulation, since elevated-HR events have multiple possible causes.

## Relevance

Enables cardiovascular analysis, essential for cardiac diagnostics

## Method

Aggregation of Apple Health high-HR events; per-event classification by temporal overlap/context with (1) orthostatic sessions (sessions.type='orthostatic', ΔHR threshold), (2) training sessions (sessions.type='training', post-exercise window), (3) detected arrhythmia episodes (arrhythmie_episoden, buffered time window); everything else = unexplained. Threshold >120 bpm per Apple Watch default.

## Scoring

```
HR threshold: >120 bpm (Apple Watch default)
POTS criterion: ΔHR >=30 bpm (validated) | 15-29 bpm borderline (heuristic)
Post-exertional window: within 180 min after a training session's end
Arrhythmia-correlation buffer: ±15 min around an arrhythmie_episoden window
```

## Data flow

- **Reads:** `apple_records`, `clinical_findings`, `sessions`, `session_metrics`, `arrhythmie_episoden`, `measurements`, `symptoms`
- **Writes:** `analyses/cardiovascular/high_hr_*.{md,png}`

## Limitations

Heuristic method: Apple Watch threshold (>120 bpm) is device-specific and not clinically validated; context classification is a time-window correlation, not a causal or clinical assignment — "unexplained" means only "no recognised trigger in the available data", not "IST" or any other named diagnosis. Orthostatic sessions only present if a real test/evaluation took place. POTS criterion ≥30 bpm is validated (Sheldon 2015, doi:10.1016/j.hrthm.2015.03.029); 15–29 bpm borderline range is heuristic/project-internal without literature support. Arrhythmia correlation only checks temporal overlap with compute_arrhythmia.py output, no independent signal analysis.

## References

- Sheldon RS, Grubb BP 2nd, Olshansky B, et al. (2015). 2015 Heart Rhythm Society expert consensus statement on the diagnosis and treatment of postural tachycardia syndrome, inappropriate sinus tachycardia, and vasovagal syncope. Heart Rhythm, 12(6), e41-e63. doi:10.1016/j.hrthm.2015.03.029 (POTS/IST: ΔHR ≥30 bpm supine→standing)
- Cooney MT, Vartiainen E, Laakitainen T, Juolevi A, Dudina A, Graham IM (2010). Elevated resting heart rate is an independent risk factor for cardiovascular disease in healthy men and women. American Heart Journal, 159(4), 612-619.e3. doi:10.1016/j.ahj.2009.12.029 (elevated resting HR as a cardiovascular risk marker, independent of orthostatic cause — motivates tracking event frequency/trend even in the "unexplained" bucket)
- Brugada J, Katritsis DG, Arbelo E, et al. (2020). 2019 ESC Guidelines for the management of patients with supraventricular tachycardia. European Heart Journal, 41(5), 655-720. doi:10.1093/eurheartj/ehz467 (differential-diagnosis awareness for arrhythmia-correlated events; this script does not itself diagnose SVT)

## Usage

```bash
python analyse_high_hr.py
python analyse_high_hr.py --help
python analyse_high_hr.py --from 2024-01-01 --to 2024-12-31
```
