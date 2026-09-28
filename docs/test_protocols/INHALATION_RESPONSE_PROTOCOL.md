<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
# Measurement Protocol: Inhalation + SpO2 Response

> **Deutsche Version:** [INHALATION_RESPONSE_PROTOCOL_DE.md](INHALATION_RESPONSE_PROTOCOL_DE.md)

**Purpose:** Documenting the SpO2/HR response to an inhaled treatment (e.g. saline/ectoine inhalation, bronchodilator)
**Device:** Finger pulse oximeter (medical device)
**Parallel recording:** set a wearable tag "inhalation/breathing therapy" if available (for overnight SpO2 correlation)

---

## Standard procedure

| Step | Time point | Action |
|---------|-----------|--------|
| 1 | T−5 min | Sit calmly, attach the pulse oximeter (index or middle finger) |
| 2 | T−2 min | **Read baseline:** note SpO2 + HR (value should be stable, not fluctuating) |
| 3 | T=0 | Start inhalation, pulse oximeter stays on the finger |
| 4 | During | Note any notable changes (SpO2 drops/rises, HR response) |
| 5 | T+5 min | First follow-up value right after inhalation ends |
| 6 | T+15 min | Second follow-up value |
| 7 | T+30 min | Third follow-up value (optional, if time permits) |
| 8 | Evening | Set wearable tag "inhalation/breathing therapy" if available |

---

## Measurement log (template)

### Date: ________ Start time: ________

**State before inhalation:**
- Breathing: ☐ free  ☐ mildly restricted  ☐ notably restricted  ☐ tightness
- Mucus sensation: ☐ none  ☐ little  ☐ a lot  ☐ thick/sticky
- General complaints: ___________________________________

**Measurements:**

| Time point | SpO2 (%) | HR (bpm) | Note |
|-----------|----------|----------|-----------|
| T−2 min (baseline) | | | |
| During inhalation | | | e.g. "coughing", "mucus loosening" |
| T+5 min | | | |
| T+15 min | | | |
| T+30 min (opt.) | | | |

**Breathing after inhalation:**
- ☐ notably freer  ☐ somewhat freer  ☐ unchanged  ☐ worse

**Other notes:**
___________________________________

*(Copy this section for each additional measurement.)*

---

## Interpretation notes

**What a positive finding would look like:**
- SpO2 at T+5 or T+15 ≥ 1-2 points above baseline → demonstrates airway obstruction from mucus/inflammation
- Effect lasts ≥ 1 day (overnight SpO2 higher the following night) → the inhalation has an overnight carry-over effect

**What can suggest an inflammatory/reactive airway component** (e.g. in mast cell disorders, asthma, COPD):
- Baseline SpO2 varies day to day by ≥ 2 points (without a physical cause)
- SpO2 typically drops in the evening/at night and is lower in the morning
- Inhalation breaks the pattern for several days

**For documentation to your doctor:**
- Bring this protocol together with the wearable's daily trend and overnight SpO2 trend to your rheumatologist/pulmonologist
- For nighttime abnormalities: check whether polygraphy is indicated (sleep apnea vs. nocturnal bronchoconstriction as a differential)

---

## Entering data into Kyoro-HealthHub

Measurements can be logged via the symptom/note import paths; for structured analysis, correlate wearable SpO2 data and inhalation timestamps via the day tag (see `scripts/analysis/` for the analysis script matching your device).
