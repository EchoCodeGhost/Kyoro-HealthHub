# Autonome-Dysfunktion-Evidenz-Score — tageweise über die gesamte Historie

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/compute/compute_ans_dysfunction_evidence.py`

**Evidence tier:** heuristic (deliberate design from domain knowledge, no formal literature or validation basis)

## Purpose

Computes a suspected-autonomic-dysfunction evidence score for every day with available signals, across the entire available history (not just "today") -- architecture copied 1:1 from compute_af_evidence.py (AFES): direct evidence (max of candidates, not sum, to avoid double-counting a single strong signal) plus capped, additive support evidence.

## Relevance

Historical, day-by-day view of suspected-dysfunction evidence -- complements analyse_ans_battery.py (correlations + most recent value per channel), which deliberately does not keep a daily evidence score.

## Method

Direct evidence (validated external criteria, not newly derived): - Orthostatic candidate ΔHR≥OI_HR_THRESHOLD (Sheldon 2015 POTS criterion, s. compute_clinical.py) that day -> 30 pts (highest weight of the three -- the only one with a named clinical syndrome criterion behind it), borderline (OI_HR_BORDERLINE to <THRESHOLD) -> 15 pts. - Nocturnal HR dip <5% (already documented as an "autonomic dysregulation" threshold in compute_af_evidence.py:: load_hr_nightdip(), reused here for the same signal type, not newly invented) -> 15 pts, <10% (non-dipper) -> 8 pts. - Nocturnal BP non-/reverse-dipping (ESC criteria, s. analyse_bp_sleep.py::_dipping_class()): reverse dipper (<0%) -> 15 pts, non-dipper (0-10%) -> 8 pts. direct_pts = max(...) of these three candidates per day. Support evidence (graduated deviation from the person's own personal_baseline, s. modules/baseline.py -- no absolute clinical cutoff, hence weighted lower): - HRV (RMSSD) < -50% vs. baseline -> 10 pts, < -30% -> 5 pts. - Resting HR > +20% vs. baseline -> 10 pts, > +10% -> 5 pts. - Breathing disturbance, device-agnostic (Apple sleep_breathing_ disturbances >1.0/h=5/>0.7/h=2, Oura breathing_disturbance_ index >10=5/>5=2, Sleep Cycle breathing_disrupt >15=5/>10=2 -- all three threshold pairs copied 1:1 from compute_af_evidence.py, not newly invented; Polar demonstrably has no data for this, s. coverage check in main()). - SpO2 < 92% -> 10 pts, < 94% -> 5 pts, NOCTURNAL MINIMUM ONLY (measurements.metric='sleep_spo2_min' from compute_sleep_spo2.py -- Garmin/Apple/Wellue O2Ring; Oura/ Polar/Beurer/Withings deliberately excluded, s. that docstring: no genuine nighttime value derivable). With multiple sources for the same night: ONE winner via spo2_priority() (Regel B, device_registry.py), NOT MIN() across sources -- MIN() would let a noisy device systematically "win" via a random low outlier, s. _load_spo2(). Deliberately restricted to nighttime rather than a daily average (earlier state: daily_context.spo2_avg_pct) -- Kyoro has no continuous daytime SpO2 coverage from any device, a full-day criterion would almost always have been empty. Threshold copied 1:1 from compute_af_evidence.py::_load_spo2(). support_pts = min(20, sum). score = direct_pts+support_pts (max 50 -- notably less than AFES' 100, since only 3 direct + 4 support criteria feed in here vs. ~20 there; LEVELS thresholds therefore scaled proportionally to this smaller range, s. comment at LEVELS in the code, NOT copied 1:1 from AFES). CONTEXT (not scored, carried informationally in the components JSON): deconditioning (daily activity/met_minutes vs. own baseline -- ORIGINALLY scored as a support criterion, corrected after user pushback: unlike the other criteria, activity only measures BEHAVIOUR, not ANS function itself -- low activity can follow from dysfunction, but just as easily from any other reason; additionally confirmed empirically: as a support criterion it overlapped with hrv_low on 41.5% of relevant nights, likely double-counting the same underlying phenomenon, s. _load_deconditioning_context()); cycle day (cycle_day, not an ANS symptom itself, but a possible modulator via oestrogen/progesterone effects on baroreflex sensitivity); progesterone:estradiol ratio and eGFR from medicine.db:: lab_manual, each matched to the nearest score date (±30 days) -- both point-in-time lab values without an established daily ANS cutoff, deliberately not scored. Polar's own nocturnal ANS signal (polar_nightly_hrv: ans_status, ans_rate, recovery_indicator/-sublevel, rmssd_ms/rri_ms/ respiration_ms each against Polar's own baseline_* calculation, s. _load_polar_nightly_context()) -- deliberately NOT scored after checking: ans_status correlates only weakly with this score (r=-0.072, n=941, p=0.028, practically negligible effect despite statistical significance), ans_rate is demonstrably just a 5-step rounding of ans_status (same weak correlation), and both are an unpublished, proprietary Polar algorithm without external clinical validation -- unlike the other criteria here (Sheldon 2015, ESC). Carried only as context/ comparison, to cross-check Polar's own system against ours where useful. IMPORTANT: personal_baseline stores only ONE current baseline snapshot per metric (no time-varying baseline history) -- historical days are therefore compared against a baseline computed from a later period, not one contemporaneous with that day. Rows with implausible n_days (s. finding on compute_personal_baseline.py, analyse_ans_battery.py:: _baseline_n_days_plausible()) are skipped rather than computing a false deviation.

## Scoring

```
direct  = max(Orthostatic=30/15, NightHRDip=15/8, BPDipping=15/8)
support = sum(HRV_low=10/5, RHR_high=10/5, Breathing=5/2, SpO2=10/5)
          capped at 20
score   = direct_pts + support_pts  (max 50)
```

## Data flow

- **Reads:** `sessions`, `session_metrics`, `(type='orthostatic')`, `daily_context`, `personal_baseline`, `blood_pressure`, `(via`, `analyse_bp_sleep.py)`
- **Writes:** `ans_dysfunction_evidence`

## Limitations

DELIBERATELY not a substitute for clinical diagnostics (Schellong test, tilt-table, 24h BP monitoring, formal HRV analysis). The three direct criteria are individually validated; their combination into ONE score (max/sum/cap) is a project-internal heuristic, not a literature-validated combination rule -- same as AFES, documented there with the same caveat. Baseline comparison is retrospective against a single, later-computed baseline (s. @method), not point-in-time accurate. Days without any signal get no row (do not read "no row" as score=0/"unremarkable" -- s. signals_used column). No multiple-testing correction. Score omits channels not yet wired in (e.g. symptom diary, sport-cardiology stress-test data) -- can be added in a future extension.

## References

- Sheldon RS, Grubb BP, Olshansky B et al. (2015). 2015 Heart Rhythm Society Expert Consensus Statement on the Diagnosis and Treatment of Postural Tachycardia Syndrome, Inappropriate Sinus
- Tachycardia, and Vasovagal Syncope. Heart Rhythm, 12(6):e41-e63. doi:10.1016/j.hrthm.2015.03.029 (cited via compute_clinical.py, not re-derived).
- ESC 2024 nocturnal BP dipping criteria (cited via analyse_bp_sleep.py, not re-derived).

## Usage

```bash
python3 compute_ans_dysfunction_evidence.py
python3 compute_ans_dysfunction_evidence.py --recompute
python3 compute_ans_dysfunction_evidence.py --from 2023-01-01 --to 2023-12-31
```
