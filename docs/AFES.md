# AF Evidence Score (AFES)

> **German version:** [AFES_DE.md](AFES_DE.md)

`scripts/compute/compute_af_evidence.py` — daily, stored in `af_evidence_scores`

---

## Score formula

```
AFES = min(100, direct_points + support_points)

direct_points  = max(all direct components)      — cap: 50
support_points = sum(all support components)     — cap: 50
```

**Level:** none (0–9) · low (10–24) · moderate (25–49) · high (50–74) · critical (≥75)

---

## Direct evidence (clinically validated)

Only clinically validated or FDA-cleared algorithms. Only the highest value counts.

| Key | Max pts | Signal | Algorithm / source |
|---|---|---|---|
| `ecg` | **50** | Apple Watch ECG → AFib classification | FDA-cleared (Perez 2019 NEJM). Reads `ecg_sessions.classification = 'atrial_fibrillation'` |
| `tg` | **40** | Chest-strap RR intervals → TG episode | Tateno & Glass 2001 (doi:10.1114/1.1350670). Runs on `ppi_raw`, stored in `arrhythmie_episoden` |
| `bp_afib` | **40** | Omron blood pressure monitor → AFib flag | Omron's own oscillometric AFib detection (CE class IIa). Reads `blood_pressure.afib_possible` |
| `burden` | **30** | Apple Watch AFib burden > 0 % | FDA-cleared, continuous passive monitoring (atrial fibrillation history feature). Reads `measurements.metric = 'afib_burden'` |
| `ecg` | **15** | Apple Watch ECG → high HR or inconclusive | Same source as above, lower confidence |

**Why ECG (50) outranks the Omron BP flag (40) despite both being medically validated
devices:** ECG measures the heart's electrical activity directly — the reference
modality for rhythm diagnosis — and Apple's classifier was validated in a large
prospective study against ECG-patch ground truth (Apple Heart Study, Perez et al. 2019,
~419,000 participants). Omron's oscillometric detection is an indirect surrogate: it
infers irregularity from the pressure-wave pattern during a single ~30 s cuff
measurement, which can also be triggered by ectopic beats or motion artefact, and CE
class IIa clearance requires a smaller clinical evidence base than FDA De Novo
clearance. Same reasoning applies to the `tg` (chest-strap Tateno-Glass, 40 pts) vs.
`bp_afib` (40 pts) tie — both are algorithmic surrogates one step removed from a direct
ECG reading, hence capped below the `ecg` component.

---

## Supporting evidence (heuristic, not clinically validated)

These components add up; the sum is capped at 50 pts.

### `bp_ihb` — Irregular heartbeat during BP measurement (max 15 pts)

Omron detects pulse irregularities within the measurement window (~30 s).
Reads `blood_pressure.ihb_flag`.

| IHB flag | Points |
|---|---|
| present | 15 |

---

### `hr_tachy` — Share of sustained tachycardia (max 20 pts)

Share of wrist HR readings > 100 bpm across the full day.
Sources: all wrist sensors except those listed in
`clinical.afes.exclude_coarse_hr_devices` (health_config.json) — e.g. older
Garmin models with 120 s Smart Recording, since PPG averaging over irregular
RR intervals systematically underestimates AFib HR.
At least 10 readings/day required.

| % readings > 100 bpm | Points |
|---|---|
| ≥ 80 % | 20 |
| ≥ 60 % | 15 |
| ≥ 40 % | 10 |
| ≥ 20 % | 5 |

---

### `hr_nightcv` — Night heart-rate coefficient of variation (max 15 pts)

CV = σ/μ of all HR readings between 00:00–06:00.
High nocturnal CV indicates beat-to-beat irregularity, as seen in AFib.
Same device exclusion as `hr_tachy`. At least 5 night readings required.

| Night HR CV | Points |
|---|---|
| ≥ 0.25 | 15 |
| ≥ 0.20 | 10 |
| ≥ 0.15 | 5 |

---

### `hrv_rmssd` — Low resting RMSSD (max 10 pts)

Low optical RMSSD as a proxy for reduced autonomic modulation.
Priority: `daily_summary.hrv_rmssd_ms` > `measurements.metric = 'hrv_rmssd'` (all devices).
Note: Polar's optical RMSSD is derived from smoothed 1 s HR (±1 bpm/s) — not a
true beat-to-beat signal; use as heuristic only. Oura's RMSSD (5-min windows
from internal 1 s PPG) is more reliable.

| RMSSD | Points |
|---|---|
| < 20 ms | 10 |
| < 30 ms | 5 |

---

### `oura_hrv_chaos` — Intra-night RMSSD variability (max 8 pts)

CV of the Oura Ring's 5-minute RMSSD windows during sleep (`device_id` from
`device_registry`, `brand='Oura'`).
High intra-night RMSSD variability is an AF-precursor pattern (based on
PMC8569481). At least 3 windows/night required.

| Intra-night RMSSD CV | Points |
|---|---|
| ≥ 0.40 | 8 |
| ≥ 0.30 | 5 |
| ≥ 0.20 | 3 |

---

### `h10_preaf` — Pre-AF HRV pattern on chest-strap RR (max 8 pts)

Share of 5-minute `ppi_windows` with RMSSD > 50 ms **and** CV_RR 0.08–0.18.
This pattern occurs 5–35 min before AF onset (93 % precision, PMC8569481).
Applicable to any Polar chest-strap beat-to-beat RR source (`sensor_type = 'chest_strap'`, e.g. H10 or H7), not H10-exclusive despite the name. At least 3 windows/day required.

| % windows with pre-AF pattern | Points |
|---|---|
| ≥ 30 % | 8 |
| ≥ 15 % | 5 |
| ≥ 5 % | 2 |

---

### `hr_range` — Intraday HR range (max 15 pts)

P90−P10 percentile spread of daily HR, from continuous wrist/ring sensors.
More robust than max−min: single artifacts or short tachycardia spikes don't
distort the result. AFib with rapid ventricular response (RVR) typically
produces a spread ≥ 65 bpm; normal sinus rhythm stays below that in everyday life.
Training windows are excluded. At least 20 readings/day required.

**Devices used:** automatically derived from `device_registry` (all entries
with `sensor_type` ∈ {`optical_wrist`, `optical_wrist_gps`, `ring`}); manual
override via `clinical.afes.wrist_hr_devices`. Coarse-HR sources are excluded
via `clinical.afes.exclude_coarse_hr_devices`.

| HR spread (P90 − P10) | Points |
|---|---|
| ≥ 65 bpm | 15 |
| ≥ 50 bpm | 8 |

---

### `aw_high_hr` — Apple Watch high heart rate alert (max 10 pts)

Apple Watch passively monitors resting HR and triggers an alert when HR > 120 bpm
for > 10 minutes at rest (FDA-cleared passive monitoring algorithm).
HealthKit stores these as category events with `value = 0` (notApplicable =
event occurred). Deduplicated via `source_app='apple_health'` plus the
associated `device_id`.

| Alert present that day | Points |
|---|---|
| yes | 10 |

---

### `spo2` — Low oxygen saturation (max 10 pts)

AFib reduces cardiac output; hypoxia can result.
Apple Health stores SpO₂ as a decimal fraction (0.956 = 95.6 %) — normalized on import.
Priority: `daily_summary.spo2_avg` > `measurements.metric IN ('spo2','oxygen_saturation')`.

| SpO₂ | Points |
|---|---|
| < 92 % | 10 |
| < 94 % | 5 |

---

### `resp` — Breathing disturbances (max 5 pts)

Elevated respiratory rate/breathing disturbances can accompany hemodynamic
stress in AFib. Combines four sources; per day the source with the highest
points wins (MAX logic, not additive). Devices listed in
`clinical.afes.exclude_coarse_hr_devices` are excluded for the respiratory-rate
source (see `hr_tachy`).

| Source | Threshold | Points |
|---|---|---|
| Respiratory rate (`daily_summary`/`measurements`) | > 20 /min | 5 |
| | ≥ 18 /min | 2 |
| Sleep Cycle `breathing_disrupt` | > 15 | 5 |
| | > 10 | 2 |
| Sleep Cycle `snore_s` | > 7200 s | 5 |
| | > 4800 s | 2 |
| Sleep Cycle `coughs_per_h` | > 2.0 | 5 |
| | > 1.0 | 2 |
| Sleep Cycle `respiration_avg` | ≥ 17 | 2 |
| Apple `sleep_breathing_disturbances` | > 1.0 /h | 5 |
| | > 0.7 /h | 2 |
| Oura `breathing_disturbance_index` | > 10 | 5 |
| | > 5 | 2 |

---

### `symptoms` — Cardiac symptoms logged (max 10 pts)

Any of the following symptoms logged the same day with value > 0:
*palpitations, chest tightness/pain, dizziness, dyspnea (physiological),
dyspnea (panic)*.
Source: `symptoms` table (symptom-diary importer).

| ≥ 1 cardiac symptom | Points |
|---|---|
| yes | 10 |

---

### `hr_nightdip` — Nocturnal HR dip (max 8 pts)

In normal sleep, HR drops 15–25 % below the pre-sleep baseline (parasympathetic dominance).
AFib, rapid ventricular response (RVR), and autonomic dysregulation suppress this dip (non-dipper).

**Sleep window:** adaptive from the `sessions` table — priority via
`clinical.afes.sleep_device_priority` (ordered list of `device_id`s;
typically devices with the best sleep-staging quality first, such as ring
sensors, then optical wrist sensors, then smartphones). Sessions < 3 h (naps)
are skipped.
Fallback for nights without a session: fixed windows converted to the
person's local timezone (`persons.timezone`, via `ZoneInfo`) — pre-sleep
local 21–22, sleep onset local 23:00, sleep local 00–05.

**Baseline:** median HR 90 min before sleep onset (at least 10 readings).
**Nadir:** P10 of HR during the sleep period (at least 20 readings). P10 is
more robust than the minimum against PPG artifact outliers.
Score date = the evening before sleep onset (falling asleep after midnight
is attributed to the previous day).

Confounders: alcohol raises night HR, beta blockers suppress the baseline —
both mimic a non-dipper pattern without AFib. Support evidence only.

| Dip magnitude | Points |
|---|---|
| < 5 % (missing dip) | 8 |
| 5 – < 10 % (reduced dip) | 4 |
| ≥ 10 % (normal) | 0 |

---

### `h10_dfa` — DFA alpha1 on chest-strap RR data (max 15 pts)

Detrended Fluctuation Analysis (DFA) measures the fractal self-similarity of
the RR time series. The short-term scaling exponent alpha1 describes the
memory structure of consecutive RR intervals:

```
alpha1 < 0.75  → loss of fractal memory → typical for AFib (AV-node chaos)
alpha1 ~ 1.0   → normal sinus rhythm (1/f noise)
alpha1 > 1.2   → pathological rigidity (e.g. severe heart failure)
```

In AFib, chaotic AV-node conduction destroys the correlated RR patterns of
the sinus node → alpha1 drops below 0.75.
One of cardiology's most-replicated nonlinear HRV markers (Mäkikallio
1998/1999/2001, Ho 1997, Peng 1995).

**Processing:** `scripts/compute/compute_ppi_dfa.py` — 5-min non-overlapping
windows on `ppi_raw` (at least 100 beats/window; gaps > 3 s split segments).
Results in `ppi_dfa`. Only resting windows (`is_training = 0`) count toward AFES.

**Device:** chest-strap beat-to-beat data only (`sensor_type = 'chest_strap'`).
Optical sensors produce artificially correlated sequences (firmware-side
smoothing ±1 bpm/s) that render alpha1 meaningless.

| % resting windows/day with alpha1 < 0.75 | Points |
|---|---|
| ≥ 30 % | 15 |
| ≥ 15 % | 8 |
| ≥ 5 % | 3 |

At least 30 resting windows/day required. Days without chest-strap data: 0 points.

**Interpretation:** days with a high share of α1 < 0.75 are suspicious for
paroxysmal episodes; multi-day clusters in the 13–25 % range can precede an
ECG-confirmed AFib diagnosis.
Days without chest-strap data receive 0 points and remain neutral in the evaluation.

---

### `h10_poincare` — Poincaré SD1/SD2 ratio (max 6 pts)

SD1 (short-term variability, ≈ RMSSD/√2) relative to SD2 (long-term
variability) from chest-strap beat-to-beat data (`ppi_hrv_advanced`, any
`sensor_type = 'chest_strap'` source, e.g. H10 or H7 — not H10-exclusive
despite the name).
Sinus rhythm: SD2 ≫ SD1 → ratio ≪ 1 (typically 0.15–0.35 at rest). AFib: SD1 ≈
SD2 → ratio → 1.0.

**Calibration method** (`scripts/calibration/calibrate_afib_thresholds.py`): sliding 150-beat windows (~2-3 min, step 75 beats) were built across all 24 AFDB recordings (10 h ECG, 250 Hz, with expert rhythm annotation); a window counts as an AFib window at ≥90 % AFib-annotated beats, as a sinus-rhythm window at <10 %, windows in between are discarded. `poincare_ratio` is computed per window; an ROC curve over all pooled windows (AFib vs. sinus-rhythm label) yields the AUC and the F1-optimal threshold.

AFDB calibration yielded AUC 0.537 — barely
better than chance. Threshold 0.74 from the calibration; the metric is kept
only as a weak supporting signal with a reduced point cap (6 instead of the
original 10). Chest-strap data only, training windows excluded, at least 3
windows/day, at least 100 beats/window.

| Avg. SD1/SD2 ratio | Points |
|---|---|
| ≥ 0.74 | 6 |
| ≥ 0.60 | 3 |

---

### `h10_sampen` — Sample entropy (max 5 pts)

Share of 5-minute windows with high sample entropy (Richman & Moorman 2000,
doi:10.1152/ajpheart.2000.278.6.H2039) from chest-strap beat-to-beat data
(`ppi_hrv_advanced`, any `sensor_type = 'chest_strap'` source, e.g. H10 or
H7). AFib's chaotic, irregular ventricular rate produces
higher RR entropy than sinus rhythm's regular, RSA-shaped structure.

AFDB calibration (MIT-BIH AF Database, 24 records, same window/label methodology as `h10_poincare` above): direction higher = AFib,
AUC 0.853, F1 0.793, calibrated threshold 1.587. Serves as cross-validation
for `h10_dfa`. Chest-strap data only, training windows excluded, at least 3
windows/day, at least 200 beats/window. Transfer of the AFDB threshold to
chest-strap data is unverified.

| % windows with sample entropy ≥ 1.587 | Points |
|---|---|
| ≥ 10 % | 5 |
| ≥ 5 % | 3 |

---

### `h10_turning` — Turning-point ratio (max 8 pts)

Share of local extrema in the RR time series (turning-point ratio = number of
local extrema / (n−2)) from chest-strap beat-to-beat data (`ppi_hrv_advanced`,
any `sensor_type = 'chest_strap'` source, e.g. H10 or H7, column
`turning_pt_ratio`). Sinus rhythm: ~0.55–0.65 (RSA pattern suppresses turning
points). AFib: > 0.57 (irregular ventricular rate → more local extrema per
window).

AFDB calibration (MIT-BIH AF Database, 24 records, same window/label methodology as `h10_poincare` above): direction higher = AFib,
threshold 0.5743, AUC 0.882, F1 0.816 — the strongest single discriminator
among the chest-strap support components. Requires `compute_hrv_advanced.py
--rebuild` for the `turning_pt_ratio` backfill; yields 0 points as long as the
column is missing or more than 90 % NULL. Chest-strap data only, training windows
excluded, at least 3 windows/day, at least 50 beats/window.

| % windows with turning-point ratio ≥ 0.5743 | Points |
|---|---|
| ≥ 40 % | 8 |
| ≥ 25 % | 5 |
| ≥ 15 % | 3 |

---

### `skin_temp` — Skin temperature anomaly (max 5 pts)

Deviation > 1.5 °C from the rolling 14-day average.
Fever / autonomic dysregulation can trigger or accompany AFib.
Source: `measurements.metric = 'skin_temperature'` (wrist/finger sensors with
skin-temp capability). At least 5 baseline days required.

| Deviation from 14-day average | Points |
|---|---|
| > 1.5 °C | 5 |

---

## Disabled component

### `hr_sym_entropy` — Symbolic dynamics entropy *(disabled)*

Shannon entropy of HR-direction bigrams (A/D/S) on 1 s wrist data.
Based on Zhou et al. 2015 (PMC4573734).

Disabled after calibration across all available optical sources (comparing
AFib day vs. normal days):

| Source | Normal-day H_norm | AFib-day H_norm | Finding |
|---|---|---|---|
| Optical, 1 s smoothed | ~0.15 | ~0.15 | always low — firmware-side smoothing (±1 bpm/s) produces long (S,S) runs |
| Optical, ~5 s active / ~300 s passive | ~0.96 | ~0.96 | always high — coarse sampling looks like noise |
| Optical, variable interval (1–30 s) | ~0.88 | ~0.97 | diff only 0.09 — variable sampling creates artificial entropy even on normal days |

**Root problem:** symbolic dynamics requires true beat-to-beat data at a
constant rate (Holter quality). No optical wrist sensor delivers that. If a
chest-strap raw-ECG lead is added later, re-evaluate.
Function remains in the code for that case.

---

## Device policy

Classified by `sensor_type` from `device_registry` (health_config.json) and
the firmware-/protocol-typical HR sampling. The concrete models are
user-specific and are mapped via `device_registry`.

| Sensor class | HR sampling | Used in AFES |
|---|---|---|
| Chest strap (`chest_strap`) | Beat-to-beat RR (ms) | `tg`, `h10_preaf`, `h10_dfa`, `h10_poincare`, `h10_sampen`, `h10_turning` |
| Wrist optical, 1 s continuous | 1 s | `hr_tachy`, `hr_nightcv`, `hr_range` |
| Finger ring (`ring`) | ~5 s active / ~300 s sleep | `hr_tachy`, `hr_nightcv`, `hr_range`, `oura_hrv_chaos` |
| Wrist optical, variable + ECG (`optical_wrist_gps` with ECG) | ~5 s active / ~75–300 s passive / 1 s training | `hr_tachy`, `hr_nightcv`, `hr_range`, `aw_high_hr`, `ecg`, `burden`, `spo2`, `resp` |
| Wrist optical, Smart Recording (≥ 60 s) | Configurable via `clinical.afes.exclude_coarse_hr_devices` | **excluded from all HR signals** — PPG averaging masks AFib HR |
| Blood pressure monitor (`bp_monitor`) | per reading | `bp_afib`, `bp_ihb` |
| Symptom diary | per entry | `symptoms` |

→ For how to actually capture good chest-strap data for the `h10_*`
components: [HRV_MONITORING_PROTOCOL.md](test_protocols/HRV_MONITORING_PROTOCOL.md)

---

## Output table: `af_evidence_scores`

| Column | Type | Description |
|---|---|---|
| `date` | TEXT | ISO date (PK) |
| `person` | TEXT | 'self' / 'partner' (PK) |
| `score` | INTEGER | 0–100 |
| `direct_pts` | INTEGER | Direct-evidence contribution |
| `support_pts` | INTEGER | Support-evidence contribution (≤ 50) |
| `level` | TEXT | none / low / moderate / high / critical |
| `components` | TEXT | JSON: component → points for all non-zero components |
| `signals_used` | INTEGER | Number of contributing data sources |
| `computed_at` | TEXT | UTC timestamp of the last computation |

---

## Result schema (level distribution)

| Level | Description |
|---|---|
| critical | ECG-confirmed AFib or score ≥ 75 |
| high | Several independent signals simultaneously, score 50–74 |
| moderate | Individual notable signals, score 25–49 |
| low | Weak background noise, score 10–24 |
| none | No relevant signals, score < 10 |

The actual distribution (days per level, max scores, peak days) is computed
from your own data in `af_evidence_scores` and printed in the analysis
report. No personal example data is documented here.

---

## Usage

```bash
# Full recompute (after code changes)
python scripts/compute/compute_af_evidence.py --recompute

# Append new days only
python scripts/compute/compute_af_evidence.py --update

# Specific date range
python scripts/compute/compute_af_evidence.py --from YYYY-MM-DD --to YYYY-MM-DD
```
