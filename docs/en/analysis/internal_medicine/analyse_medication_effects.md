# Substanz-Effekt-Analyse

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/analysis/internal_medicine/analyse_medication_effects.py`

**Evidence tier:** heuristic (deliberate design from domain knowledge, no formal literature or validation basis)

## Purpose

Analyses the effect of substances on body weight, resting heart rate, overnight HRV, blood glucose and documented effects in the temporal context of their start.

## Relevance

Enables health data analysis, essential for medical diagnostics

## Method

Medication history: `medications` (DB) takes precedence as the structured, per-dose logged source; if that table is empty, `clinical.events` from the configuration is used as a fallback (free-text events of type medication_start, plus dose-change/ discontinuation entries filed under the catch-all type other, recognised via generic dose/discontinuation vocabulary). Every event carries its provenance (documented vs. inferred/estimated date) into the report. For resting heart rate and overnight HRV (one value/day, device-agnostic via modules/metric_loader): before/after means in a symmetric window around each event date, ranked against the same computation run on gridded comparison dates across the same period (percentile of the control distribution) — without this ranking an already-running trend would be indistinguishable from an effect tied to the event date. Linear trend (slope kg/week) for body weight.

## Scoring

```
Weight trend: slope <0 weight loss | slope >0 weight gain (kg/week)
Before/after: post-window mean minus pre-window mean, ranked as a percentile
of the same statistic computed at gridded control dates in the same period
```

## Data flow

- **Reads:** `medications`, `clinical.events`, `(health_config)`, `body_composition`, `symptoms`, `measurements`, `blood_glucose`
- **Writes:** `analyses/internal_medicine/medication_effects_*.{md,png}`

## Limitations

Heuristic method: no control-group design in the clinical sense (the control distribution comes from the same n=1 time series, not from a second person); causal attribution is not possible even when an effect falls outside the control distribution. An inferred/estimated event date always caps the confidence of the corresponding statement at the most cautious level. Detection of dose-change/discontinuation entries filed under the catch-all type other relies on generic German vocabulary (e.g. "Dosissteigerung", "abgesetzt") and can miss differently worded entries. Weight trajectory can be confounded by many factors; blood glucose as spot measurements only.

## References

- Choi SW, Wong GTC (2018). Quality improvement studies - pitfalls of the before and after study design. Anaesthesia, 73(11):1432-1435. doi:10.1111/anae.14451 (Limitationen unkontrollierter Vorher/Nachher-Vergleiche — Begründung für die gerasterte Kontrollverteilung unten)
- Doshi P, Dickersin K, Healy D, Vedula SS, Jefferson T (2013). Restoring invisible and abandoned trials: a call for people to publish the findings. BMJ, 346, f2865. doi:10.1136/bmj.f2865

## Usage

```bash
python analyse_medication_effects.py
python analyse_medication_effects.py --help
python analyse_medication_effects.py --from 2024-01-01 --to 2024-12-31
```
