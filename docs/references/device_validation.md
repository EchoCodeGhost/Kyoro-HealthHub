# Device validation: literature basis for confidence scores

> Sources researched and compiled via PubMed. Human review of the
> individual DOI/finding assignments before relying on them as a trustworthy
> source is still pending — spot-checked so far, not fully verified.
> Release took priority over completing this review.

All confidence scores in `compute_canonical.py` and `source_confidence` are
based on peer-reviewed validation studies. Sources retrieved via PubMed.

---

## Polar H10 (chest strap, ECG-based)

**Use:** gold-standard anchor for HR and HRV_RMSSD in `compute_calibrate_sources.py`

| Study | Metric | Finding | Score rationale | DOI |
|--------|--------|--------|-----------------|-----|
| Yang & Ben-Menachem 2023 | HRV (all indices) | "Substantial agreement" with Holter ECG (Lin's CCC); clinically usable | Justifies anchor status | [10.1007/s10877-023-01080-8](https://doi.org/10.1007/s10877-023-01080-8) |
| Topalidis et al. 2023 | Sleep staging via HRV | κ = 0.76 vs. PSG gold standard | H10 as clinical reference | [10.3390/s23229077](https://doi.org/10.3390/s23229077) |
| Hajj-Boutros et al. 2022 | HR | Used as reference device (gold standard) in a three-way comparison | Industry consensus | [10.1080/17461391.2021.2023656](https://doi.org/10.1080/17461391.2021.2023656) |
| Rogers et al. 2022 | Respiration rate | r = 0.85 vs. gas-exchange reference; bias −3.9 br/min | Moderate accuracy, not a primary strength | [10.3390/s22197156](https://doi.org/10.3390/s22197156) |

**Conclusion:** Polar H10 is the de facto standard in the consumer segment
for beat-to-beat intervals. HRV_RMSSD score: **0.95**; HR score: **0.92**

---

## Oura Ring (finger-based PPG, nocturnal)

| Study | Metric | Finding | Score rationale | DOI |
|--------|--------|--------|-----------------|-----|
| Kinnunen et al. 2020 | Nocturnal HR + HRV | r = 0.996 (HR), r = 0.980 (HRV) vs. ECG | Excellent — but COI (Oura authors) | [10.1088/1361-6579/ab840a](https://doi.org/10.1088/1361-6579/ab840a) |
| Cao et al. 2022 | Nocturnal HR + RMSSD | High correlation for HR/RMSSD; LF/HF poor | RMSSD reliable, frequency domain not | [10.2196/27487](https://doi.org/10.2196/27487) |
| Liang et al. 2024 | Nocturnal HRV RMSSD | > 50% of older participants > 10% MAPE; better with 80% validity threshold + 30-min window | HRV accuracy limited, age-dependent | [10.3390/s24237475](https://doi.org/10.3390/s24237475) |

**Conclusion:** Oura Gen 3 measures continuously around the clock. The
available validation studies, however, cover only nighttime measurements —
daytime reliability is barely studied in the literature. Hence a
conservative score choice. Note the conflict of interest in the best study
(Kinnunen 2020: Oura authors). Empirical finding from own data (n=45d vs.
Polar): r=0.593, bias=+0.4 bpm → moderate. HR score: **0.80** (lit.) →
**0.717** (empirically calibrated); HRV_RMSSD score: **0.82** → **0.729**;
SpO2 score: **0.72** (barely validated)

---

## Apple Watch (optical wrist PPG)

| Study | Metric | Finding | Score rationale | DOI |
|--------|--------|--------|-----------------|-----|
| Hajj-Boutros et al. 2022 | HR | CV < 5% across all 5 activities — best optical device in the comparison | Top result for wrist PPG | [10.1080/17461391.2021.2023656](https://doi.org/10.1080/17461391.2021.2023656) |
| Lee et al. 2026 | HR | ICC > 0.94, LoA ≈ ±10 bpm; no significant difference from ECG | Consistent even during resistance training | [10.3390/s26082526](https://doi.org/10.3390/s26082526) |
| Helmer et al. 2022 | HR | r ≥ 0.95, MAPE < 5% in stationary patients | Clinically robust | [10.2196/42359](https://doi.org/10.2196/42359) |
| Falter et al. 2019 | HR | ICC 0.729–0.958 in cardiac patients (intensity-dependent) | Lower intensity shows more scatter | [10.2196/11889](https://doi.org/10.2196/11889) |
| Jiang et al. 2026 | SpO2 | Arms = 5.82% under hypoxemia; systematic overestimation; exceeds the FDA threshold (3%) | Not clinically suitable | [10.2196/85253](https://doi.org/10.2196/85253) |

**Conclusion:** Apple Watch is the most accurate optical wrist device for
HR. SpO2 is not clinically reliable, especially at low saturations. HR
score: **0.87**; SpO2 score: **0.65**

---

## Garmin (optical wrist PPG)

| Study | Metric | Finding | Score rationale | DOI |
|--------|--------|--------|-----------------|-----|
| Lee et al. 2026 | HR | ICC > 0.94; deviates significantly from ECG during resistance training | Good for endurance, worse for strength training | [10.3390/s26082526](https://doi.org/10.3390/s26082526) |
| Helmer et al. 2022 | HR | r ≥ 0.95, MAPE < 5% (Fenix 6 Pro, postoperative patients) | Clinically acceptable at rest | [10.2196/42359](https://doi.org/10.2196/42359) |
| Hajj-Boutros et al. 2022 | HR | CV 2.44–8.80% depending on activity — highest variance in the comparison | Less reliable, activity-dependent | [10.1080/17461391.2021.2023656](https://doi.org/10.1080/17461391.2021.2023656) |

**Conclusion:** Garmin is good for HR, but more variable than Apple Watch,
especially during dynamic movement. HRV via optical PPG is barely
specifically validated → more conservative score. HR score: **0.82**;
HRV_RMSSD score: **0.68**; SpO2 score: **0.68**

---

## CameraHRV (rPPG, smartphone camera)

| Study | Metric | Finding | Score rationale | DOI |
|--------|--------|--------|-----------------|-----|
| Di Lernia et al. 2024 | HR | rPPG high accuracy under controlled conditions (webcam, online) | Promising, but light-dependent | [10.3758/s13428-024-02398-0](https://doi.org/10.3758/s13428-024-02398-0) |
| Ahmad Hatib et al. 2024 | HR | Rs = 0.82 (ages 12–16); SpO2 weak correlation (Rs = −0.25) | HR moderately good; SpO2 not usable | [10.21037/atm-23-1896](https://doi.org/10.21037/atm-23-1896) |

**Conclusion:** rPPG-based HR is usable under controlled conditions.
HRV/RMSSD via rPPG is experimental — the 2 data points in the DB aren't
enough for calibration. HR score: **0.70**; HRV_RMSSD score: **0.55**
(fallback, experimental)

---

## SpO2 — cross-device limitation

Based on PubMed research: all consumer wearables systematically overestimate
SpO2, especially at saturations < 90%. The FDA Arms threshold (< 3%) is not
met by any evaluated consumer device under hypoxemia (Jiang et al. 2026,
[10.2196/85253](https://doi.org/10.2196/85253); Uchimura et al. 2019,
[10.1615/CritRevBiomedEng.2019026110](https://doi.org/10.1615/CritRevBiomedEng.2019026110)).

**Consequence:** SpO2 values from consumer wearables in `health_canonical`
should be read as a trend indicator, not as a clinical measurement. No
device receives a score > 0.75.

---

## Option C: empirical calibration

`compute_calibrate_sources.py` computes, from overlap days in the DB:
- Pearson r per (metric, source) against the anchor (polar_connect)
- Blend score: `0.6 × literature score + 0.4 × r`
- Minimum overlap: 20 days; below that threshold the literature score
  stays active

Concrete overlap-day counts and empirical validation findings (SpO2
three-way comparison, Apple `sleep_spo2_min`, Somneo/Sleep Cycle
correlation) are personal analyses from own device data and therefore
stay local, not part of this public document.
