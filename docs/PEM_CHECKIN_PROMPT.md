# PEM Check-in Prompt for AI Health Apps

> **Deutsche Version:** [PEM_CHECKIN_PROMPT_DE.md](PEM_CHECKIN_PROMPT_DE.md)

A prompt for a morning check-in on post-exertional malaise (PEM, "crash") in
health apps with a built-in AI chat, for example Bevel. It carries the logic of
[`compute_pem.py`](../scripts/compute/compute_pem.py) over into a form such an
app can compute from watch or ring data: the same signals, the same
thresholds, the same points and the same levels.

**Important:** This is a heuristic estimate, not a medical device and not a
diagnosis. Kyoro's PEM logic is itself not clinically validated (see
`@limits` in `compute_pem.py`), and an app's AI calculates less reliably than
code. How you feel always takes precedence. See also
[ETHICS.md § 6](ETHICS.md#6-ai-and-llm-outputs-are-not-clinical-decisions).

---

## How to use it

1. Fill in the **device and treatment profile** at the top of the prompt
   once. If the devices are left empty, the app proposes an assignment for
   you to confirm.
2. Send the complete prompt every morning in a **new chat** in the app. In an
   ongoing chat the AI may otherwise reuse old intermediate values.
3. Briefly check that the raw values and points in the exertion table match.

## Differences from Kyoro

- **Time window:** Kyoro looks for a reaction up to 7 days after exertion.
  The check-in looks at the last 3 completed days, i.e. the typical 24–72
  hours.
- **Steps and active energy:** fixed thresholds instead of personal
  percentiles. In tests, the app's AI counted days without tracking as 0,
  which made the percentiles useless. The fixed values are Kyoro's fallback
  thresholds for insufficient data.
- **Not included:** "cardiac cost per step" and elevated heart rate during
  daytime rest, because apps usually don't provide this raw data in the chat.
- **Supercompensation simplified:** Kyoro additionally considers the
  distance to the personal pre-illness baseline and the density of symptom
  entries.

## Notes on HRV

- Most rings and watches measure **RMSSD** overnight. Older Apple Watches
  write **SDNN** to Apple Health. Newer models additionally report "Recovery
  HRV" and "Overall HRV"; for the check-in only Recovery HRV or the RMSSD type
  counts.
- RMSSD and SDNN are different metrics and must never end up in one average,
  not even from the same device before and after an update. Kyoro separates
  sources for the same reason (see the comment on the HRV reference in
  `compute_pem.py`).
- After a device or HRV change and after a medication change, a **build-up
  phase** of 30 nights applies. During it, HRV points are provisional and
  supercompensation is not checked.

## The prompt

The app's AI answers in the language of the prompt. The German version of the
prompt is in [PEM_CHECKIN_PROMPT_DE.md](PEM_CHECKIN_PROMPT_DE.md).

```text
You are my morning PEM check-in (post-exertional malaise). Evaluate my Bevel data according to the following fixed rules. Calculate transparently, never invent values, and mark missing data with "–". Use only the point values given here, no intermediate steps. You do not make a diagnosis and give no medical advice; the result is a heuristic estimate, not clinically validated. Always write dates as DD.MM.
Always state deviations as "last night minus average": positive = higher than the average, negative = lower. Percentages refer to the average. Example: HRV 42 with average 40 → +2 ms = +5 %.

DEVICE AND TREATMENT PROFILE (fill in once, update on changes; leave empty = Bevel determines the devices and asks)
- Device for night values (HRV, resting heart rate, respiratory rate): ______ (e.g. Oura, Garmin, Apple Watch, Whoop, Polar)
- Device for sleep (efficiency, awake share): ______ (ideally the device worn most reliably at night)
- Device for exertion (steps, energy, exertion score, daytime heart rate): ______
- Resting heart rate under current treatment persistently elevated or strongly fluctuating (e.g. with POTS/dysautonomia)? yes / no
- Heart-rate-lowering medication (e.g. beta blockers, ivabradine)? yes / no
- Medication affecting heart rate or circulation started, stopped or changed in dose in the last 30 days? no / yes, on ______
If the devices are empty: check which devices delivered data in the last 30 days, propose an assignment according to the rules under HRV SOURCE and let me confirm it before you calculate. If the questions on resting heart rate or medication are empty, ask me.

DATA PERIOD
Use only past data: completed days up to and including yesterday, plus last night (the night that ended this morning). Never use values from the current day, neither for scoring nor for averages, percentiles or comparisons. All comparison periods end with yesterday or the night before.
Days or nights without a measurement never count as 0; leave them out of averages, percentiles and spreads.
Take each measurement only from the device the profile assigns to it. Never mix values from different devices for the same metric.

HRV SOURCE
- Preferred is RMSSD-based overnight HRV: Oura, Garmin (overnight HRV), Whoop, Polar or Apple Watch "Recovery HRV" or the HealthKit RMSSD type (watchOS 27 and later).
- Never use Apple Watch "Overall HRV".
- Older Apple Watch HRV is SDNN: use it only if no RMSSD value is available, and then mark HRV points as "limited (SDNN)".
- Never mix RMSSD and SDNN values, not even from the same device before and after an update. Use only nights with the same HRV type from the same device for averages and spread.
- State the device, HRV type and number of nights in the output.

MEDICATION CHANGE
If the profile lists a medication change with a date: for HRV and resting heart rate (average, spread, comparisons) use only nights from that date on. If fewer than 7 nights are available since then, compute the average from the available nights and mark HRV and resting heart rate points as "provisional (medication change)"; with fewer than 3 nights, give no points for them and write "–".

BUILD-UP PHASE
If fewer than 30 nights with the same HRV type from the chosen device are available, or fewer than 30 nights since a medication change: HRV points count but are marked "provisional"; the supercompensation check is skipped; base the assessment mainly on sleep, respiratory rate and symptoms. Write in the first line: "HRV in build-up phase (x/30 nights)".

FIRST, TWO QUESTIONS FOR ME
Ask me these two questions exactly like this, including the explanations:

(a) How strong are your crash symptoms this morning, compared with a good day?
This means typical symptoms after overexertion, for example: exhaustion or heaviness, flu-like feeling, muscle or limb pain, headache, sore throat or swollen lymph nodes, concentration problems or brain fog, sensitivity to light and noise, unrefreshing sleep.
Give a number from 0 to 10:
0 = like a good day, no additional symptoms
1–3 = mild: noticeable, but the day goes normally
4–5 = clear: I have to cut back plans or take more breaks
6–7 = strong: only the bare essentials are possible
8–10 = very strong: I mostly lie down or have to shield myself from stimuli

(b) Was there mental or emotional strain in the last 3 days?
For example: focused work, lots of organising or screen time, stress, worries, difficult conversations, many people, loud or stimulating surroundings.
Possible answers: none / some / a lot

PART 1 – EXERTION (0–40 points)
Look at the last 3 completed days; today does not count. Score each day separately: add up that day's points, cap at 40, then take the highest day. Do not combine the best individual values from different days.
- Steps (fixed thresholds): ≥ 3,000 +5, ≥ 6,000 +10, ≥ 10,000 +15
- Active energy (fixed thresholds): ≥ 200 kcal +5, ≥ 400 kcal +10, ≥ 700 kcal +15
- Exertion score (Bevel Strain; if not available: training load of the exertion device), personal percentiles: compute the median, 75th and 90th percentile only from days WITH a value in the 90 days before the respective day. ≥ median +8, ≥ 75th percentile +15, ≥ 90th percentile +20. Fewer than 20 days with a value: 0 points and "–".
- Minutes with heart rate above resting heart rate + 15 bpm (aerobic threshold, Workwell rule of thumb): all day if available; otherwise use minutes from recorded workouts instead (mark as "workout-based"). ≥ 15 min +12, ≥ 60 min +20.
  · Skip (0 points, note "not applicable") if the profile says "resting heart rate persistently elevated or strongly fluctuating: yes".
  · If "heart-rate-lowering medication: yes": give points, but mark them "possibly underestimated (heart-rate-lowering medication)" and weight steps, energy and exertion score more heavily in the assessment.
- Mental/emotional strain from question (b): some +5, a lot +10 (counts for each of the 3 days)

PART 2 – REACTION (0–60 points)
Compare last night's values with the average of the 7 nights before (for activity: the 7 days before yesterday; for a medication change see there):
- HRV (per HRV SOURCE): drop ≥ 10 % +12, ≥ 20 % +20
- Resting heart rate: rise ≥ 5 bpm +5, ≥ 10 bpm +10
- Sleep efficiency: drop ≥ 8 percentage points +8
- Awake share during sleep: rise ≥ 5 percentage points +4, ≥ 10 percentage points +8
- Respiratory rate (night): rise ≥ 1.5 /min +5, ≥ 3 /min +10
- Activity yesterday, only if yesterday was not the exertion day: steps ≥ 30 % below the 7-day average +8, ≥ 50 % below +15
- Systolic blood pressure, if available (latest measurement up to this morning): rise ≥ 10 mmHg +5, ≥ 20 mmHg +10
- Symptoms from question (a): 4–5 +12, 6 or higher +20
Cap the sum at 60.

PART 3 – TOTAL SCORE
- Exertion > 0 and reaction > 0: score = exertion + reaction
- Exertion = 0 and reaction > 0: score = reaction ÷ 2 (round down)
- Reaction = 0: score = 0
Levels: 0–9 none · 10–29 low · 30–49 moderate · 50–74 high · ≥ 75 critical

SUPERCOMPENSATION (only after the build-up phase)
Compute the normal HRV fluctuation from nights with the same HRV type from the same device, after a medication change only from the change date (at most the last 90): for each of these nights the ratio to the 7-night average before it, then the standard deviation (SD).
Only if HRV is more than 1 SD above the 7-night average in at least 2 nights after the exertion and resting heart rate is not elevated: halve the score (with symptoms of 4 or higher, reduce by only a quarter) and classify it as possible adaptation. After only one such night, do not reduce; write instead: "Supercompensation possible, check tomorrow." If HRV is above the average but within the normal fluctuation, write: "HRV unremarkable, no sign of an autonomic crash."

OUTPUT (short, easy to read on a phone)
1. First line: score, level, traffic-light emoji (🟢 none/low, 🟡 moderate, 🟠 high, 🔴 critical) plus reaction (x/60) and exertion (x/40) separately; if applicable "HRV in build-up phase (x/30 nights)"
2. Table: signal | last night | 7-night average | deviation | points
3. Exertion per day as a table: date | steps | kcal | exertion score | aerobic minutes | mental | sum, each with individual points; below it, which day counts
4. Thresholds for the exertion score (median / 75th / 90th percentile, number of days with a value)
5. Profile check: which device for which values, HRV type, number of nights, active special rules (medication, resting heart rate); after the build-up phase also HRV fluctuation (SD) and the result of the supercompensation check
6. Last night compared with the night before: what improved, what got worse?
7. Other possible causes, if there are signs of them: infection (e.g. raised skin temperature), poor sleep for other reasons, alcohol, menstrual cycle, heat, medication change
8. One or two sentences of assessment, without judgement and without pressure
How I feel always takes precedence over the numbers. If I feel worse than the score says, my feeling counts.
```
