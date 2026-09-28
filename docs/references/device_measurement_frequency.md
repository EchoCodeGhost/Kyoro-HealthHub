# Wearables — Measurement Frequency & HRV Capabilities

Generic device capabilities (manufacturer specs/public documentation), not
personal measurement data. Empirical validation findings from own data live
in `docs/references/device_validation.md` (only aggregate figures such as
correlations, no raw values), or, where they contain raw measurements, stay
local in `intern/` (not part of this repo).

---

## Glossary: HRV, RMSSD, SDNN

**HRV (heart rate variability)** — umbrella term: the variation in the time
intervals between successive heartbeats. Not a single value, but a whole
family of metrics (RMSSD, SDNN, LF/HF, pNN50, ...) that each capture a
different aspect of this variation.

**RMSSD** (Root Mean Square of Successive Differences) — short-term HRV
metric: the difference between each pair of adjacent beat intervals,
squared, averaged, square-rooted. Captures almost exclusively
**parasympathetic (vagal) activity** (respiratory sinus arrhythmia — the
vagus nerve modulates heart rate in step with breathing, which is fast
enough to produce RMSSD; the sympathetic nervous system reacts too slowly
for that). That's why it's the standard marker for "how strongly is the
vagus braking right now." Higher = more vagal activity, usually "better" at
rest (recovery). Normally drops on standing up (vagal withdrawal) — an
excessive drop, coupled with a sharp HR jump, is the pattern heuristic
orthostatic detection looks for.

**SDNN** (Standard Deviation of NN Intervals) — total variability of all
beat intervals in a measurement window. Captures both short-term (vagal)
and slower influences (thermoregulation, hormonal cycles, circadian rhythm,
sympathetic activity) — less specific to the vagus than RMSSD, but a more
comprehensive picture of the system's overall adaptability. Often used for
longer measurement windows (e.g. 24h), RMSSD more for short windows (5
min., one night). Not 1:1 interchangeable with RMSSD, even though both are
called "HRV" — they capture different physiological components. A device
that only reports SDNN therefore isn't directly comparable to a device that
only reports RMSSD, without conversion or separate consideration.

---

## Comparison table: heart rate & HRV

| Device | HR passive (daily life) | HR active (exercise) | HRV measurement | HRV metric | HRV continuous? |
|---|---|---|---|---|---|
| Polar H10 (chest strap) | Beat-to-beat RAW (RR intervals, ms) | Beat-to-beat RAW | Any time during recording | RMSSD | Only during active recording |
| Polar H7 (chest strap) | Beat-to-beat RAW (RR intervals, ms) | Beat-to-beat RAW | Any time during recording | RMSSD | Only during active recording |
| Polar Loop | 1s continuous | 1s continuous | Nightly Recharge (sleep) | RMSSD | No (sleep only) |
| Polar Ignite 2 | 1s continuous | 1s continuous | Sleep (5-min. window) | RMSSD | No |
| Polar Vantage V3 | 1s continuous | 1s continuous | Sleep (5-min. window) | RMSSD | No |
| Polar M430 | 1s continuous | 1s continuous | — | — | No |
| WHOOP 4.0/5.0 | ~100ms (10 Hz) | ~100ms (10 Hz) | Sleep only (5-min. window) | RMSSD | No |
| Oura Ring 4 | 5s continuous (API export); internally 1s PPG (not exported) | — (no exercise mode) | Sleep (5-min. window) | RMSSD | No (sleep only) |
| Garmin Fenix 6 Pro | ~every 2 min. | ~every 2 sec. | First 5h of sleep | RMSSD | No |
| Apple Watch S9 | ~75s passive (measured; varies 75–225s) | 1s (active workout) | ~every 2h | SDNN | No |
| Fitbit Sense 2 / Charge 6 | ~every 1 min. | ~every 1 min. | Sleep only | RMSSD | No |
| Samsung Galaxy Watch 6/7 | ~every 1 min. | ~every 1 min. | Sleep only | RMSSD | No |

**Why Polar H7/H10 (chest strap) count as gold standard:** unlike every
optical wrist/ring device in this table (PPG — light through the skin),
H7/H10 sit with real ECG electrodes directly on the skin and detect the R
wave electrically, not optically. That yields significantly more precise,
less motion-sensitive beat-to-beat timing — which is why they're the
reference anchor for HR/RMSSD in `compute_calibrate_sources.py`.
Peer-reviewed validation (with DOI) for this: `docs/references/device_validation.md`.
**Important limitation:** it's still NOT a diagnostic ECG (see table below)
— the chest strap only outputs the time intervals between heartbeats (RR
intervals), no displayable ECG waveform (P-QRS-T) for cardiological rhythm
assessment.

---

## Why is there no 24/7 second-by-second device?

Three physical reasons:

1. **Battery** — Continuous PPG activation at a per-second cadence would
   drain the battery in under 24 hours.
2. **Data volume** — Beat-to-beat 24/7 = ~100,000 RR intervals per day. No
   consumer device is built for that.
3. **Statistics** — HRV windows under 5 minutes are barely clinically
   meaningful. 5-min. RMSSD is the established standard.

---

## SpO2 measurement frequency (for sleep apnea relevance)

| Device | Device type | SpO2 frequency (sleep) | Suitable for sleep apnea? |
|---|---|---|---|
| Wellue O2Ring | Ring, dedicated pulse oximeter | Every 4 seconds | Yes — purpose-built for this, including night alarm |
| Beurer PO 40 / PO 60 | **Fingertip pulse oximeter** | Instantaneous reading, spot check | No — per the manufacturer manual (both models), not intended for continuous monitoring, no alarm function, max. 2h measurement duration per session recommended |
| Oura Ring 4 | Ring, multi-sensor | Measured internally ~every 15 min., but only ONE aggregated value exported per night | Limited — no raw-data access to the individual readings |
| Apple Watch S9 | Wrist, multi-sensor | Sporadic (background) | Limited |
| Polar (consumer sports watches, no model with continuous overnight SpO2 feature) | Wrist, multi-sensor | Individual readings/spot check | No |
| Garmin Fenix 6 Pro | Wrist, multi-sensor | Sleep average | No |

**On fingertip pulse oximeters in general** (Beurer and comparable models
from other manufacturers): this device class is often the medically most
accurate single reading (Beurer PO60, e.g., is a CE Class IIa medical
device), but **fundamentally designed as a spot-check device** — the finger
has to sit still in the clip, which rules out continuous overnight
measurement by the form factor itself (unlike a ring or band that can be
worn continuously). This isn't a Beurer-specific detail but a property of
the fingertip-clip form factor in general.

---

## Blood pressure measurement frequency

| Device | Measurement frequency | Continuous possible? |
|---|---|---|
| Upper-arm/wrist blood pressure monitor (Omron etc.) | Spot check, manually triggered | No — fundamentally physical (oscillometry/cuff), no continuous measurement |
| Withings ScanWatch/BPM | Spot check, manually triggered | No, same principle |
| Optical wrist-PPG estimation (various fitness watches, "blood pressure trend") | Continuous possible, but uncalibrated | Technically yes, but without regular calibration against a cuff the estimate drifts — not approved as medically accurate by any regulatory body |
| Ambulatory 24h blood pressure monitor (ABPM, via physician) | Every 15–30 min. automatically, including at night | Yes — the only consumer-adjacent path to true day/night dipping analysis |

**Fundamental problem:** genuine continuous, beat-by-beat blood pressure
measurement without a cuff (e.g. via pulse transit time/PTT) currently only
exists in research/clinical devices, not in the consumer segment with a
robust approval.

---

## ECG measurement frequency

| Device | Recording duration | Triggering | Leads | Provides waveform (P-QRS-T)? |
|---|---|---|---|---|
| Apple Watch (Series 4 onward) | 30 seconds per reading | Manually triggered | 1 (single-lead, arm-to-arm) | Yes |
| Polar/Garmin with ECG feature | 30 seconds per reading | Manually triggered | 1 | Yes |
| KardiaMobile 6L | 30 seconds to several minutes | Manually triggered | 6 | Yes |
| Withings BPM Core | ~30 seconds, during the blood pressure measurement | Manually triggered (part of the BP measurement, see BP table above) | 1 (single-lead, hand-to-hand via case electrodes) | Yes |
| Polar H7/H10 (chest strap) | Continuous during active recording | Manually started, then continuous | 1 (internal) | **No** — only RR intervals (time gaps) are exported, no displayable waveform |
| Holter ECG (via cardiologist) | 24–48h continuous | Automatic, continuous | Usually 2–12, device-dependent | Yes |
| Zio Patch (iRhythm) | Up to 14 days continuous | Automatic, continuous | 1 (patch lead) | Yes |

**On the Polar H7/H10:** real ECG electrodes technically sit on the skin
(not PPG) — that makes beat-to-beat timing very precise (see table above,
gold-standard anchor for HR/HRV). But the chest strap itself only exports
the RR intervals derived from that, not the underlying voltage curve — a
cardiological rhythm assessment (detecting atrial fibrillation, ST
elevations, etc.) needs the waveform, which requires one of the devices
marked "Yes" in the last column.

**Fundamental problem:** all consumer ECG devices with a waveform only
provide snapshots (spot checks lasting seconds to minutes), not continuous
recording — capturing rare/paroxysmal rhythm events requires a long-term
device (Holter, patch); a spot-check ECG can't, by design, capture an event
that isn't happening right at that moment.

---

## Respiration rate measurement frequency

| Device | When measured | Available during the day? |
|---|---|---|
| Apple Watch | Only during sleep (documented HealthKit sleep feature) | No — structural device limit, not a configuration option |
| Garmin (modern models with respiration sensor) | Continuous, including during the day | Yes |
| Oura Ring | Only during sleep | No |
| Whoop | Only during sleep | No |

---

## Skin temperature measurement frequency

| Device | When measured | Resolution |
|---|---|---|
| Oura Ring | Continuous during sleep | Deviation from personal baseline, no absolute value |
| Polar (models with skin temperature sensor) | Continuous, device-dependent sampling | Absolute value in °C |
| Apple Watch (Series 8/Ultra onward) | Only during sleep | Deviation from personal baseline, no absolute value |
| Withings ScanWatch | Continuous during sleep | Absolute value |

---

## CGM / glucose measurement frequency

| Device | Frequency | Approval | Calibration |
|---|---|---|---|
| Dexcom G6/G7 | Every 5 minutes, continuous | FDA/CE-approved medical device | G6 factory-calibrated or with finger-stick, G7 factory-calibrated |
| FreeStyle Libre 3 | Continuous transmission (~every minute) | FDA/CE-approved medical device | Factory-calibrated |
| FreeStyle Libre 2 (classic scan mode) | Sensor measures every minute, but only retrievable via manual scan (otherwise only alarm events) | FDA/CE-approved medical device | Factory-calibrated |
| Optical/non-invasive glucose estimation (various fitness wearables) | Advertised as continuous | **No device using this method has yet received approval as an accurate blood glucose meter** | — |

**Fundamental problem/context:** CGM is the only category in this overview
where "continuous" is actually the norm (the sensor's principle: a
subcutaneous needle, permanently in tissue) — unlike HR/SpO2/BP, where
continuous consumer measurement is the exception. Non-invasive (needle-free)
optical glucose estimation via PPG remains, despite recurring marketing
announcements, without a validated, approved implementation.

---

## Sleep stage detection

| Device | Method | Comparison to the gold standard |
|---|---|---|
| Polysomnography (PSG, sleep lab) | EEG (brain waves) + EOG + EMG, direct neurological measurement | Gold standard — all consumer devices are validated against this |
| Oura, Apple Watch, Garmin, Whoop, Fitbit (all consumer wearables) | Indirect: motion sensor (accelerometer) + HR/HRV pattern, algorithmically converted to light/deep/REM sleep | No direct brain-wave measurement — accuracy varies by device/algorithm version, validation studies usually show moderate to good agreement for total sleep time, weaker for individual sleep stages (especially light sleep vs. wake) |

**Fundamental problem:** no consumer wearable measures sleep stages
directly — all of them derive it from movement and cardiac signals. This is
fundamentally different from HR/SpO2, where at least in principle a direct
physiological measurement takes place.

---

## Steps / activity

Unlike the other categories here, **continuous measurement** is the norm
for steps/activity, not the exception — practically every wearable with an
accelerometer counts continuously. The relevant difference isn't in the
frequency but in the **counting method/wear position**:

| Wear position | Typical accuracy | Known weakness |
|---|---|---|
| Wrist (most fitness watches/rings) | Good for walking/running | Overcounts during repetitive arm movements (cycling, washing dishes), undercounts during activities without arm movement (pushing a stroller, some strength exercises) |
| Hip (older pedometers, clinical actigraphy) | Historically considered more accurate for pure walking | Barely used anymore in the consumer segment |
| Smartphone (in a pocket) | Inaccurate, device-dependent | Counts nothing if the phone isn't carried along |

---

## AFib detection (atrial fibrillation)

Two fundamentally different mechanisms, often combined in the same device:

| Device | Mechanism | Mode | Medically approved? |
|---|---|---|---|
| Apple Watch (Series 4 onward, with ECG feature) | Active single-lead ECG (manually triggered) | Spot check, 30s | Yes — FDA-cleared (ECG app), CE marking |
| Apple Watch (all models with optical sensor) | Passive irregular-rhythm notification (PPG-based, background) | Continuous in the background, notification only when suspected, no diagnostic ECG | Yes — FDA-cleared as a notification feature, doesn't replace a diagnosis |
| KardiaMobile 6L | Active 6-lead ECG | Spot check, manual | Yes — FDA-cleared, CE medical device |
| Fitbit (current generation with ECG app) | Active single-lead ECG + passive PPG notification | Both, like Apple | Yes — FDA-cleared |
| Samsung Galaxy Watch (Watch 3 onward, with ECG feature) | Active single-lead ECG | Spot check, manual | Yes — FDA-cleared (regional availability varies) |
| Whoop (current generation, with ECG feature) | Active single-lead ECG | Spot check, manual | Yes — FDA 510(k)-cleared |
| Polar H7/H10, plain fitness chest straps without AFib feature | No AFib detection algorithm | — | No — provides only raw data (RR intervals), no rhythm interpretation |
| CardiacSense CSF-3 | Continuous beat-by-beat monitoring | Continuous, not just spot check | Yes — FDA AND CE-MDR approved for continuous AFib monitoring (as of the last-checked approval info; verify current status before buying) |

**Important distinction:** an "AFib notification" (passive, PPG-based, in
the background) is NOT a diagnosis — it only triggers a hint that an
irregularity might be present. Only an active single-lead ECG (or a
clinical multi-lead ECG) produces a displayable waveform that's actually
suitable for diagnosis. Most "AFib detection" marketing claims from fitness
wearables refer to the passive notification feature, not to a diagnostic
ECG.

---

## Medically validated devices — full overview

Consolidated from all tables above: only devices with a **specific FDA
approval (510(k)/De Novo) or CE marking as a medical device** for the
respective parameter — not to be confused with a general CE mark as an
electrical device (which practically every consumer wearable has, but says
nothing about medical accuracy).

| Device | Validated parameter | Approval type |
|---|---|---|
| Apple Watch (Series 4 onward) | ECG (single-lead spot check) | FDA-cleared, CE |
| Apple Watch (all with optical sensor) | Irregular-pulse notification | FDA-cleared (notification, not a diagnosis) |
| KardiaMobile 6L | ECG (6-lead spot check) | FDA-cleared, CE medical device |
| Fitbit (current generation) | ECG (single-lead spot check) | FDA-cleared |
| Samsung Galaxy Watch (Watch 3 onward) | ECG (single-lead spot check) | FDA-cleared |
| Whoop (current generation) | ECG (single-lead spot check) | FDA 510(k)-cleared (K243236) |
| Beurer PO 40 / PO 60 | SpO2 (spot check) | CE medical device, MDR Class IIa |
| CardiacSense CSF-3 | Continuous beat-by-beat HR + SpO2, AFib monitoring | FDA- and CE-MDR-approved |
| Holter ECG / Zio Patch / ActiHeart | ECG or actigraphy (clinical) | Medical device, prescribed by a physician |
| Ambulatory 24h blood pressure monitor (ABPM) | Blood pressure, day/night | Medical device, prescribed by a physician |
| Dexcom G6/G7, FreeStyle Libre 2/3 | Continuous glucose | FDA/CE-approved medical device |

**Not on this list = no known medical approval for the named parameter**
(even if the device is otherwise widely used/trusted) — SpO2/HRV/respiration
rate/sleep stages from fitness watches and rings are considered
industry-wide "wellness grade," not medically approved, even if the same
device has a genuine approval for a DIFFERENT parameter (e.g. ECG) —
approvals always only apply to the specific tested parameter, never to the
whole device by default.

---

## Medical alternatives (via physician/cardiologist)

| Device | Frequency | Duration | Availability |
|---|---|---|---|
| Holter ECG | 500 Hz, beat-to-beat | 24–48h | Via cardiologist, covered by German statutory health insurance |
| Zio Patch (iRhythm) | 200 Hz continuous | 14 days | Prescription, private pay |
| ActiHeart | 128 Hz | 7 days | Research/clinical only |
