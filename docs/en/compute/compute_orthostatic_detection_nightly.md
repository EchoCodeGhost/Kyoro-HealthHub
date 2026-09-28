# Naechtliche Orthostase-Kandidaten aus Oura-Bewegungs-/HF-Daten.

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/compute/compute_orthostatic_detection_nightly.py`

**Evidence tier:** heuristic (deliberate design from domain knowledge, no formal literature or validation basis)

## Purpose

Nighttime counterpart to compute_orthostatic_detection.py: scans Oura sleep data (30-second movement classification + 5-minute HR averages) for patterns consistent with getting out of bed at night (e.g. a bathroom trip), storing candidates in sessions/session_metrics (type='orthostatic', source_app='oura_nightly_detected') for analyse_orthostatic.py to evaluate.

## Relevance

Surfaces suspected nighttime orthostatic episodes (e.g. bathroom trips) from Oura sleep data that couldn't be captured during the day

## Method

No continuous beat-to-beat signal exists during Oura sleep (only 5-minute HR/HRV averages, already imported as measurements (metric='oura_sleep_hr'/'hrv_rmssd', source_app='oura_app') by import_oura.py — reused here rather than re-parsing heart_rate_json/ hrv_json from the oura_sleep_model row, since those measurements rows are already verified to be correctly in UTC). Instead of an HR jump (too coarse for the sharp-onset test used in compute_orthostatic_detection.py) movement_30_sec is evaluated: a digit string (one digit per 30-second epoch, higher digit = more movement per Oura, the precise meaning of individual digit values is not available from official documentation — treated here purely as a relative movement intensity, see @limits). A "movement burst" is defined as at least MOVEMENT_BURST_EPOCHS epochs with digit >= MOVEMENT_BURST_MIN following at least MOVEMENT_QUIET_EPOCHS quiet epochs (digit <= MOVEMENT_QUIET_MAX). For the burst onset, mean HR in the NIGHT_BASELINE_MIN window before is compared to peak HR in the NIGHT_ONSET_WINDOW_MIN window after; a rise >= NIGHT_HR_JUMP_MIN counts as a candidate. The blood-pressure cross-check (_bp_check from compute_orthostatic_detection, same Sheldon 2015 criteria) is reused but practically never finds a reading (blood pressure isn't measured during sleep) — included only for data-structure completeness, not a meaningful confirmation channel here. Only ONE candidate per night (largest ΔHR).

## Scoring

```
detection (all must hold for a candidate):
  movement burst: >= MOVEMENT_BURST_EPOCHS epochs >= MOVEMENT_BURST_MIN,
                   preceded by >= MOVEMENT_QUIET_EPOCHS epochs <= MOVEMENT_QUIET_MAX
  hr jump:         peak HR in NIGHT_ONSET_WINDOW_MIN after burst onset
                    minus mean HR in NIGHT_BASELINE_MIN before >= NIGHT_HR_JUMP_MIN (10 bpm)
bp_confirmed (informational, not a filter, almost always None at night):
  see compute_orthostatic_detection._bp_check
```

## Data flow

- **Reads:** `oura_sleep_model`, `measurements`, `(oura_sleep_hr`, `hrv_rmssd)`, `sessions`, `(to`, `resolve`, `the`, `Oura`, `device`, `id)`, `blood_pressure`
- **Writes:**

  ```
  sessions, session_metrics (type='orthostatic',
  source_app='oura_nightly_detected')
  ```

## Limitations

Considerably more speculative than the daytime counterpart compute_orthostatic_detection.py: (1) the 5-minute HR averages smooth out any brief rise far more than beat-to-beat data — a real, short bathroom-trip HR rise can be underestimated or missed entirely by the averaging; NIGHT_HR_JUMP_MIN (10 bpm) is NOT calibrated against real confirmed tests the way compute_orthostatic_detection.py's threshold is (no real nighttime stand tests exist as a reference) — a pure own judgment call, considerably less certain. (2) The meaning of movement_30_sec digit values is not verified from official Oura documentation, only assumed as "higher = more movement" — whether a detected movement burst actually corresponds to getting up (rather than e.g. turning over in bed, scratching, a bed partner's movement if the device is wrist-worn) cannot be verified. (3) Only a small number of nights with complete movement data available (as of this implementation, a short observation period) — a small sample. (4) The BP cross-check practically never yields a confirmation (blood pressure isn't measured during sleep) — unlike the daytime script, not a meaningful extra confirmation channel here. A candidate here is therefore substantially weaker evidence than a daytime candidate, let alone a real Polar test.

## References

- Sheldon RS, Grubb BP, Olshansky B et al. (2015). 2015 Heart Rhythm Society Expert Consensus Statement on the Diagnosis and Treatment of Postural Tachycardia Syndrome, Inappropriate Sinus Tachycardia, and Vasovagal Syncope. Heart Rhythm, 12(6):e41-e63. doi:10.1016/j.hrthm.2015.03.029 (nur fuer den wiederverwendeten BP-Gegencheck relevant, s. @method; kein eigenes Referenzkriterium fuer die Bewegungserkennung selbst, da diese nicht auf publizierter Evidenz beruht, s. @limits)

## Usage

```bash
python3 scripts/compute/compute_orthostatic_detection_nightly.py
python3 scripts/compute/compute_orthostatic_detection_nightly.py --date-from 2026-01-01
python3 scripts/compute/compute_orthostatic_detection_nightly.py --lang en
```
