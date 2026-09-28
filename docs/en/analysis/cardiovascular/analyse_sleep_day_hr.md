# Schlaf- vs. Tag-Herzfrequenz-Vergleich

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/analysis/cardiovascular/analyse_sleep_day_hr.py`

**Evidence tier:** heuristic (deliberate design from domain knowledge, no formal literature or validation basis)

## Purpose

Compares average heart rate during real, device-recorded sleep periods against the heart rate in the following waking hours of the same day, across the entire recording period. Goal: surface whether/when the normal day/night gap (sleep clearly lower than day) narrows -- a recognised marker of autonomic dysregulation (reduced nocturnal parasympathetic recovery).

## Relevance

Surfaces a long-term autonomic recovery trend that lines up with the clinically documented ECG finding and the orthostatic candidate trend (s. compute_orthostatic_detection.py) -- an independent, methodologically separate line of evidence.

## Method

Sleep window: primarily Polar sleep sessions (sessions.type='sleep', id LIKE 'polar%') with a real ts_end -- checked against the other available sources: in this DB, Garmin sleep sessions consistently have ts_start=midnight and ts_end=NULL (pure date placeholders, no real time window), Oura has ts_end but only from May 2026 onward (too short a history for a trend comparison). For nights WITHOUT a Polar session (e.g. a period when a different device was primarily worn) an approximate window is derived from Apple Health 'sleep_analysis' stage samples, s. APPLE_SLEEP_GAP_HOURS/_derive_apple_sleep_nights() -- these nights are called out separately as n(Apple) in the report since they are NOT a device-computed sleep interval, only min/max of the sample timestamps within a detected night episode. Day window: the DAY_WINDOW_HOURS hours right after sleep end (ts_end), NOT the full calendar day -- avoids overlap with the next sleep phase and keeps the sleep/day windows comparable for the same transition. Heart rate from measurements (metric='heart_rate'); for the sleep window and 'day_raw' ALL sources (Polar, Apple, Garmin, Oura, ...) -- collapsed per minute via device_registry.collapse_concurrent() to one device when more than one reports for that minute (Rule B of the cross-cutting-conventions spec: priority winner, not averaging -- otherwise periods with more devices worn at once would be weighted more heavily than periods with only one device). 'day_rest' (activity-filtered) instead ONLY from samples whose source AND minute actually have a confirmed step count -- currently Polar (via the minute-resolved 'steps_1min' metric, s. import_polar.py::import_polar_activity) and Apple Health (where 'steps' is already minute-resolved). Other sources (Garmin, Oura, Bearable, Polar Accesslink) demonstrably deliver only one 'steps' value per calendar day (no window confirmation possible) and therefore only contribute to 'sleep' and 'day_raw', not to 'day_rest' -- their HR samples without activity confirmation are NOT assumed to be rest (no default value, s. STEPS_MINUTE_SOURCES/load_data()). 'day_raw' stays unfiltered for all sources and shows the difference filtering makes. Rest threshold STEPS_MAX steps/minute (default 10), modelled on the STEPS_MAX value in compute_orthostatic_detection.py, though that one is calibrated for a narrow confirmation window around an HR jump -- here deliberately not treated as a validated value, only a plausible rest cutoff.

## Scoring

```
Kein Evidenz-Score -- reine Kennzahlen-Gegenueberstellung
(Ø-HF Schlaf vs. Ø-HF Tagfenster, deren Differenz/Verhaeltnis).
Keine Punkte, keine Schwellen, kein Level. Fuer eine gescorte
Verdachtsbewertung s. compute_ans_dysfunction_evidence.py.
```

## Data flow

- **Reads:** `sessions`, `session_metrics`, `(auto_detected`, `distance_m)`, `measurements`, `(heart_rate`, `hrv_rmssd`, `steps`, `steps_1min`, `sleep_analysis`, `body_mass`, `body_weight`, `weight_kg)`
- **Writes:** `analyses/cardiovascular/sleep_day_hr_*.{md,png}`

## Limitations

Heuristic, not a validated clinical instrument. The 12-hour day window is an approximation, not an exact waking interval (wake time isn't identical to sleep end every night). Activity filtering is only possible for Polar/Apple data (s. @method) -- 'day_raw' stays unfiltered for all sources and thus exercise-confounded. The Apple Health approximate sleep windows (n(Apple) nights, s. @method) are NOT a device-computed sleep interval, only a rough min/max clustering of sample timestamps -- less precise than the Polar sessions, hence reported separately rather than blended with them. Months with very few nights (n<5) are statistically unstable but not auto-hidden -- visible via the n column in the report. No proof of causality: the observed trend correlates in time with other findings but proves no relationship.

## Usage

```bash
python3 analyse_sleep_day_hr.py
python3 analyse_sleep_day_hr.py --plot
python3 analyse_sleep_day_hr.py --from 2020-01-01 --to 2022-12-31
python3 analyse_sleep_day_hr.py --steps-max 5
```
