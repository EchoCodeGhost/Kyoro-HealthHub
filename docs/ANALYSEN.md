# Analyses — Overview and Guide

All scripts run from the project root: `cd ~/Kyoro-HealthHub`

---

## Pipeline: Compute → Analyse

```
imports/           write to DB          pre-process           analyse
  import files  →  import_all.py  →  compute_all.py  →  analyse_*.py
```

**Compute scripts must run before analysis scripts** — they populate the derived tables
(`af_evidence_scores`, `arrhythmie_episoden`, `ppi_dfa`, `health_canonical`, `sleep_hypnogram`,
`clinical_findings`, `data_quality_flags`) that the analysis scripts read from.

After a fresh import:
```bash
python scripts/import_all.py --update
python scripts/compute_all.py
```

---

## Compute Scripts (Pre-processing)

These scripts write to the DB — they produce intermediate tables used by the analysis layer.

### `compute_af_evidence.py` — AF Evidence Score (AFES)

```bash
python scripts/compute/compute_af_evidence.py --update
python scripts/compute/compute_af_evidence.py --recompute          # full recompute
python scripts/compute/compute_af_evidence.py --from 2026-01-01
```

**What it does:** Calculates a daily score 0–100 from 21 signal channels (see `docs/AFES.md` for the full list and weights).  
**Method:** Max-aggregation (direct evidence) + sum-aggregation capped at 50 (support).  
Writes: `af_evidence_scores`.  
**Value:** Central AFib monitoring tool — one risk estimate per day from all available devices combined.
Shows patterns, precursors, and confirmed episodes. → See [AFES.md](AFES.md)

---

### `compute_ppi_dfa.py` — DFA alpha1 on H10 data

```bash
python scripts/compute/compute_ppi_dfa.py --update
python scripts/compute/compute_ppi_dfa.py --recompute              # all PPI beats
python scripts/compute/compute_ppi_dfa.py --from 2026-01-01
```

**What it does:** Detrended Fluctuation Analysis on beat-to-beat RR intervals.  
**Method:** Pure Python implementation. 5-minute non-overlapping windows, ≥ 100 beats/window,
gaps > 3 s split segments. alpha1 (short-range, scales 4–16 beats) + alpha2 (long-range, if N ≥ 256).  
Writes: `ppi_dfa`.  
**Value:** Strongest non-optical AFib precursor signal. Responds 2–3 days before ECG-confirmed AFib.
Only available during H10 wear time.

---

### `compute_arrhythmia.py` — Tateno & Glass arrhythmia detection

```bash
python scripts/compute/compute_arrhythmia.py --update
```

**What it does:** Detects arrhythmia episodes from 5-min PPI windows.  
**Method:** H10/H7: Tateno & Glass 2001 (TPR > 0.60 + RMSSD ≥ 30 ms to reduce false alarms).
Optical sources: CV-RR > 0.15 (softer criterion).  
Writes: `arrhythmie_episoden`.  
**Value:** Detects concrete episodes over time; basis for `analyse_arrhythmia.py` and AFES `tg` component.

---

### `compute_hrv_advanced.py` — Extended HRV metrics

```bash
python scripts/compute/compute_hrv_advanced.py --update
```

**What it does:** Calculates all HRV metrics per 5-min window, analogous to KubiosHRV.  
**Method:** Time domain (RMSSD, SDNN, pNN50), Poincaré (SD1, SD2, ratio),
frequency domain (LF, HF, LF/HF via Welch 4 Hz), DFA alpha1, Sample Entropy (m=2).  
Writes: `ppi_windows`.  
**Value:** Full HRV analysis as the basis for `h10_preaf`, `analyse_dfa_alpha1.py` and more.

---

### `compute_canonical.py` — Canonical metrics (best-source selection)

```bash
python scripts/compute/compute_canonical.py --update
```

**What it does:** Selects the best source per (date, metric) by confidence ranking.  
Writes: `health_canonical`.  
**Value:** Resolves multi-device redundancy — one number per metric per day without manual filtering.

---

### `compute_clinical.py` — Clinical criteria

```bash
python scripts/compute/compute_clinical.py --update
```

**What it does:** Algorithmically evaluates clinical findings (POTS criterion ΔHR ≥ 30 bpm,
HRV changepoints) before LLMs interpret the data.  
Writes: `clinical_findings`.  
**Value:** Structured findings for doctor's reports; basis for `analyse_clinical_findings.py`.

---

### `compute_sleep_hypnogram.py` — Unified sleep stage profile

```bash
python scripts/compute/compute_sleep_hypnogram.py --update
```

**What it does:** Merges sleep stages from Polar and Oura into a unified table.  
Writes: `sleep_hypnogram`.  
**Value:** Enables cross-device sleep stage analysis.

---

### `compute_stress.py` — Stress score

```bash
python scripts/compute/compute_stress.py --update
```

**What it does:** Calculates daily stress score from RMSSD, HRV SDNN, RHR, sleep, training.  
Writes: `daily_stress`.

---

### `compute_postinfectious.py` — Reaction-pattern detection

```bash
python scripts/compute/compute_postinfectious.py --update
```

**What it does:** Rolling 28-day baseline → reaction-pattern signal when HRV/RHR on day N+1
is more than 1 SD below/above baseline following exertion on day N.  
Also records `had_sport` (training on that day) and `sport_prior_3d` (training on any of the 3 preceding days) to enable 2×2 sport-context analysis downstream.  
Writes: `pem_correlation`.

---

### `compute_quality.py` — Data consistency

```bash
python scripts/compute/compute_quality.py              # full scan
python scripts/compute/compute_quality.py --severity critical
python scripts/compute/compute_quality.py --summary
```

**What it does:** Checks for anomalies in the DB before AI analyses. Writes: `data_quality_flags`.  
**Value:** Prevents bad data (duplicates, jumps, outliers) from distorting analysis results.

---

### Additional compute scripts in the dependency chain

These run as part of `compute_all.py` (see its header for the full 22-step order) but weren't yet listed above:

| Script | What it does | Writes |
|---|---|---|
| `compute_ecg_rpeaks.py` | Detects R-peaks in 30-s ECG raw signals (512 Hz, µV, lead I) via Pan-Tompkins | `ecg_rpeaks` |
| `compute_bp_pulse_bridge.py` | Mirrors pulse values captured alongside each BP measurement | `measurements` (metric='heart_rate') |
| `compute_hr_zones.py` | Distributes HR samples across five zones, computes daily budget | `daily_hr_zones` |
| `compute_gesamtpensum.py` | Combines physical HR load with subjective domain loads into a total load score | `daily_energy_summary` |
| `compute_hrv_anomaly.py` | Computes daily Z-scores for RMSSD and DFA alpha1 | `measurements` (hrv_anomaly_rmssd_z, hrv_anomaly_dfa1_z, …) |
| `compute_pem.py` | Scores daily evidence for post-exertional malaise | `pem_evidence_scores` |
| `compute_sleep_spo2.py` | Extracts nocturnal SpO2 minimum from raw measurements | `measurements` (metric='sleep_spo2_min') |
| `compute_symptoms.py` | Normalises raw symptom labels (DE/EN) onto a unified vocabulary | `symptoms_canonical` |
| `compute_personal_baseline.py` | Personalised baseline from best/stable periods (four methods) | `personal_baseline` |
| `compute_daily_context.py` | Materialises a wide daily context table (one row per day, all domains) | `daily_context` |
| `compute_acute_events.py` | Computes a daily NEWS2-inspired severity score | `acute_events` |
| `compute_calibrate_sources.py` *(optional, not in the core 22-step chain)* | Computes Pearson r per (metric, source) against a configured gold-standard anchor | `source_confidence` |
| `compute_histamine_triggers.py` *(optional, not in the core 22-step chain)* | Derives candidate food triggers by temporally correlating symptoms with meals | `food_triggers` |

---

## Query Tools (`scripts/query/`)

Interactive tools — run on pre-computed data.

### `health_query.py` — AI query

```bash
python scripts/query/health_query.py                   # interactive
python scripts/query/health_query.py hrv
python scripts/query/health_query.py sleep
python scripts/query/health_query.py "AFib last month"
```

Natural language query of the DB via LLM (OpenVINO / Anthropic).

---

### `health_report.py` — Doctor's report

```bash
python scripts/query/health_report.py
python scripts/query/health_report.py --focus kardio
python scripts/query/health_report.py --period 2026
```

Generates structured Markdown for doctor appointments — all key metrics, clinically classified.

---

### `health_visualize.py` — Dashboard PDF

```bash
python scripts/query/health_visualize.py
python scripts/query/health_visualize.py --only hrv,stress
python scripts/query/health_visualize.py --format png
```

Multi-page PDF dashboard with plots across all years.

---

### `health_ecg.py` — ECG analysis

```bash
python scripts/query/health_ecg.py
python scripts/query/health_ecg.py --plot
```

R-peak detection, HR from ECG, RR variability, rhythm irregularities on Apple Watch ECG CSVs.

---

## Analysis Scripts (`scripts/analysis/`)

All support `--plot`, `--from YYYY-MM-DD`, `--to YYYY-MM-DD`, `--no-llm` (disables AI comments), `--lang de|en`.

---

### Cardiology & AFib

| Script | What it shows | Method | Value |
|---|---|---|---|
| `analyse_afib_burden.py` | Frequency, duration, trends; CV classification (AFib suspect vs. ectopy); burden estimate with clinical thresholds (ASSERT >0.4%/month, TRENDS >23%); H10/ECGLogger session analysis (score distribution, algorithm consensus, monthly trend); 13 context correlations (HRV, BP, SpO2, sleep, stress, pressure etc.) | Polar PPI (CV) + Apple Watch ECG + Polar H10 (ECGLogger) + 10 context sources; ESC-2020 documentation requirement | Burden documentation for clinical appointments; literature-backed thresholds |
| `analyse_arrhythmia.py` | CV classification (AFib vs. ectopy/artefact); burst analysis; 60-min pre-episode context (HR, HRV, stress, BB, RR); time-of-day patterns; seasonal trends; pressure + BP triggers; correlations HRV/sleep/SpO2 | Polar PPI + 9 context sources (pressure, BP, Garmin/Oura context) | Trigger hypotheses, time-of-day patterns, pre-episode physiology |
| `analyse_ecg_detail.py` | classification distribution, clusters, AFib intervals, PPI analysis | ECG classification + RR analysis | Detailed single-ECG analysis from Apple Watch |
| `analyse_blood_pressure.py` | BP time series, time-of-day profile, ESC-2023 classification, corticosteroid effect | ESC thresholds + correlation with AFib/HRV | BP trend, medication effect, IHB frequency |
| `analyse_high_hr.py` | Apple Watch high-HR events; POTS context; time-of-day pattern | HealthKit high_hr_event evaluation | Detects resting tachycardia patterns and POTS indicators |
| `analyse_dfa_alpha1.py` | DFA alpha1 time series, load threshold, Sample Entropy, SD1/SD2 | Non-linear HRV on `ppi_dfa` | Autonomic complexity; alpha1 < 0.75 as AFib/ME-CFS marker |
| `analyse_ptt_hrv.py` | PTT × HRV × blood pressure | Correlation PTT (optical-wrist spot measurements) with RMSSD + RR | Pulse wave analysis; indirect BP proxy |
| `analyse_bp_sleep.py` | Nocturnal BP dipping classification | Sleep/wake window classification + ESC 2024 dipping formula (dipper ≥10%, non-dipper 0–10%, reverse-dipper <0%) | Detects abnormal BP dipping patterns overnight |
| `analyse_ecg_session.py` | Pan-Tompkins re-analysis of stored ECG sessions | QRS detection (Pan-Tompkins 1985) on raw `ecg_samples` | Independent re-check of ECG session R-peak detection |
| `analyse_fluid_orthostatic.py` | Fluid/salt intake × orthostatic tolerance | Target thresholds (2,500 ml/day + 3,000 mg sodium, Raj 2013) correlated with orthostatic markers | Whether hydration/sodium intake improves OI symptoms |
| `analyse_vascular_health.py` | Vascular parameter overview: SpO2, resting HR, activity, skin temp, respiration, PWV, weight, Oura recovery | Monthly aggregation/trend per parameter vs. ESC 2018 references (PWV <10 m/s, resting HR 50–90 bpm) | Cross-parameter vascular health trend |

```bash
python scripts/analysis/cardiovascular/analyse_afib_burden.py --plot
python scripts/analysis/cardiovascular/analyse_ecg_detail.py --plot
python scripts/analysis/cardiovascular/analyse_dfa_alpha1.py --plot --from 2025-01-01
```

---

### HRV & Autonomic Nervous System

| Script | What it shows | Method | Value |
|---|---|---|---|
| `analyse_hrv_multisource.py` | RMSSD comparison Polar / Oura / Apple Watch / Kubios on overlapping days | Bland-Altman + trend comparison | Consistency and systematic offsets between devices |
| `analyse_hrv_fatigue.py` | Night HRV × subjective fatigue, lag ±7 days | Spearman correlation + cross-correlation | How well does HRV predict next-day fatigue? |
| `analyse_intraday_stress.py` | Intraday autonomic load (Garmin 5-min stress + Oura recovery) | Time series + time-of-day profile | When is autonomic load highest? Recovery patterns |
| `analyse_orthostatic.py` | All orthostatic tests: ΔHR, POTS criterion, time course | Schellong-test evaluation, ΔHR ≥ 30 bpm | Dysautonomia screening; comparison with baseline |
| `analyse_hrv_verlauf.py` | Monthly RMSSD trend chart with configured event markers | Monthly RMSSD averages (min. 5 measurement days/month) | Doctor-appointment HRV trend PDF |
| `analyse_recovery.py` | Oura minute-level stress/recovery trend × sleep HRV | Daily/hourly aggregation of `oura_daytime_stress`; Pearson correlation with next-night HRV; recovery-quality score | How does daytime load affect nocturnal recovery? |
| `analyse_ans_battery.py` | Bundled HRV correlations: resting HR, respiratory rate, sleep duration/score, readiness, stress score, systolic BP; plus pulse pressure and nocturnal HR-dip vs. HRV | Pearson correlation per metric pair, n<30 flagged exploratory | Single consolidated autonomic/cardiovascular correlation report for cardiology prep |
| `analyse_ans_dysfunction_evidence.py` | Yearly overview, trend, and list of critical days from the `ans_dysfunction_evidence` table | Reads exclusively from `compute_ans_dysfunction_evidence.py`'s output (no new computation) plus `polar_nightly_hrv` for context | Report counterpart to the ANS dysfunction evidence compute script |
| `analyse_sleep_day_hr.py` | Average heart rate during real, device-recorded sleep vs. the following waking hours, across the full recording period | Sleep-window detection (primarily Polar sessions, cross-checked against other sources) + day/night HR comparison | Whether nocturnal HR is meaningfully lower than daytime HR (autonomic recovery signal) |

```bash
python scripts/analysis/cardiovascular/analyse_hrv_multisource.py --plot
python scripts/analysis/cardiovascular/analyse_orthostatic.py --plot
```

---

### Sleep

| Script | What it shows | Method | Value |
|---|---|---|---|
| `analyse_sleep_multisource.py` | Sleep architecture from Polar, Sleep Cycle, Apple Watch, Somneo | Multi-source fusion | Which source shows what; consistent sleep duration picture |
| `analyse_sleep_stages.py` | Deep sleep and REM distribution (Apple Watch); age-norm comparison (50–60 yr) | Hypnogram evaluation + HRV correlation | Sleep architecture vs age norm; Infectious effect |
| `analyse_sleep_polar.py` | Polar sleep architecture + night HRV trend + recovery | Stage plot + HRV across night | Polar-specific sleep analysis |
| `analyse_hypnogram.py` | Single night or time series: sleep stages visually | Stage plot per source | Quick visual inspection of a night |
| `analyse_sleep_apnea.py` | Long-term apnea screening: breathing disturbances + SpO₂ (all sources) | AW breathing disturbances + SpO₂ combination | OSAS screening without a sleep lab |
| `analyse_sleep_respiration.py` | Breathing disturbances × SpO₂ × respiration rate × sleep architecture | Correlation analysis | Relationship between sleep breathing and recovery |
| `analyse_snoring_spo2.py` | Snoring + breathing interruptions (Sleep Cycle) + AHI estimate | AHI = interruptions / sleep duration | Simple OSAS screening from Sleep Cycle data |
| `analyse_sleep_environment.py` | Environmental parameters × sleep quality (temp, humidity, lux) | Correlation home_environment + weather_station | Whether indoor climate affects sleep |
| `analyse_home_environment_sleep.py` | Home Assistant sensors × sleep (Dyson, room climate) | Spearman + trend analysis | Specific to HA data |
| `analyse_nightly_recharge.py` | Polar Nightly Recharge (ANS charge, sleep charge, level 1–5): recovery level, ANS status patterns, sleep-onset habits, trend | Distribution/trend analysis of Nightly Recharge components | Polar-specific recovery-level tracking |
| `analyse_nightmare.py` | Nightmare alarms from the Kyoro SleepGuard watch app: frequency, time-of-night distribution, HR delta | Aggregates nightmare HR/baseline per night; ≥3 consecutive nights = RBD screening flag | Nightmare pattern tracking + RBD screening flag |

```bash
python scripts/analysis/sleep/analyse_hypnogram.py --date 2026-05-31
python scripts/analysis/sleep/analyse_sleep_stages.py --plot
python scripts/analysis/sleep/analyse_sleep_apnea.py --plot --from 2025-01-01
```

---

### Long term infection impact, PEM & Pacing

| Script | What it shows | Method | Value |
|---|---|---|---|
| `analyse_health_timeline.py` | biomarker comparison | Period comparison HRV, RHR, sleep, symptoms | Central document for doctor discussion |
| `analyse_postinfectious_its.py` | HRV / RHR / sleep before vs. after infection | Segmented linear regression (ITS model) | Quantifies the infection related drop statistically |
| `analyse_pacing.py` | Daily activity budget: Sedentary / Light / Moderate / Intense in minutes + MET | Polar activity levels × HRV + PEM | Safe activity limit for PEM prevention |
| `analyse_pem_cascade.py` | Lag correlation: activity day N → HRV drop / symptoms day N+1 to N+3 | Cross-correlation, 24–72h lag | Shows the classic PEM delay pattern |
| `analyse_pem_threshold.py` | At what exertion level does PEM likely occur? | Logistic regression + Youden index + ROC | Personal PEM threshold in kcal / training score |
| `analyse_postinfectious_diagnose.py` | Multi-domain diagnostic score: 6 domains vs. WHO/NICE reference values + individual baseline | Autonomic, PEM, cardiac, sleep, activity, SpO2 + LLM interpretation | Doctor appointment export with baseline comparison |
| `analyse_mecfs.py` | ME/CFS IOM-2015 criteria: PEM, sleep, fatigue, cognition, OI from wearable data | IOM/ICC criteria + Workwell severity grading | Biomarker-based ME/CFS assessment |
| `analyse_mcas_muster.py` | MCAS pattern tracker: coincident wearable signals (not a diagnostic tool) | RHR, HRV-delta, SpO2, temp, symptoms | Episode patterns for doctor discussion |
| `analyse_symptom_progression.py` | Symptom trend by category: 30/90-day smoothing, good/bad day profiles | Moving average + quartile profiles | Shows whether symptoms are improving or worsening |
| `analyse_acute_response.py` | Acute episodes from `acute_events`: duration, peak severity | Episode clustering on consecutive-day NEWS2-style scores (gap-tolerant merging) | Identifies discrete acute illness episodes from daily severity scores |
| `analyse_energy_domains.py` | Multidimensional energy management: physical HR load + subjective sensory/cognitive/social domain scores | Reads `daily_energy_summary` (from `compute_gesamtpensum`) | Pacing across physical AND non-physical energy domains |
| `analyse_pem.py` | PEM evidence score time series, recovery pattern distribution, monthly PEM burden, sport-adjusted rate pre/post event | Aggregation/visualisation of `pem_evidence_scores` (from `compute_pem`), broken down by confidence level | Longitudinal PEM burden tracking |
| `analyse_undocumented_events.py` | Potential undocumented health events from wearable metrics | Z-score anomaly detection (median/MAD) per metric group; dual baseline (rolling 42 days + fixed reference); composite score ≥2 groups, flag at ≥1.8σ | Flags possible unlogged illness/relapse episodes |
| `analyse_changepoint.py` | Sustained level shifts (step changes) in daily marker time series | Binary segmentation with mean-shift cost (Killick et al. 2012) | Detects structural breaks in HRV/stress trends without pre-specifying a date |
| `analyse_postcovid_sleep_wearable.py` | Own wearable sleep data (HRV, RHR, breathing, efficiency, REM latency, bedtime regularity) vs. seven patterns from the RECOVER Long-COVID cohort | Pre/post-window mean and dispersion comparison, restricted to Polar data for device consistency | Literature-grounded benchmark for post-infectious sleep deterioration |

```bash
python scripts/analysis/infectious/analyse_postinfectious_diagnose.py --infection-date YYYY-MM-DD
python scripts/analysis/neurology/analyse_mecfs.py --infection-date YYYY-MM-DD
python scripts/analysis/immunology/analyse_mcas_muster.py --from YYYY-MM-DD
python scripts/analysis/internal_medicine/analyse_health_timeline.py --plot
python scripts/analysis/neurology/analyse_pem_cascade.py --plot
python scripts/analysis/neurology/analyse_pem_threshold.py --plot
```

---

### Vitals & Body

| Script | What it shows | Method | Value |
|---|---|---|---|
| `analyse_body_composition.py` | Weight, body fat, muscle mass, waist over years | Multi-source: FDDB + Apple + Beurer | Long-term body composition trend |
| `analyse_body_temperature.py` | Skin temperature (Polar/Apple/Oura): subfebrile phases, circadian pattern | Time series + correlation with HRV/symptoms | Inflammation indicator |
| `analyse_oura_temperature.py` | Oura temp deviation + Apple + Polar: illness patterns, cycle effect | Time series + cycle phases | Temperature long-term analysis |
| `analyse_spo2.py` | SpO₂ from Polar, Oura, Apple Watch,... — trends, outliers, hypoxia | Multi-source: < 94 % notable, < 90 % critical | Long-term SpO₂ profile |
| `analyse_blood_glucose.py` | Blood glucose (glucometer): time-of-day profiles, in-range rate, trend | Fasting / postprandial markers | Glucose control, insulin sensitivity |
| `analyse_cgm_glucose.py` | CGM: time in range, variability, patterns | CGM metrics (TIR, GMI, CV) | Generic CGM ingestion; metrics computed when data present |
| `analyse_respiration.py` | Nocturnal respiration rate (Garmin + Apple Watch): trends, outliers | Time series, > 18 /min notable | Early indicator for infections and inflammation |
| `analyse_overview.py` | Daily/weekly overview dashboard: RHR, HRV, sleep, SpO2, activity, symptoms combined | 7-day rolling average per biomarker; event lines from `clinical.events` | Single-glance cross-domain status dashboard |

```bash
python scripts/analysis/metabolic/analyse_body_composition.py --plot
python scripts/analysis/sleep/analyse_spo2.py --plot --from 2025-01-01
```

---

### Fitness & Training

| Script | What it shows | Method | Value |
|---|---|---|---|
| `analyse_training_load.py` | Training load: PEM risk by sport, recovery times | Load-HRV correlation | Safe training budget in post infectious context |
| `analyse_workout_performance.py` | Training overview, HR zones, recovery, PEM threshold, pre/post infection | Monthly trends + HRV analysis | Performance development over time |
| `analyse_fitness_vo2max.py` | VO2max trend (Polar Own Index + Apple Watch, ...) | Time series from `measurements` | Aerobic capacity as objective fitness trend |
| `analyse_gait.py` | Gait parameters: Steadiness, Asymmetry, Speed, Step Length (Apple Watch) | Long-term trend, Apple Walking Steadiness ≥ 75 % = OK | Neurological long-term marker |
| `analyse_sedentary.py` | Stand hours, sitting time, movement breaks | Apple Stand Hours + Polar activity | Sedentary behaviour as independent risk factor |
| `analyse_ecg_longterm.py` | Multi-day H10 monitoring: hourly RMSSD, post-workout reactions | HRV time series across day and night | Deep analysis of individual H10 monitoring periods |
| `analyse_ecg_24h.py` | Evaluate a 24h H7 recording | Beat-to-beat HRV over 24h | Evaluation after H7 24h monitoring |
| `analyse_daily_load.py` | HR zone distribution and daily load score | Reads `daily_hr_zones` (from `compute_hr_zones`); empirically calibrated zone boundaries | Overview of daily training/activity load levels |
| `analyse_functional_capacity.py` | 6-minute walk test (6MWT) as objective outcome measure: distance, reference values | ATS 2002 reference (~560 m for women ~40–50y), MCID 30 m | Objective functional-capacity tracking over time |
| `analyse_sport_environment.py` | Training sessions × environmental data (pollen, air quality, UV, temperature) with GPS location | Spearman rank correlation; GPS centroid; ±1-day location matching | Whether environment affects training tolerance/performance |
| `analyse_stryd_dynamics.py` | Per-session power (W/kg) vs. heart-rate response ("cardiac cost"); elevation-HR correlation | Pearson correlation per session, n<30 flagged exploratory | Objectifies the exertion cost of a run beyond pace/speed |

```bash
python scripts/analysis/activity/analyse_training_load.py --plot
python scripts/analysis/activity/analyse_fitness_vo2max.py --plot
```

---

### Environment & Triggers

| Script | What it shows | Method | Value |
|---|---|---|---|
| `analyse_migraine_triggers.py` | Multi-trigger: sleep, HRV, cycle, weather, stress × migraine | Lag correlation ±3 days + Mann-Whitney U + risk score | Which trigger raises migraine risk? |
| `analyse_migraine_pressure.py` | Barometric pressure change × migraine risk | Pressure variability ±2-day window + Mann-Whitney U | Confirms/refutes pressure as personal trigger |
| `analyse_pollen_symptoms.py` | Pollen types × symptom categories, lag 0–2 days | Spearman + Mann-Whitney U | Which pollen causes which symptoms? |
| `analyse_airquality_symptoms.py` | PM2.5, PM10, NO2, O3, AQI × symptoms & migraine | Spearman + lag analysis 0–3 days | Air quality triggers |
| `analyse_allergens.py` | EU-14 allergens from FDDB data × symptoms | Keyword matching + correlation | Food allergen load |
| `analyse_noise.py` | Noise (Apple Watch dBASPL) × migraine, neurological symptoms, HRV | WHO thresholds + correlation | Noise as trigger and HRV stressor |
| `analyse_daylight.py` | Daily sunlight exposure × sleep, HRV, energy, mood | Time series + Spearman | Circadian light effect |
| `analyse_product_exposures.py` | Product exposures (medications, cosmetics, dental care, household) × symptoms | Co-occurrence ratio (days with/without) + Spearman correlation, 0–2 day lag | Substance trigger hypotheses |
| `analyse_pathogen_exposure.py` | Lifetime pathogen exposure risk from travel history, GPS clusters, GPX routes | Geo-matching (outbreak/endemic data) + temporal overlap; severity weights {high:1.0, mid:0.6, low:0.25} | Exposure-based differential diagnosis input |
| `analyse_outbreak_exposure.py` | Travel history × outbreak/endemic disease data | Geo (ISO-country + radius 5°/2°) + temporal overlap (±60/30-day incubation buffer) | Exposure-based differential diagnosis list |
| `analyse_histamine_triggers.py` | Histamine trigger diary patterns: daily loads, top triggers, reaction-time windows | Category-based histamine load scoring (high=3, medium=2, low=0, liberator=2); correlation with symptoms | Histamine intolerance pattern identification |
| `analyse_background_infection_activity.py` | Own symptom diary × five population-level RKI/UBA background series (GrippeWeb, ARE consultation incidence, SurvStat, AMELAG wastewater, ED surveillance) | Correlates weekly symptom load with regional infection-activity series | Distinguishes individual illness from population-wide waves |
| `analyse_environmental_triggers.py` | Environmental substances (cosmetics, household products), incl. INCI ingredient-level | Baseline (pre-exposure) vs. exposure-period event-frequency comparison | Substance- and ingredient-level trigger hypotheses |

```bash
python scripts/analysis/neurology/analyse_migraine_triggers.py --plot
python scripts/analysis/immunology/analyse_pollen_symptoms.py --plot
```

---

### Menstrual Cycle

| Script | What it shows | Method | Value |
|---|---|---|---|
| `analyse_cycle_health.py` | Cycle lengths, HRV by phase (follicular vs. luteal), temperature curve | Phase assignment from WomanLog + Oura | Cycle-HRV patterns; Post infectious cycle effect |
| `analyse_cycle_hrv.py` | Cycle length trends, phase-HRV, energy, PEM risk | Cycle phase × HRV / energy | Safe activity window in cycle |
| `analyse_cycle_sleep.py` | Cycle phase × sleep × body temperature | Phase assignment + sleep metrics | Sleep quality by cycle phase |

```bash
python scripts/analysis/cycle/analyse_cycle_health.py --plot
python scripts/analysis/cycle/analyse_cycle_hrv.py --plot
```

---

### Medications & Clinical

| Script | What it shows | Method | Value |
|---|---|---|---|
| `analyse_medication_effects.py` | for example GLP-1 (ozempic, mounjaro, ...) or other general health related medication effect on weight, HRV, symptoms | Before/after medication start | Medication efficacy tracking |
| `analyse_clinical_findings.py` | All clinical findings over time: categories, severity grades, status development | Timeline from `clinical_findings` | Doctor appointment preparation |
| `analyse_nutrition.py` | Macronutrients, calorie trend, meal timing × HRV/energy | FDDB analysis | Dietary patterns and effects |
| `analyse_clinical_addendum.py` | Clinical addendum to the data synthesis, folding in manually logged clinical observations | Reads latest synthesis report + `clinical.observations` from config | Adds clinician-entered context to the automated synthesis |
| `analyse_synthesis.py` | LLM-based synthesis of all individual analyses | Reads latest markdown reports from `analyses/`; LLM cross-evaluation (optional multi-model panel with individual-opinions appendix) | Single consolidated narrative across all analysis scripts |
| `analyse_treatment_response.py` | Effect of logged treatments/applications on documented events and HRV | Baseline-vs-during/after comparison from `treatment_history.json` | Tracks whether a given treatment measurably changed symptoms or HRV |
| `analyse_reha_klinik_empfehlung.py` | LLM-ranked rehab facility recommendation matched against the current clinical picture | Matches latest synthesis report against parsed DRV/dasrehaportal facility lists | Discussion basis for exercising the SGB IX §8 facility-choice right |

```bash
python scripts/analysis/internal_medicine/analyse_clinical_findings.py --plot
python scripts/analysis/internal_medicine/analyse_medication_effects.py --plot
```

---

### Cognition & Longevity

| Script | What it shows | Method | Value |
|---|---|---|---|
| `analyse_cognitive.py` | Cognitive short tests (reaction time, SDMT, digit span, N-back) | Pearson correlation cognitive scores × HRV/fatigue; pre/post group comparison | Objective cognitive-impairment tracking |
| `analyse_longevity.py` | Integrated longevity profile: biological age (epigenetics), genetic risk markers, lab/wearable data | Descriptive aggregation (no statistical modelling); Phenotypic Age reference (Levine et al. 2018) | Cross-domain longevity overview |

```bash
python scripts/analysis/neurology/analyse_cognitive.py --plot
python scripts/analysis/longevity/analyse_longevity.py --plot
```

---

### Manual Lab, Imaging & Skin

| Script | What it shows | Method | Value |
|---|---|---|---|
| `analyse_lab_verlauf.py` | Longitudinal table of all lab values from `lab_manual`, pivoted by (category, parameter) × date | Reads `lab_manual` from `medicine.db` | Full lab-history overview across years |
| `analyse_saliva_ph.py` | Saliva pH data from home monitoring | Reads `lab_manual` (parameter="Speichel-pH") from `medicine.db` | Home-monitoring pH trend |
| `analyse_urine.py` | Urine dipstick test data from home monitoring | Reads `lab_manual` (Urine-* parameters) from `medicine.db` | Home-monitoring urinalysis trend |
| `analyse_skin.py` | Temporal progression of skin lesions | LLM/VLM-based lesion analysis over time | Longitudinal skin-lesion tracking |
| `analyse_fundus.py` | Fundus photographs: optic disc, vessels, structured findings | Structured VLM prompt (no diagnostic scoring) | Home fundus-photo documentation |

```bash
python scripts/analysis/manual/analyse_lab_verlauf.py
python scripts/analysis/manual/analyse_skin.py --plot
```

---

## Quick start by device / question

**"What does the H10 show today?"**
```bash
python scripts/analysis/cardiovascular/analyse_dfa_alpha1.py --plot --from $(date -d '7 days ago' +%Y-%m-%d)
python scripts/analysis/cardiovascular/analyse_arrhythmia.py --plot --from $(date -d '30 days ago' +%Y-%m-%d)
```

**"How is my AFib situation?"**
```bash
python scripts/query/health_report.py --focus kardio
python scripts/analysis/cardiovascular/analyse_afib_burden.py --plot
python scripts/analysis/cardiovascular/analyse_ecg_detail.py --plot
```

**"How was my sleep?"**
```bash
python scripts/analysis/sleep/analyse_hypnogram.py --date $(date +%Y-%m-%d)
python scripts/analysis/sleep/analyse_sleep_stages.py --plot --from $(date -d '30 days ago' +%Y-%m-%d)
```

**"PEM risk after yesterday?"**
```bash
python scripts/analysis/neurology/analyse_pem_cascade.py --plot
python scripts/analysis/psychology/analyse_pacing.py --plot
```

**"Prepare for doctor's appointment"**
```bash
python scripts/query/health_report.py
python scripts/analysis/internal_medicine/analyse_health_timeline.py --plot
python scripts/analysis/internal_medicine/analyse_clinical_findings.py --plot
```

---

## Flags — Overview

| Flag | Meaning |
|---|---|
| `--plot` | Open / save Matplotlib plots |
| `--from YYYY-MM-DD` | Only data from this date |
| `--to YYYY-MM-DD` | Only data up to this date |
| `--update` | Only compute new days (compute scripts) |
| `--recompute` | Recompute everything (compute scripts) |
| `--no-llm` | Disable AI comments |
| `--lang de\|en` | Output language |
| `--person self\|partner` | Select person |
