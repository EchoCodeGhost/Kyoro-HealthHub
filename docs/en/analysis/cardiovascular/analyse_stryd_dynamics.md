# Stryd-Laufdynamik — Herzfrequenz-Leistungs-Missverhältnis pro Session

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/analysis/cardiovascular/analyse_stryd_dynamics.py`

**Evidence tier:** heuristic (deliberate design from domain knowledge, no formal literature or validation basis)

## Purpose

Computes per-Stryd-session power and heart rate metrics, a heart-rate-to-power ratio ("cardiac cost"), and the Pearson correlation between elevation and heart rate within the session.

## Relevance

Objectifies the exertion cost of everyday movement under a pronounced aerobic deficit, complements ergometry-based exercise testing with everyday-life data

## Method

Power (power_wkg) is averaged only over samples with power_wkg>0 (pauses/signal dropouts at 0 W/kg would otherwise artificially skew the average downward). "Cardiac cost" = mean heart rate / mean power (bpm per W/kg) — a self-defined, not clinically validated metric, no substitute for VO2max/lactate threshold testing. Elevation-HR correlation: Pearson correlation (scipy.stats.pearsonr) with a real p-value per session, minimum n=5, results with n<30 flagged "[exploratory]" (same convention as analyse_ans_battery.py).

## Scoring

```
Signifikanz: p<0,05 markiert mit "*" (keine Multiple-Testing-Korrektur)
Stichprobengröße: n<5 kein Ergebnis | n<30 "[explorativ]"-Hinweis | n>=30 unmarkiert
```

## Data flow

- **Reads:** `stryd_sessions`, `stryd_samples`
- **Writes:** `analyses/cardiovascular/*.{md,png}`

## Limitations

"Cardiac cost" is a self-defined, not clinically validated heuristic — no established reference ranges, no diagnostic claim. Elevation-HR correlation explains only part of the HR variation, not the overall HR level; confounds such as ambient temperature are not controlled for (Stryd elevation/wrist temperature sensors are also unreliable for ambient temperature — body-heat artifact, see session notes). Balance metrics (ground time/vertical oscillation/leg spring stiffness/impact loading rate balance) remain unevaluated since they require a dual-footpod setup and are consistently 0 with a single pod. Plot shows only the most recently imported session in range, not a multi-session trend.

## References

- Cavagna GA, Kaneko M (1977). Mechanical work and efficiency in level walking and running. The Journal of Physiology, 268(2):467-481. doi:10.1113/jphysiol.1977.sp011866 (Referenzbereich für Gehen/Laufen-Leistung)

## Usage

```bash
python analyse_stryd_dynamics.py
python analyse_stryd_dynamics.py --plot
python analyse_stryd_dynamics.py --from 2026-01-01 --to 2026-12-31
python analyse_stryd_dynamics.py --no-llm
python analyse_stryd_dynamics.py --lang en
```
