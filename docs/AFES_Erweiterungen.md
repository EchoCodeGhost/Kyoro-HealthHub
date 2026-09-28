# AFES – Possible Extensions and Algorithms

> **Deutsche Version:** [AFES_Erweiterungen_DE.md](AFES_Erweiterungen_DE.md)

Context: [AFES.md](AFES.md) — score formula, existing components, device policy

---

## Data basis (inventory schema)

The actual row counts and time span depend on the local data set.
Representative orders of magnitude (determine your own values via `SELECT COUNT(*)` if needed):

| Source | Content |
|---|---|
| `ppi_raw` (chest strap) | Real beat-to-beat RR intervals, ms resolution |
| `ppi_raw` (wrist pairing) | Chest strap parallel to smartwatch/ring |
| `ppi_windows` | 5-min windows: RMSSD, CV_RR, SDNN, n_beats, tpr |
| `measurements` | HR, SpO₂, respiratory rate, skin temp, … |
| Confirmed AFib days | Ground truth: ECG-confirmed or AFib burden > 0 % |

---

## Candidate 1 — Poincaré SD1/SD2 ratio ✅ IMPLEMENTED

### What we do
From every 5-min `ppi_window`, SD1 and SD2 can be derived directly from already-stored columns:

```
SD1 = rmssd_ms / sqrt(2)           ← short-term beat-to-beat scatter
SD2 = sqrt(2 * rr_sd_ms² − SD1²)   ← long-term variability
Ratio = SD1 / SD2
```

Poincaré is a geometric representation: RR(n) on the X axis, RR(n+1) on the Y axis. SD1 is the scatter perpendicular to the diagonal (beat-to-beat chaos), SD2 along the diagonal (overall trend).

### Why / evidence
- In sinus rhythm, respiratory sinus arrhythmia dominates the long-term pattern → SD2 > SD1 (ratio < 1).
- In AFib, autonomic modulation is absent; RR intervals follow a pseudo-random pattern due to chaotic AV-node conduction → SD1 >> SD2 (ratio > 1).
- Brennan et al. 2001 (Ann Biomed Eng) showed Poincaré geometry discriminates between AF and other arrhythmias.
- Guzik et al. 2007: SD1/SD2 significantly higher in AF episodes than in sinus rhythm (p < 0.001).

### What it gives us
- **No new processing needed** — `ppi_windows` already has `rmssd_ms` and `rr_sd_ms`. Just new SQL logic in `compute_af_evidence.py`.
- Adds a geometric dimension to `h10_preaf` (RMSSD + CV_RR).
- Signal independent of the existing RMSSD heuristic (`hrv_rmssd`).
- Max. 8-10 points as a support component would make sense (similar to `oura_hrv_chaos`).

### Downsides / risks
- **Window-length dependency:** SD2 varies with window length; our fixed 5-min windows are internally consistent but not comparable to standard 24 h Poincaré. Thresholds need to be calibrated empirically from our own data.
- **Optical-smoothing problem:** `ppi_windows` can also contain windows from optical sources (sensor_type=`optical_wrist_gps`). There, HR is smoothed (±1 bpm/s), which artificially reduces SD1. Filtering to sources with `sensor_type='chest_strap'` (e.g. H10 or H7) is necessary.
- **Few calibration days:** Only a small single-digit number of confirmed AFib days in our own data → threshold recommendation is weak; high risk of being too conservative or too aggressive.
- **Double-counting with `hrv_rmssd`:** SD1 is mathematically equivalent to RMSSD/√2. If both are counted as support components, the score could weight AFib days more heavily than intended.

### Consequences for AFES
If we add SD1/SD2 as a new support component `h10_poincare` (max. 8 points), the theoretical support maximum rises to 131 points — the 50-pt cap keeps the overall score maximum at 100 regardless. This means: the cap gets reached on more AFib days, while on weak days the individual component becomes more visible. Risk: on normal days with occasional heart-rate variability, the ratio could briefly exceed 1 and yield false points.

**Implemented as:** `h10_poincare` (see [AFES.md](AFES.md)) — though with a reduced point cap (6 instead of the 8 proposed here), since the later AFDB calibration only yielded AUC 0.537 (barely better than chance) instead of the strong discrimination hoped for here.

---

## Candidate 2 — DFA alpha1 ✅ IMPLEMENTED

### What we do
Detrended Fluctuation Analysis (DFA) measures the fractal self-similarity of the RR time series. `alpha1` is the scaling exponent in the short-term range (roughly 4-16 beats):

```
alpha1 < 0.75  → loss of long-term memory → typical for AFib
alpha1 ~ 1.0   → normal sinus rhythm (normal 1/f noise)
alpha1 > 1.2   → pathological rigidity (e.g. severe heart failure)
```

**Script:** `scripts/compute/compute_ppi_dfa.py` — iterates over `ppi_raw`, 5-min windows (≥100 beats), pure-Python DFA (no numpy), gaps > 3 s split segments. Results in table `ppi_dfa`.
**AFES component:** `h10_dfa` in `compute_af_evidence.py` — counts the share of resting windows (is_training=0) with alpha1 < 0.75 per day.

### Why / evidence
One of the most-replicated nonlinear HRV markers in cardiology:
- Peng et al. 1995 (Chaos): foundational description for cardiac rhythm
- Mäkikallio et al. 1998, 1999, 2001: alpha1 < 0.75 in AF patients, replicated multiple times
- Ho et al. 1997: distinguishes AF from normal controls
- Cf. Huikuri et al. 1999 NEJM: DFA as a prognostic marker for cardiac arrest

DFA works specifically for AFib because chaotic AV-node conduction destroys the fractal memory of sinus-node RR variability.

### What it gives us
- The strongest and clinically most robust nonlinear marker we could implement.
- Draws on genuine chest-strap intervals (H10, H7, etc.) — none of our optical markers come close to this data quality.
- Completely independent of all existing AFES components (no overlap with RMSSD, CV_RR, or tpr).

### Scoring logic

Per day, the share of resting windows with α1 < 0.75 is computed (provided
chest-strap data is available). Thresholds from the literature (≥5 %, ≥15 %,
≥30 % window density) yield tiered point values. Multi-day clusters ≥13 % can
precede an ECG-confirmed AFib by 2-3 days — the specific days are determined
from the individual's own data and reported.

### Known limitations (confirmed)
- **Chest-strap wear time only:** structurally 0 points on days without a chest-strap session — the component can contribute nothing at all on those days, regardless of the actual underlying rhythm.
- **Optical sensors excluded:** firmware-side smoothing (±1 bpm/s, affects all optical wrist sources including Polar) produces artificial autocorrelation → alpha1 closer to 1.5 instead of real values. Oura (5 s) and Apple Watch (variable) are likewise unsuitable.
- **Training correctly excluded:** During training, alpha1 physiologically drops (stress) — the is_training flag prevents misclassification.

---

## Candidate 3 — Sample entropy (SampEn) ✅ IMPLEMENTED

### What we do
Sample entropy measures the unpredictability of the RR time series:

```
SampEn(m=2, r=0.2·SDNN, N)
= -ln(number of length-(m+1) patterns that match /
       number of length-m patterns that match)
```

High = irregular (AFib). Low = predictable (normal sinus rhythm). Needs N > 200 beats per window; typically 500-1000 for stable estimates.

### Why / evidence
- Richman & Moorman 2000 (AJP): SampEn superior to ApEn due to the absence of self-matching bias.
- Alcaraz et al. 2010: SampEn significantly higher in AF vs. sinus rhythm in short recordings.
- Similar conceptual logic to DFA, but complementary — measures entropy instead of scaling.

### What it gives us
- A second independent nonlinear marker alongside DFA.
- Confirms the DFA finding when both point to AFib → higher confidence.

### Downsides / risks
- **Parameter-sensitive:** r = 0.2 · SDNN is standard, but if SDNN varies strongly day to day, SampEn isn't comparable across days.
- **High N requirement:** < 200 beats → unreliable estimate. Short chest-strap sessions (< 3 minutes) yield nothing.
- **Computationally heavy:** O(N²) with a naive implementation; not runnable on a large number of intervals at once — a windowed approach is mandatory.
- **Conceptually very similar to DFA:** if DFA works well, SampEn adds little extra information. Both depend on the same root cause (RR chaos in AFib). Double-counting in the score needs to be considered.

### Consequences for AFES
More useful as a validation/calibration tool than as a standalone component. Once DFA is implemented, SampEn can run on the same windows and serve as cross-validation before assigning it a score weight.

**Implemented as:** `h10_sampen` (max. 5 pts, see [AFES.md](AFES.md)) — implemented as a standalone, score-contributing component after all, diverging from the recommendation here (AFDB-calibrated: AUC 0.853, threshold 1.587), not merely as a validation tool without its own weight.

---

## Candidate 4 — P90-P10 HR spread ✅ IMPLEMENTED

### What we do
Instead of max-min of daily HR, we take the 90th minus 10th percentile of HR readings:

```
spread = HR_P90 − HR_P10   (from _WRIST_HR_DEVICES, training excluded)
```

### Why / evidence
- AFib with rapid ventricular response (RVR) typically produces a > 90 bpm daily span.
- Max-min is highly susceptible to single outliers (artifact pixels, faulty PPG).
- P90-P10 is statistically robust while still sensitive to broad HR distributions.
- No dedicated study needed — a direct evolution of the existing `hr_range` logic.

### What it gives us
- Practically no implementation effort — a quantile instead of max/min in the SQL query.
- More robust signal on noisy days (e.g. Polar artifacts from poor skin contact).
- Can replace the existing `hr_range` component (not add to it — that would be double-counting).

### Downsides / risks
- **No new signal:** conceptually identical to `hr_range`, just more robust. No information gain on days without outliers.
- **Threshold calibration needed:** currently ≥90 bpm span → 15 pts / ≥70 bpm → 8 pts. For P90-P10 these thresholds are somewhat lower (since P90/P10 aren't extremes). Calibration against AFib days needed.
- **No standalone score gain:** if we replace `hr_range` with `hr_range_p9010`, the score weight doesn't change — only robustness. No new AFES channel.

### Consequences for AFES
**Recommendation: replace `hr_range` rather than add to it.** This improves the quality of the existing signal without enlarging the score space. No risk of score inflation.

**Implemented as:** exactly as recommended here — `hr_range` (see [AFES.md](AFES.md)) now uses P90-P10 instead of max-min, no separate new component.

---

## Candidate 5 — Lag-1 autocorrelation of RR intervals

### What we do
Compute the lag-1 autocorrelation of consecutive RR intervals per 5-min window:

```
r₁ = Corr(RR[1..N-1], RR[2..N])
```

### Why / evidence
- Sinus rhythm: respiratory sinus arrhythmia produces consecutive RR intervals with positive correlation (r₁ ≈ 0.3-0.7).
- AFib: AV-node conduction responds to chaotic atrial rate; consecutive RR intervals are statistically independent → r₁ ≈ 0.
- Mathematically related to DFA alpha1, but simpler to compute and explain.

### What it gives us
- A simple, interpretable component.
- Can run on the same `ppi_raw` windows as DFA at no extra cost.

### Downsides / risks
- **Redundant with DFA:** both measure the absence of correlation structure. Once DFA is implemented, lag-1 adds little extra information.
- **Optical smoothing:** on smoothed optical HR data, r₁ is artificially high (due to the ±1 bpm/s cap). Only meaningful on chest-strap beat-to-beat data.

### Consequences for AFES
Only useful as a supplementary check during DFA development, not as a standalone component.

---

## Candidate 6 — ML on existing AFES components

### What we do
Train a simple classifier (logistic regression or random forest) on the existing AFES feature vector:

```
Features: ecg, tg, bp_afib, burden, bp_ihb, hr_tachy, hr_nightcv,
          hrv_rmssd, oura_hrv_chaos, h10_preaf, hr_range, aw_high_hr,
          spo2, resp, symptoms, skin_temp  (16 dimensions)
Label: 1 = confirmed AFib day, 0 = normal day
```

### Why / evidence
- The current weights in AFES (50/40/40/... points) are clinically/empirically estimated, not learned from our own data.
- ML could empirically determine which components actually predict AFib days in our data set.
- With a small number of confirmed AFib days and a large number of normal days, this would be a strongly imbalanced problem, but feasible with SMOTE or class weighting.

### What it gives us
- Validation of the existing weights: do they match what the data shows?
- Potentially: automatically optimized weights instead of manual estimates.
- Explains why some high-scoring days aren't ECG-confirmed despite a high score — the model could learn to separate false positives from true positives.

### Downsides / risks
- **Critical with few positive labels:** a small number of AFib days. With 16 features, any ML approach is seriously at risk of overfitting given so few AFib days. LOOCV (leave-one-out cross-validation) is mandatory, results must be interpreted with caution.
- **Circularity risk:** the existing AFES score was partly developed/observed against exactly these AFib days. That makes the days not independent of the features.
- **Not generalizable:** a model trained on a small number of labels has no generalizability beyond this data. Medical decisions should not be based on it alone.
- **Maintenance overhead:** every new AFES component requires model retraining.

### Consequences for AFES
Not suitable as a direct scoring component. Useful as an **analysis tool**: feature importance shows which AFES components correlate most strongly with AFib days. This informs future manual weight adjustments — but doesn't replace them.

---

## Candidate 7 — Nocturnal HR dip ✅ IMPLEMENTED

### What we do
In normal sleep, heart rate typically drops 15-25 % below the pre-evening level (circadian rhythm, parasympathetic dominance during sleep). We measure two things:

```
dip_magnitude = (HR_baseline − HR_nadir) / HR_baseline × 100   [%]

HR_baseline = median HR in the 60 min before sleep onset
HR_nadir    = median HR in the 60-min window around the nocturnal minimum
              (typically between 01:00-05:00)
```

Additionally: trajectory entropy of the minute-by-minute HR course over the night. Instead of the failed second-by-second entropy, 1-minute averages are formed (optical smoothing artifacts average out) and SampEn or CV computed on those.

**Usable sensor classes:** optical wrist with continuous 1 s sampling (ideal), finger ring with ~5 s active sleep sampling (sufficient), optical wrist variable (acceptable with resampling to 1 min).
Sleep onset: from `daily_summary.sleep_start` or an approximate 22:00-07:00 window.

### Why / evidence
- **Circadian HR dip** is an established marker of autonomic function, physiologically related to the better-studied blood-pressure dipping. Absent blood-pressure dipping ("non-dipper") is associated with cardiovascular risk (Hermida et al. 2010, J Hypertension) — that study examines blood pressure, not heart rate; extending it to HR non-dipping is plausible given the shared autonomic mechanism, but isn't directly supported by the same evidence.
- **AFib disrupts the dip directly:** with rapid ventricular response (RVR) at night, HR stays elevated; the nadir shrinks or disappears entirely. Carrington et al. 2005 showed significantly reduced nocturnal HR variation in paroxysmal AF vs. sinus rhythm.
- **AFib episodes during sleep:** when AFib starts and stops during the night, abrupt HR step-changes appear in the trace — not a gradual dip, but jumps. This is visible in the minute-by-minute trace even though optical smoothing destroys second-level resolution.
- **Known autonomic-nervous-system phenomenon:** AFib itself reduces vagal tone; the parasympathetic system can no longer modulate HR → the dip is absent even without RVR.

### What it gives us
- **Uses only optical sensors** — no chest strap needed. This fills the gap on days without a chest-strap session.
- Conceptually distinct from `hr_nightcv`: `hr_nightcv` measures the overall scatter of night HR, the dip measures the systematic shape (trend). A poor sleeper can have high CV and a normal dip; AFib can show low CV (because the fast HR stays constantly elevated) but a missing dip.
- Combined with `hr_nightcv`: if both are abnormal → a stronger AFib signal.
- Max. 8-10 points as a support component would make sense.

### Downsides / risks
- **Sleep-onset timing:** without an exact sleep onset time, an approximate window must be used, which blurs the baseline calculation. On days with irregular sleep times (shift work, travel), incorrect baseline values result.
- **Confounders:** alcohol raises nocturnal HR and can reduce the dip. Fever, medications (beta blockers artificially reduce the dip), exercise shortly before sleep — all of this mimics a missing dip without AFib.
- **Oura gaps:** Oura delivers `respiration_rate` during sleep, but HR sampling is coarser during deep sleep. Brief wake phases or Oura artifacts can distort the nocturnal minimum.
- **Not available every night:** without sleep HR data (device removed, battery dead), no calculation is possible.
- **Calibration needed:** which dip threshold separates normal from AFib nights in our data? The literature values (< 10 % = non-dipper) come from blood-pressure studies; clear cutoffs for HR and AFib are missing.

### Consequences for AFES
New support component `hr_nightdip` (max. 8-10 points):
- Low dip magnitude (< 5 %) → 8 points
- Reduced dip magnitude (5-10 %) → 4 points
- Optional second sub-component `hr_nightdip_entropy` for trajectory irregularity → 5 points

Important: since the dip can also be absent for other reasons (alcohol, fever), it should never reach the direct-evidence category on its own — as a support component with moderate weight, the risk of false-positive contributions is acceptable.

**Implemented as:** `hr_nightdip` (see [AFES.md](AFES.md)) — exactly as proposed here (< 5 % → 8 pts, 5-10 % → 4 pts). The optional `hr_nightdip_entropy` sub-component (trajectory irregularity) was not implemented.

---

## Summary and recommendation

| Candidate | Data basis | Effort | Signal strength | Independence | Recommendation |
|---|---|---|---|---|---|
| **Poincaré SD1/SD2** ✅ | Chest-strap ppi_windows | low | weak (AFDB: AUC 0.537) | low (↔ RMSSD) | **DONE** — `h10_poincare` active in AFES, reduced point cap |
| **DFA alpha1** ✅ | Chest-strap ppi_raw | high | **very high** | **high** | **DONE** — `h10_dfa` active in AFES |
| **Sample entropy** ✅ | Chest-strap ppi_raw | high | high (AFDB: AUC 0.853) | low (↔ DFA) | **DONE** — `h10_sampen` active in AFES, as its own component rather than just a validation tool |
| **P90-P10 spread** ✅ | all optical HR | very low | low | low (= hr_range) | **DONE** — folded into `hr_range` (replaced max-min, no new component) |
| **Lag-1 autocorr.** | Chest-strap ppi_raw | low | medium | low (↔ DFA) | Only as a DFA companion measure |
| **Nocturnal HR dip** ✅ | **optical** (chest strap, ring, smartwatch) | medium | medium | **high** (↔ hr_nightcv) | **DONE** — `hr_nightdip` active in AFES |
| **ML classifier** | AFES feature vector | medium | unclear | — | Only as an analysis tool, not in the score |

**Already implemented:**
- ✅ `hr_nightdip` (8 pts) — adaptive sleep-onset time from the sessions table
- ✅ `h10_dfa` (15 pts) — DFA alpha1 on chest-strap RR intervals
- ✅ `h10_poincare` (6 pts) — Poincaré SD1/SD2 ratio, AFDB-calibrated (AUC 0.537, weak support signal)
- ✅ `h10_sampen` (5 pts) — sample entropy, AFDB-calibrated (AUC 0.853)
- ✅ `hr_range` (15 pts) — identical to Candidate 4 above since the P90-P10 switch
- ✅ `aw_high_hr` (10 pts) — Apple Watch tachycardia alert

**Not proposed in this document, but implemented anyway:**
- ✅ `h10_turning` (8 pts) — turning-point ratio on chest-strap RR data, AFDB-calibrated (AUC 0.882, the strongest single discriminator among the chest-strap support components, see [AFES.md](AFES.md)). No candidate section here — implemented directly, without first appearing in this brainstorm document.
