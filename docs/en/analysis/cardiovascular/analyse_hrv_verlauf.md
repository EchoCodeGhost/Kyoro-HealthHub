# HRV-Verlauf (RMSSD) mit Ereignismarkern — Arzttermin-Export

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/analysis/cardiovascular/analyse_hrv_verlauf.py`

**Evidence tier:** heuristic (deliberate design from domain knowledge, no formal literature or validation basis)

## Purpose

Creates monthly RMSSD trend chart with configured event markers for cardiology or other medical appointments.

## Relevance

Enables cardiovascular analysis, essential for cardiac diagnostics

## Method

Reads monthly RMSSD averages from measurements (min. 5 measurement days/month). Draws event lines from clinical.events (type: infection, reinfection). Calculates pre/post baseline relative to first/last event. Reports total percentage decline. Saves as PDF to analyses/<date>/.

## Scoring

```
Prozentualer Rueckgang: (baseline_pre − baseline_post) / baseline_pre × 100;
kein klinischer Grenzwert, projektintern zur Verlaufsorientierung.
```

## Data flow

- **Reads:** `measurements`, `(metric=hrv_rmssd)`
- **Writes:** `analyses/cardiovascular/<YYYY-MM-DD>/hrv_cardiology_<datum>.{pdf,md}`

## Limitations

Heuristic visualization. Not a clinical diagnostic tool. Monthly granularity: daily outliers are averaged out. Minimum 5 measurement days per month required.

## References

- Task Force of the European Society of Cardiology and the North American Society of Pacing and Electrophysiology (1996). Heart rate variability: standards of measurement, physiological interpretation, and clinical use. Circulation, 93(5), 1043-1065. doi:10.1161/01.CIR.93.5.1043
- Shaffer F, Ginsberg JP (2017). An overview of heart rate variability metrics and norms. Frontiers in Public Health, 5:258. doi:10.3389/fpubh.2017.00258

## Usage

```bash
python3 scripts/analysis/cardiovascular/analyse_hrv_verlauf.py
python3 scripts/analysis/cardiovascular/analyse_hrv_verlauf.py --from 2023-01-01
python3 scripts/analysis/cardiovascular/analyse_hrv_verlauf.py --out /tmp/hrv.pdf
```
