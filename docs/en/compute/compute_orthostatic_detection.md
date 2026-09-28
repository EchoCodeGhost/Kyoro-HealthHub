# Orthostase-Kandidaten-Erkennung aus Alltags-PPI-Daten.

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/compute/compute_orthostatic_detection.py`

**Evidence tier:** heuristic (deliberate design from domain knowledge, no formal literature or validation basis)

## Purpose

Scans continuous everyday heart-rate recordings (not just deliberate stand tests) for patterns consistent with a position/posture change (e.g. lying → standing), storing candidates in sessions/session_metrics (type='orthostatic', source_app='ppi_detected') for analyse_orthostatic.py to evaluate.

## Relevance

Surfaces suspected orthostatic episodes from existing everyday data instead of only the rare deliberate tests

## Method

No device in this project exports raw position/accelerometer sensor data (checked: all imports/ directories + Apple Health Export.xml record types — nothing found, only the unrelated AppleWalkingSteadiness gait score, no position/orientation signal). Substitute: a rolling HR window from ppi_raw (device-/source-agnostic — any device delivering beat-to-beat data, including PPG wearables like the Polar Loop, flows in automatically, see @limits for the PPG accuracy caveat). HARD LIMIT for CONTINUOUS everyday monitoring: Garmin, Oura, and continuous Apple Watch HR deliver NO beat-to-beat raw data via their APIs at all — only already-computed RMSSD window values (Garmin: get_hrv_data(); Oura: hrv.items(), both 5-minute aggregates). These therefore never reach ppi_raw and are NEVER processed by this script regardless of device_registry entries — a vendor API boundary, not a design choice. NO hard limit, however, for single ECG recordings (30-sec snapshots): those land device-agnostically in ecg_sessions/ecg_samples and are automatically converted to genuine RR intervals by compute_ecg_rpeaks.py's R-peak detection (source derived dynamically from ecg_sessions.source, e.g. 'ecg_apple', 'ecg_garmin' — no longer Apple-exclusive since the earlier mislabeling bug there was fixed). In practice this still depends on the source device's own capability: not every model records on-device ECG snapshots at all (checked against device_registry and export content: fitness/outdoor-only models without an ECG app simply produce no *ECG_Details*.json files) — the pathway exists in the script but only delivers data if the source device actually records ECG snapshots. A jump ≥HR_JUMP_MIN bpm (15 bpm — the lower bound of "borderline" per the classification in analyse_orthostatic.py, NOT the Sheldon 2015 POTS criterion of 30 bpm: an own calibration against real stand tests showed genuine HR jumps mostly falling below that threshold — requiring 30bpm directly would miss real episodes) that is already reached within ONSET_WINDOW_S after the REF_WINDOW_S reference window AND sustained for at least SUSTAIN_MIN_S counts as a candidate — the absence of a transition gap forces a SHARP rise (characteristic of a genuine position change), a slow multi-minute stress/MCAS ramp fails this. RMSSD analogously from the same windows (chronological beat order, not value-sorted). To rule out exercise false alarms: where intraday-resolved step data exists (so far only Apple, other sources only provide daily totals), step count in the confirmation window must stay under STEPS_MAX — without such data the candidate is flagged with a note instead of rejected (missing confirmation ≠ refutation). Additionally: blood pressure readings within a ±BP_WINDOW_MIN window around the jump are checked for orthostatic hypotension (Sheldon 2015: SBP drop ≥BP_SYS_DROP_MIN OR DBP drop ≥BP_DIA_DROP_MIN) — purely confirmatory, not a filter, since only a fraction of candidates happen to have a nearby BP reading at all. Detects only ONE candidate per day (the one with the largest ΔHR) to avoid flooding from adjacent partial hits on the same real episode.

## Scoring

```
detection (all must hold for a candidate):
  HR jump    >= HR_JUMP_MIN (15 bpm)   within ONSET_WINDOW_S of the reference window
  sustained  >= HR_JUMP_MIN * 0.7      for at least SUSTAIN_MIN_S afterwards
  steps      <= STEPS_MAX              in the confirmation window (if intraday step data exists)
bp_confirmed (informational, not a filter):
  SBP drop >= BP_SYS_DROP_MIN (20 mmHg) OR DBP drop >= BP_DIA_DROP_MIN (10 mmHg)
  within ±BP_WINDOW_MIN of the candidate, per Sheldon 2015 orthostatic-hypotension criterion
```

## Data flow

- **Reads:** `ppi_raw`, `measurements`, `(steps`, `steps_1min)`, `blood_pressure`
- **Writes:** `sessions, session_metrics (type='orthostatic', source_app='ppi_detected')`

## Limitations

Heuristic method: own detection algorithm, no published change-point detection library used (simple rolling-window comparison). Everyday data is less controlled than a real stand test (no standardized pre-behaviour, no guaranteed rest period before the jump) — so inherently lower evidentiary weight than real Polar stand tests (source_app='polar_connect' in the same sessions table), even at the same delta HR. Cannot distinguish a genuine position change from any other cause of non-exertional HR rise (anxiety, MCAS reaction, and medication effect are equally plausible causes); a found candidate is "unexplained sharp HR rise without movement", orthostatic change is a plausible but unproven explanation for it. PPG sources (Polar Loop, sensor_type optical_wrist_gps) are more motion-artifact-prone and less precise than chest-strap ECG (H7/H10) — candidates from PPG devices deserve less trust than chest-strap candidates, even though both are treated identically (the device id is in the session's device_id field and can be filtered afterwards). HR_JUMP_MIN (15 bpm, see @method), ONSET_WINDOW_S, SUSTAIN_MIN_S, STEPS_MAX, BP_SYS_DROP_MIN/BP_DIA_DROP_MIN are own thresholds for the DETECTION (the BP thresholds themselves are Sheldon 2015, but applying them to uncontrolled everyday data with a ±BP_WINDOW_MIN window instead of an exact test moment is an own approximation). RMSSD values use a simple local-median outlier filter (see modules/rr_interval_algorithms.filter_beat_artifacts), NOT the full Kubios artifact correction from compute_hrv_advanced.py — the RMSSD column is informational, the HR-based detection itself doesn't depend on it.

## References

- Sheldon RS, Grubb BP, Olshansky B et al. (2015). 2015 Heart Rhythm Society Expert Consensus Statement on the Diagnosis and Treatment of Postural Tachycardia Syndrome, Inappropriate Sinus Tachycardia, and Vasovagal Syncope. Heart Rhythm, 12(6):e41-e63. doi:10.1016/j.hrthm.2015.03.029 (orthostatische Hypotonie SBP-Abfall ≥20mmHg / DBP-Abfall ≥10mmHg — hier als BP-Bestätigungsschwelle verwendet, s. _bp_check. Das POTS-Kriterium ΔHR ≥30 bpm aus derselben Quelle wird NICHT als Erkennungsschwelle verwendet, s. HR_JUMP_MIN-Begründung in @method)

## Usage

```bash
python3 scripts/compute/compute_orthostatic_detection.py
python3 scripts/compute/compute_orthostatic_detection.py --date-from 2026-01-01
python3 scripts/compute/compute_orthostatic_detection.py --lang en
```
