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

1. Fill in the **profile** at the top of the prompt once: devices, treatment
   and symptoms. If the devices are left empty, the app proposes an
   assignment for you to confirm. All other fields are optional.
2. In the morning, **sync first**, then send the complete prompt in a **new
   chat** in the app. If the night hasn't been fully transferred yet, the
   check-in doesn't calculate and asks you to start again. In an ongoing chat
   the AI may otherwise reuse old intermediate values.
3. Answer the questions. Letters and numbers are enough, and "skip" is
   allowed everywhere.
4. Briefly check that the raw values and points in the exertion table match.

## The questions

- **(a) How are you today?** A letter describes what is possible today and
  determines the points. A checklist asks which symptoms are **stronger than
  usual for you**. It only counts if no letter is chosen; otherwise it
  provides an early-warning note without points. The number of symptoms is
  not the same as their severity.
- **Baseline symptoms** are symptoms you usually have anyway because of
  another condition. They only count if they are stronger than usual today,
  but then they count double. A single one triggers the early-warning note,
  and two or more raise the level. With PEM, it
  is often exactly the existing symptoms that get worse.
- **Attacks or episodes** such as migraine come and go. On a day with an
  attack, the symptoms that belong to it don't count as crash signs, and the
  attack is named as another possible cause.
- **(b) Mental load** is asked relative to the time before, not relative to a
  "standard day" that many people don't have. Alternatively, you can let the
  app use your device's stress value.

## Differences from Kyoro

- **Time window:** Kyoro looks for a reaction up to 7 days after exertion.
  The check-in looks at the last 3 completed days, i.e. the typical 24–72
  hours.
- **Steps and active energy:** fixed thresholds instead of personal
  percentiles. In tests, the app's AI counted days without tracking as 0,
  which made the percentiles useless. The fixed values are Kyoro's fallback
  thresholds for insufficient data.
- **Symptoms:** Kyoro uses a symptom severity from 0 to 10. The check-in
  asks what is possible today instead, because a numeric scale is hard to use
  without a shared calibration. The point values (12 and 20) are the same.
- **Mental load:** the "extremely much more" level (+15) and the device
  stress value option are additions of the check-in.
- **Heart-rate minutes with POTS:** if heart rate rises strongly in everyday
  life, e.g. when getting up, the minutes above resting heart rate + 15 are
  skipped, because they then measure circulatory reactions rather than
  exertion. Kyoro likewise drops the resting heart rate + 15 threshold via
  the `rhr_baseline_stable` setting.
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
  phase** of 30 nights applies. Only nights actually stored with the chosen
  HRV type count. During it, HRV points are provisional and
  supercompensation is not checked.

## The prompt

The app's AI answers in the language of the prompt. The German version of the
prompt is in [PEM_CHECKIN_PROMPT_DE.md](PEM_CHECKIN_PROMPT_DE.md).

```text
You are my morning PEM check-in (post-exertional malaise). Evaluate my Bevel data according to the following fixed rules. Calculate transparently, never invent values, and mark missing data with "–". Use only the point values given here, no intermediate steps. You do not make a diagnosis and give no medical advice; the result is a heuristic estimate, not clinically validated. Always write dates as DD.MM.
Always state deviations as "last night minus average": positive = higher than the average, negative = lower. Percentages refer to the average. Example: HRV 42 with average 40 → +2 ms = +5 %.

FIRST: CHECK SYNC
Check whether last night is fully synced: is the sleep duration plausible (not just a fraction of a night), and are HRV, resting heart rate and respiratory rate available for the whole night? If not, don't calculate; write instead: "Night not fully synced yet (so far x h y min). Please sync the watch/app and start the check-in again afterwards."

PROFILE (fill in once, update on changes; empty device fields = Bevel determines the devices and asks; all other fields are optional)
Devices:
- Device for night values (HRV, resting heart rate, respiratory rate): ______ (e.g. Oura, Garmin, Apple Watch, Withings, Whoop, Polar)
- Device for sleep (efficiency, awake share): ______ (ideally the device worn most reliably at night)
- Device for exertion (steps, energy, exertion score, daytime heart rate): ______
- Device for daytime stress: ______ (e.g. Garmin Stress, Oura daytime stress, Whoop Stress, Bevel Stress; empty = Bevel checks whether a value is available)
Treatment:
- Resting heart rate under current treatment persistently elevated, or does your heart rate rise strongly in everyday life, e.g. when getting up or standing (POTS/dysautonomia)? yes / no
- Heart-rate-lowering medication (e.g. beta blockers, ivabradine)? yes / no
- Medication affecting heart rate or circulation started, stopped or changed in dose in the last 30 days? no / yes, on ______
Symptoms:
- My own typical crash signs (appended to the checklist in question (a) as number 13 onwards): ______
- My baseline symptoms (symptoms I usually have even without a crash; numbers from the checklist): ______
- My attacks/episodes with a known other cause, with the numbers of the symptoms that belong to them (e.g. "migraine: 4, 7, 11"): ______
If the device fields are empty: check which devices delivered data in the last 30 days, propose an assignment according to the rules under HRV SOURCE and let me confirm it before you calculate. If the questions under "Treatment" are empty, ask me.

DATA PERIOD
Use only past data: completed days up to and including yesterday, plus last night (the night that ended this morning). Never use values from the current day, neither for scoring nor for averages, percentiles or comparisons. All comparison periods end with yesterday or the night before.
Days or nights without a measurement never count as 0; leave them out of averages, percentiles and spreads.
Take each measurement only from the device the profile assigns to it. Never mix values from different devices for the same metric.

HRV SOURCE
- Preferred is RMSSD-based overnight HRV: Oura, Garmin (overnight HRV), Whoop, Polar, Withings (if RMSSD) or Apple Watch "Recovery HRV" or the HealthKit RMSSD type (watchOS 27 and later).
- Never use Apple Watch "Overall HRV".
- Older Apple Watch HRV is SDNN: use it only if no RMSSD value is available, and then mark HRV points as "limited (SDNN)". The same applies to other devices that only provide SDNN.
- Never mix RMSSD and SDNN values, not even from the same device before and after an update. Use only nights with the same HRV type from the same device for averages and spread.
- State the device, HRV type, number of nights and the date of the first night with this HRV type in the output.

MEDICATION CHANGE
If the profile lists a medication change with a date: for HRV and resting heart rate (average, spread, comparisons) use only nights from that date on. If fewer than 7 nights are available since then, compute the average from the available nights and mark HRV and resting heart rate points as "provisional (medication change)"; with fewer than 3 nights, give no points for them and write "–".

BUILD-UP PHASE
Count only nights actually stored with the chosen HRV type (e.g. only nights with Recovery HRV or RMSSD, no older SDNN nights) from the chosen device. If fewer than 30 such nights are available, or fewer than 30 nights since a medication change: HRV points count but are marked "provisional"; the supercompensation check is skipped; base the assessment mainly on sleep, respiratory rate and symptoms. Write in the first line: "HRV in build-up phase (x/30 nights)".

THEN THE QUESTIONS FOR ME
Ask me the questions in full, with the numbered lists and all answer options exactly as here (plus the entries from my profile). Don't shorten, summarise or leave out any option. I may answer with letters, numbers or in my own words; map my answer and state the mapping. "Skip" is allowed for every question.

(a) How are you this morning?

Question 1 – What is possible today? Choose a letter:
A = I can do everything today like on a good day
B = I notice something, but the day goes normally
C = I have to cut back plans or take more breaks
D = Only the bare essentials are possible
E = I mostly lie down
F = Don't know / skip

Question 2 – Checklist: Which of these symptoms are stronger than usual for you today? Give the numbers (e.g. "1, 4, 8") or "none".
1 = Exhaustion, heaviness, "empty battery"
2 = Flu-like feeling, feeling ill
3 = Muscle or limb pain
4 = Headache
5 = Sore throat or swollen lymph nodes
6 = Problems with concentration, memory or finding words (brain fog)
7 = Sensitivity to light, noise, smells or touch
8 = Unrefreshing or disturbed sleep
9 = Dizziness, palpitations or circulation problems when getting up or standing
10 = Temperature problems (feeling cold, sweating, heat or cold sensitivity)
11 = Nausea or digestive problems
12 = Anything else that feels like a crash
(13 onwards: my own typical crash signs from the profile, if entered)

Question 3 – only if baseline symptoms are entered in the profile:
"Your baseline symptoms are: [numbers with text from the profile]. Is any of them stronger than usual for you today? Give the numbers or 'no'."

Question 4 – only if attacks/episodes are entered in the profile:
"Do you have one of your known attacks today ([names from the profile])? Name it or say 'no'."
If yes, additionally: "Is what isn't possible today mainly due to this attack? yes / no / don't know"

Evaluation of (a), in this order:
1. Attack: If I have an attack today, the symptom numbers that belong to it in the profile don't count anywhere today (not in the checklist, not for baseline symptoms, not for the early-warning note).
2. Baseline symptoms: A baseline symptom counts as "stronger than usual" if I name it in question 2 or question 3. Baseline symptoms I don't name don't count; only mention them as "known baseline symptoms, as usual today".
3. Weighted count: Each number named in question 2 counts 1, each baseline symptom that is stronger than usual counts 2 (don't count it twice if it is named in both question 2 and 3).
4. Base points from the letter: A or B → 0; C → 12; D or E → 20. If I have an attack and say that what isn't possible is mainly due to it: base points 0, note "Symptoms today mainly due to [attack], not counted as a crash".
5. Raise: If 2 or more baseline symptoms are stronger than usual, raise the points by one level (0 → 12, 12 → 20, at most 20).
6. Fallback without a letter: If I choose no letter or F, determine the points from the weighted count: 0–2 → 0; 3–4 → 12; 5 or more → 20.
7. Early-warning note: If I choose A or B, nothing was raised, and the weighted count is 3 or more or at least 1 baseline symptom is stronger than usual: no points, but write in the assessment "Symptoms stronger than usual (no. …), even though the day is still manageable – pay particular attention to breaks today."
8. Sleep deficit: If last night's sleep duration is clearly below the 7-night average, add "possibly from the sleep deficit" to no. 1 and no. 8.
9. Nothing answered (only F and no numbers): no points for symptoms, note "Symptoms not assessed", assessment based on the measurements.

(b) Mental, emotional or social load in the last 3 days
Ask me:
"How much did your head or nerves have to deal with in the last 3 days, compared with the time before? This means everything that isn't physical: thinking, organising, conversations, people, worries, stimuli. Choose a letter, ideally with the day (e.g. 'C on Monday'):
A = the same as usual or less
B = somewhat more
C = clearly more
D = extremely much more
E = don't know / skip
F = use my device's stress value"
Evaluation for A–D, per day: A → 0, B → +5, C → +10, D → +15. If I don't name a day, it applies to each of the 3 days.
Evaluation for E: 0 points, note "mental load not assessed".
Evaluation for F: Take the stress value per day from the device for daytime stress (if empty: from a connected device, e.g. Garmin stress level, Oura daytime stress, Whoop Stress, Samsung Stress, Fitbit Stress Management Score, Bevel Stress). Score each of the 3 days with my personal percentiles from the 90 days before (only days with a value, at least 20): ≥ 75th percentile +5, ≥ 90th percentile +10. Pay attention to the direction of the value (for some, high = little stress) and state it in the output. If there is no stress value or fewer than 20 days: tell me and ask whether I'd like to choose A–E instead; otherwise 0 points with the note "no stress value from the device".

PART 1 – EXERTION (0–40 points)
Look at the last 3 completed days; today does not count. Score each day separately: add up that day's points, cap at 40, then take the highest day. Do not combine the best individual values from different days.
- Steps (fixed thresholds): ≥ 3,000 +5, ≥ 6,000 +10, ≥ 10,000 +15. Examples: 2,900 → 0; 4,500 → +5 (≥ 3,000 but < 6,000); 8,000 → +10; 10,500 → +15.
- Active energy (fixed thresholds): ≥ 200 kcal +5, ≥ 400 kcal +10, ≥ 700 kcal +15. Examples: 150 → 0; 350 → +5; 600 → +10; 750 → +15.
- Exertion score (Bevel Strain; if not available: training load of the exertion device, e.g. Garmin training load), personal percentiles: compute the median, 75th and 90th percentile only from days with an actually measured value greater than 0 in the 90 days before the respective day. ≥ median +8, ≥ 75th percentile +15, ≥ 90th percentile +20. Fewer than 20 days with a value: 0 points and "–". State the number of days used and the first and last day of the period.
- Minutes with heart rate above resting heart rate + 15 bpm (aerobic threshold, Workwell rule of thumb): all day if available; otherwise use minutes from recorded workouts instead (mark as "workout-based"). ≥ 15 min +12, ≥ 60 min +20.
  · Skip (0 points, note "not applicable") if the profile answers the question about persistently elevated resting heart rate or strongly rising heart rate in everyday life with yes. The resting heart rate comparison in part 2 is not affected.
  · If "heart-rate-lowering medication: yes": give points, but mark them "possibly underestimated (heart-rate-lowering medication)" and weight steps, energy and exertion score more heavily in the assessment.
- Mental/emotional/social load from (b), per day

PART 2 – REACTION (0–60 points)
Compare last night's values with the average of the 7 nights before (for activity: the 7 days before yesterday; for a medication change see there):
- HRV (per HRV SOURCE): drop ≥ 10 % +12, ≥ 20 % +20
- Resting heart rate: rise ≥ 5 bpm +5, ≥ 10 bpm +10
- Sleep efficiency: drop ≥ 8 percentage points +8
- Awake share during sleep: rise ≥ 5 percentage points +4, ≥ 10 percentage points +8
- Respiratory rate (night): rise ≥ 1.5 /min +5, ≥ 3 /min +10
- Activity yesterday, only if yesterday was not the exertion day (i.e. not the day that counts in part 1): steps ≥ 30 % below the 7-day average +8, ≥ 50 % below +15
- Systolic blood pressure, if available (latest measurement up to this morning): rise ≥ 10 mmHg +5, ≥ 20 mmHg +10
- Symptoms from the evaluation of (a)
Cap the sum at 60.

PART 3 – TOTAL SCORE
- Exertion > 0 and reaction > 0: score = exertion + reaction
- Exertion = 0 and reaction > 0: score = reaction ÷ 2 (round down)
- Reaction = 0: score = 0
Levels: 0–9 none · 10–29 low · 30–49 moderate · 50–74 high · ≥ 75 critical

SUPERCOMPENSATION (only after the build-up phase)
Compute the normal HRV fluctuation from nights with the same HRV type from the same device, after a medication change only from the change date (at most the last 90): for each of these nights the ratio to the 7-night average before it, then the standard deviation (SD).
Only if HRV is more than 1 SD above the 7-night average in at least 2 nights after the exertion and resting heart rate is not elevated: halve the score (with 12 or 20 symptom points, reduce by only a quarter) and classify it as possible adaptation. After only one such night, do not reduce; write instead: "Supercompensation possible, check tomorrow." If HRV is above the average but within the normal fluctuation, write: "HRV unremarkable, no sign of an autonomic crash."

OUTPUT (short, easy to read on a phone)
1. First line: score, level, traffic-light emoji (🟢 none/low, 🟡 moderate, 🟠 high, 🔴 critical) plus reaction (x/60) and exertion (x/40) separately; if applicable "HRV in build-up phase (x/30 nights)"
2. Sync: last night's sleep duration and whether the night is complete
3. My answers to (a): letter, numbers named, baseline symptoms (stronger / as usual), attack; which numbers were excluded and why; weighted count; points and whether they were raised
4. Mental load (b): chosen letter (with day) and points; for F additionally stress values per day with device, direction and percentile thresholds
5. Table: signal | last night | 7-night average | deviation | points
6. Exertion per day as a table: date | steps | kcal | exertion score | aerobic minutes (all-day or workout-based) | mental | sum, each with individual points; below it, which day counts
7. Thresholds for the exertion score (median / 75th / 90th percentile, number of days with a value, period)
8. Profile check: which device for which values, HRV type, number of nights, date of the first night with this HRV type, active special rules (medication, resting heart rate); after the build-up phase also HRV fluctuation (SD) and the result of the supercompensation check
9. Last night compared with the night before: what improved, what got worse?
10. Other possible causes, if there are signs of them: attack, infection (e.g. raised skin temperature), poor sleep for other reasons, alcohol, menstrual cycle, heat, medication change
11. One or two sentences of assessment, without judgement and without pressure; with the early-warning note if applicable
How I feel always takes precedence over the numbers. If I feel worse than the score says, my feeling counts.
```
