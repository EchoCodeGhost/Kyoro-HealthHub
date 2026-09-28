<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
# 6-Minute Walk Test (6MWT) — Protocol

> **Deutsche Version:** [6MWT_PROTOCOL_DE.md](6MWT_PROTOCOL_DE.md)

**Standard:** ATS 2002, adapted for home use
**Purpose:** Track functional capacity over time (ME/CFS, Long COVID, heart failure, general fitness tracking)
**Recommendation:** monthly, always at the same time of day, comparable conditions

---

## Preparation

- **Flat, straight surface** — no slope, no stairs, no tight turns (hallway, yard, quiet sidewalk)
- **Distance:** ATS-ideal is a straight 30 m course, back and forth. Shorter (10-20 m) works too, but more frequent turns cost some distance — so always use the same course, to keep results comparable across months
- Measure and mark the course beforehand (e.g. with tape, chalk, etc.)
- Have a pulse oximeter ready (finger clip preferred — more reliable than wearables for post-exercise SpO2)
- Stopwatch / phone
- Notepad or your phone for data entry

**Device recommendation:**

| Measurement | Device |
|---------|-------|
| Resting HR, peak HR, recovery HR | Chest-strap HR monitor (ECG-based, electrical, closer to clinical grade) |
| SpO2 before/after | Wearable with on-demand pulse oximetry, cross-checked against a second device |
| Walking distance | Manual — laps counted × measured course length |
| Borg | Subjective |

**Why a chest strap for HR?** A chest-strap monitor measures electrically (like an ECG), not optically — noticeably more accurate than optical wearable sensors during exertion.

**Why measure SpO2 with two devices in parallel?**
Cross-validation: if the values differ by more than 2-3%, the measurement is unreliable. Record the lower value as the primary value (more conservative, more clinically relevant), and note both individual values.

A finger pulse oximeter (~$15-20) remains the most accurate option and is worth adding, since wrist-based SpO2 sensors are more error-prone right after exertion.

**No warm-up — explicitly prohibited (ATS 2002).**
The test measures functional status as it is in daily life, not performance after preparation. Warming up skews the result and destroys comparability across months. Also avoid physical exertion in the 2 hours before the test.

**Do not perform if:** acute infection, fever, notably worse baseline state than usual, severe PEM (post-exertional malaise) from the previous day.

---

## Outdoor variant

The test also works outdoors (park, quiet residential street) if no suitable hallway is available — with a few extra considerations:

- **Surface:** paved or firmly cobbled, not grass or gravel — a soft/uneven surface changes the walking distance independent of functional capacity and destroys comparability.
- **Route:** avoid traffic lights, pedestrian crossings, or busy intersections where possible — a forced stop for traffic would be miscounted as a rest break, and the clock keeps running regardless (Step 3).
- **Weather:** extreme heat, cold, or wind affect HR, perceived exertion, and can reduce SpO2 measurement accuracy — postpone the test in extreme weather. Note temperature/wind at entry time so later comparisons can account for conditions.
- **Distance measurement:** if no fixed, measured course can be marked, GPS-based distance tracking (phone/wearable) is an alternative — but GPS drift on a short out-and-back course can amount to several meters per lap. Where possible, still prefer a short, precisely measured section (e.g. a marked path segment in a park) over relying on GPS alone.
- Otherwise Steps 1-5 apply unchanged; as with the indoor test, always use the same route.

---

## Procedure

### Step 1 — Rest (10 minutes)
Sit, relax, don't talk.

### Step 2 — Baseline measurement
Measure right before standing up:
- **Resting HR** (bpm)
- **SpO2** (%)
- **Borg RPE** (perceived exertion, scale 6-20)

### Step 3 — Walking (6 minutes)
- **Pace:** self-selected — as fast as you can, but no jogging. No fixed pace.
- Slowing down, stopping, or briefly sitting is allowed — the clock keeps running
- Count the number of stops
- Watch for symptoms: dizziness, chest tightness, severe dyspnea → stop the test

### Step 4 — Immediate measurement (right after 6 min)
- **Walking distance** in meters (laps × course length + remainder)
- **Peak HR** (highest HR during the test, bpm)
- **SpO2** (%)
- **Borg RPE**

### Step 5 — Recovery (sit for 1 minute)
- Measure **recovery HR** after exactly 1 minute

---

## Borg RPE scale

| Value | Perceived exertion |
|------|-----------|
| 6 | no exertion at all |
| 7-8 | extremely light |
| 9-10 | very light |
| 11-12 | light |
| 13-14 | somewhat hard |
| 15-16 | hard |
| 17-18 | very hard |
| 19 | extremely hard |
| 20 | maximal exertion |

---

## Reference values

| Group | Typical walking distance |
|--------|-------------------|
| Healthy adults, men (ATS cohort, ages 40-80, median) | ~576 m |
| Healthy adults, women (ATS cohort, ages 40-80, median) | ~494 m |
| Long COVID / ME/CFS, moderate | < 400 m |
| Severely impaired | < 300 m |

**ATS prediction formula (Enright & Sherrill 1998):** Age is already a continuous input to the formula — no fixed age bands needed, the formula applies to any age within the validity range below.

- **Men:** 7.57 x height (cm) - 5.02 x age - 1.76 x weight (kg) - 309
- **Women:** 2.11 x height (cm) - 2.29 x weight (kg) - 5.78 x age + 667

**Lower limit of normal:** individually predicted value - 153 m (men) or - 139 m (women). Values below this are considered notably reduced.

**Validity range:** healthy adults aged 40-80 (original cohort). Interpret with caution outside this age range.

Reference: Enright PL, Sherrill DL. "Reference equations for the six-minute walk in healthy adults." Am J Respir Crit Care Med. 1998;158(5):1384-1387. Also: American Thoracic Society, "ATS Statement: Guidelines for the Six-Minute Walk Test", 2002.

**Age 20-39:** The Enright/Sherrill formula above is not validated for this age group. A separate, simpler formula (no height/weight) covers healthy adults aged 20-80:
6MWD (m) = 868.8 - (2.99 x age) - (74.7 x sex, men = 0 / women = 1)
Reference: Gibbons WJ, Fruchter N, Sloan S, Levy RD. "Reference values for a multiple repetition 6-minute walk test in healthy adults older than 20 years." J Cardiopulm Rehabil. 2001;21(2):87-93.

**Children and adolescents (< 18):** A separate, validated reference exists for this age group (Geiger R et al., "Six-minute walk test in children and adolescents", J Pediatr. 2007;150(4):395-399, ages 3-18, height- and sex-dependent), deliberately not reproduced as a formula here since the exact regression coefficients need to come from the original paper and this protocol is written for the ATS 2002 adult standard. For rough orientation from the original study: median walking distance is roughly 655-730 m, increasing with age in boys and roughly flat in girls.

**Age > 80:** Population-based prediction formulas are sparse and less well validated here (the Enright/Sherrill cohort goes up to 80, some European studies to 85). At this age, it's more useful to evaluate the individual's trend against their own baseline than against a population-predicted value.

---

## Entering data into Kyoro-HealthHub

```bash
python3 scripts/importers/import_6mwt.py --manual
```

Or output a CSV template:
```bash
python3 scripts/importers/import_6mwt.py --template
```
→ Save the file to `imports/6mwt/YYYY-MM-DD.csv`, then:
```bash
python3 scripts/importers/import_6mwt.py
```

---

## Note on PEM / Post-Exertional Malaise

In ME/CFS and Long COVID, this test can trigger PEM.
**Plan a buffer:** at least 2-3 hours of rest afterward.
Do not perform the test on crash days or after a bad night's sleep.
The result is only comparable if starting conditions are similar — so always record time of day, sleep quality, and current state.
