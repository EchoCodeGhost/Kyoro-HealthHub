# Database Architecture

> **German version:** [ARCHITECTURE_DE.md](ARCHITECTURE_DE.md)

Kyoro-HealthHub uses two local SQLite databases. `health.db` holds wearable/sensor time series and raw genetics data. `medicine.db` holds clinical values a doctor measures or orders (lab results, medications, assessments). Both follow the same design principles below, which make them extensible without schema migrations when new devices or metrics arrive.

---

## Design Principles

1. **EAV for time series** — `measurements` and `session_metrics` use Entity-Attribute-Value: `(ts, metric, value)`. New sensors add rows, not columns.
2. **Person-first** — every health data table has a `person TEXT NOT NULL DEFAULT 'self'` column. `persons.device_user_id` maps smart-scale user slots (`u1`, `u2`) automatically. The EAV schema itself scales to any number of `person_id` values, and stronger access control via isolated per-person instances and a permission broker is built for private multi-person use (see [SHARED_ACCESS_DEPLOYMENT.md](SHARED_ACCESS_DEPLOYMENT.md)) — simple individual and family use is unaffected. This project is scoped to private use, not institutional (clinic/research) deployment.
3. **UTC storage, local date** — `ts` is always UTC ISO 8601. `date` is the local calendar day, resolved via a 6-level timezone fallback: GPS coordinates → Apple Health metadata → embedded offset → location history → device timezone → person's home timezone (`persons.timezone`).
4. **Direct source over aggregator** — manufacturer exports (Polar GDPR, Oura API, Garmin Connect) are imported first. Aggregators (Apple Health, Google Fit) fill gaps. `source_priority` resolves conflicts at query time.
5. **Sessions unify sleep and training** — five sleep sources and multiple training sources land in a single `sessions` table with EAV metrics in `session_metrics`. No schema change needed when new devices add new metrics.
6. **Modular plugin architecture** — each importer is one file in `scripts/importers/`. Export profiles are JSON files in `scripts/exporters/profiles/`. Adding a new data source requires no changes to core code. See [CONTRIBUTING.md](CONTRIBUTING.md).

---

## Configuration Layer (`health_config.py`)

All scripts obtain paths, user data, and settings exclusively through `scripts/health_config.py` — no value is hardcoded in the code.

### Structure

`health_config.py` loads `~/.config/kyoro/health_config.json` and merges the user's settings over a `DEFAULTS` dict. Missing keys automatically fall back to the default.

```python
from health_config import Config
from modules.db import open_db, open_medicine_db

cfg = Config()
conn = open_db()             # health.db — plain sqlite3 or SQLCipher, depending on db_key
conn_med = open_medicine_db()  # medicine.db — clinical values
```

### `Config` class — typed properties

| Property | Type | Description |
|---|---|---|
| `cfg.db_path` | `Path` | Path to `health.db` |
| `cfg.polar_dir` | `Path` | Polar export directory |
| `cfg.garmin_dir` | `Path` | Garmin export directory |
| `cfg.analyses_dir` | `Path` | Output directory for plots and reports |
| `cfg.name` / `cfg.age` / `cfg.gender` | | User master data |
| `cfg.llm_provider` | `str` | Active LLM provider (`"openrouter"`, `"ollama"`, …) |
| `cfg.infection_date` | `str \| None` | Index infection (explicit `clinical.infection_date`, else an `"index": true` event, else the earliest infection after `data_start`, else the earliest overall) |
| `cfg.events` / `cfg.events_of_type(*types)` | `list[dict]` | Full, sorted event list, or filtered by type |
| `cfg.max_hr` | `int \| None` | Maximum HR for zone calculations |
| `cfg.arrhythmia_cv_threshold` | `float` | Threshold for arrhythmia detection |

### `open_db()` — transparent encryption

```python
conn = open_db()   # every script, no difference whether encrypted or not
```

If `db_key` is set in the config, `open_db()` opens the database via SQLCipher (`sqlcipher3`). Without `db_key`, plain `sqlite3` is used. The calling scripts don't need to know which.

### Clinical events (`clinical.events`)

Instead of individual date fields, an ordered list is maintained in the JSON config:

```json
"clinical": {
  "events": [
    {"name": "Event A",       "date": "YYYY-MM-DD", "type": "infection"},
    {"name": "Event B",       "date": "YYYY-MM-DD", "type": "diagnosis"},
    {"name": "Medication X",  "date": "YYYY-MM-DD", "type": "medication_start"}
  ]
}
```

`cfg.infection_date` resolves to (in this order): an explicit `clinical.infection_date`, else an event with `"index": true`, else the earliest infection after `clinical.data_start`, else the earliest infection overall. There are no individual properties for other event types — access them via `cfg.events` or `cfg.events_of_type(*types)`.

### CLI

```bash
python3 scripts/health_config.py --setup        # Interactive setup wizard
python3 scripts/health_config.py --show         # Print current config (tokens masked)
python3 scripts/health_config.py --migrate-key  # Migrate DB key storage location
python3 scripts/health_config.py --test-db      # Test DB connection
```

---

## Schema Overview

### People and Devices

| Table | Purpose |
|---|---|
| `persons` | Person registry: `person_id`, `display_name` (optional), `device_user_id` (scale slot), `timezone` |
| `devices` | Device registry: `device_id`, brand, model, serial, `sensor_type`, `person`, `date_from/to` |
| `device_firmware_history` | Firmware version per device over time — relevant for algorithm-change tracking |

`sensor_type` values: `optical_wrist_gps`, `optical_wrist`, `chest_strap`, `ring`, `handheld_gps`, `scale`, `bp_monitor`, `glucometer`, `thermometer`, `smartphone`, `cgm`, `hub`, `weather_station`

### Time Series

| Table | Purpose | Key columns |
|---|---|---|
| `measurements` | All numeric/categorical device metrics (EAV) | `ts`, `metric`, `value`, `value_text`, `unit`, `device_id`, `person` |
| `ppi_raw` | Beat-to-beat PPI intervals — always queried as ordered sequences | `datetime`, `pulse_ms`, `device`, `person` |
| `cgm_readings` | Continuous glucose (Freestyle Libre 3, ~96/day) | `ts`, `glucose_mmol`, `trend`, `device_id`, `person` |

`measurements` metrics include: `heart_rate`, `hrv_rmssd`, `hrv_sdnn`, `spo2`, `respiration`, `skin_temperature`, `body_temperature`, `temp_deviation`, `stress`, `readiness`, `active_energy`, `steps`, `afib_burden`, `pulse_wave_velocity`, `vascular_age`, `resilience`, `resilience_level` (via `value_text`), and more.

### Sessions

| Table | Purpose |
|---|---|
| `sessions` | One row per session: `type`, `ts_start`, `ts_end`, `date`, `device_id`, `person`, `sport` |
| `session_metrics` | All session measurements as EAV: `session_id`, `metric`, `value`, `value_text`, `unit` |
| `session_tracks` | GPS tracks (optional): `session_id`, `ts`, `lat`, `lon`, `elevation_m`, `speed_ms` |

Session types: `sleep` · `training` · `fitness_test` · `orthostatic` · `migraine` · `meditation` · `treatment`

GPS tracks are optional — indoor sessions (Freeletics, Gymondo, Headspace, TENS/EMS) have no tracks.

### Clinical and Health Data (`health.db`)

| Table | Purpose |
|---|---|
| `ecg_sessions` | ECG recording metadata (classification, symptoms, device) |
| `ecg_samples` | Raw ECG samples at 512 Hz |
| `blood_pressure` | Manual and Omron measurements |
| `blood_glucose` | Manual and glucometer measurements |
| `body_composition` | Body-composition scale measurements (up to 22 fields) |
| `symptoms` | All symptom annotations from all sources |
| `reproductive_health` | Cycle, fertility, contraception data (WomanLog, Oura, Flo) |
| `nutrition_daily` | Daily nutrition aggregates (FDDB) |
| `nutrition_entries` | Individual meal entries |

### Clinical Values a Doctor Measures or Orders (`medicine.db`)

| Table | Purpose |
|---|---|
| `medications` | All medications: GLP-1 (Shotsy), Oura medication tracking |
| `lab_results` | Blood panels and other lab tests (Oura Lab integration) |
| `lab_manual` | Manually entered lab/saliva/urine panels (`import_lab_csv.py`, `import_saliva_ph.py`, `import_urine_strip.py`) |
| `assessments` | Scored questionnaires: PHQ-9, GAD-7, HIT-6, MIDAS, ASRS-5, oura_survey |

Importers/analysis scripts open this database with `open_medicine_db()` from `scripts/modules/db.py`, a separate connection from `open_db()` (`health.db`).

A third database, `medicine_imaging.db`, holds medical image data (fundus, X-ray, MRI, CT) — opened via `open_medicine_imaging_db()`, path from `cfg.medicine_imaging_db_path`.

### Context

| Table | Purpose |
|---|---|
| `home_environment` + `home_environment_ts` | Indoor environment sensors (Home Assistant) |
| `home_presence` | Presence detection (Home Assistant) |
| `weather_station` | Local weather (EcoWitt, priority over HA) |
| `weather_remote` | Remote weather data |
| `pollen_dwd` | DWD pollen index (0–6 scale) — Hazel, Alder, Birch, Grass, Rye, Mugwort, Ragweed; daily |
| `v_pollen` | Combined view: Open-Meteo pollen (grains/m³, historical) + DWD pollen index (current) |
| `location_history` | Raw GPS history points |
| `location_stays` | Stay periods with timezone (auto-populated via `timezonefinder`) |
| `oura_sleep_model` | Granular Oura sleep data (JSON columns, linked to sessions via date) |
| `polar_sleep_hypnogram` | Polar sleep stage sequence (raw stage transitions, variable interval) |
| `sleep_hypnogram` | **Unified** sleep hypnogram across all sources — `(ts, source, person)` PK, stages: WAKE/LIGHT/DEEP/REM |
| `kubios_hrv_resting` | Kubios HRV resting measurement (rich schema) |

### Operations

| Table | Purpose |
|---|---|
| `schema_version` | Schema version history for migration management |
| `import_log` | Audit trail of every import run (source, rows, errors, person) |
| `source_priority` | Which source wins per metric+device when duplicates exist |
| `data_quality_flags` | Quality issues flagged per measurement |

### Derived Tables

Computed by `scripts/compute_*.py` — rebuilt after every import:

Listed in `compute_all.py`'s dependency order:

| Table | Script |
|---|---|
| `ecg_rpeaks` + `ppi_raw` | `compute_ecg_rpeaks.py` — R-peak detection, device-agnostic RR intervals |
| `arrhythmie_episoden` + `ppi_windows` | `compute_arrhythmia.py` — Tateno & Glass arrhythmia detection |
| `ppi_dfa` | `compute_ppi_dfa.py` — DFA alpha1 on H10/H7 beat-to-beat RR |
| `ppi_hrv_advanced` | `compute_hrv_advanced.py` — extended HRV metrics (Poincaré, SampEn, LF/HF, DFA) |
| `daily_stress` | `compute_stress.py` |
| `sleep_hypnogram` | `compute_sleep_hypnogram.py` — unified staging from Polar + Oura + Apple Watch |
| `pem_correlation` | `compute_postinfectious.py` — post-exertional malaise pattern |
| `measurements` (`heart_rate` from BP-device pulse) | `compute_bp_pulse_bridge.py` |
| `health_canonical` | `compute_canonical.py` — best value per metric per day |
| `af_evidence_scores` | `compute_af_evidence.py` — daily AF Evidence Score 0–100 |
| `pem_evidence_scores` | `compute_pem.py` |
| `measurements` (`sleep_spo2_min`) | `compute_sleep_spo2.py` |
| `daily_hr_zones` | `compute_hr_zones.py` — samples per HR zone, daily budget |
| `activity_log` | `compute_activity_log_from_symptoms.py` |
| `daily_energy_summary` | `compute_gesamtpensum.py` — physical/sensory/cognitive load |
| `measurements` (`hrv_anomaly_*`) | `compute_hrv_anomaly.py` |
| `symptoms_canonical` | `compute_symptoms.py` |
| `clinical_findings` | `compute_clinical.py` — HR recovery, POTS criterion, ANS status |
| `personal_baseline` | `compute_personal_baseline.py` |
| `daily_context` | `compute_daily_context.py` |
| `acute_events` | `compute_acute_events.py` |
| `ans_dysfunction_evidence` | `compute_ans_dysfunction_evidence.py` |
| `data_quality_flags` | `compute_quality.py` — plausibility checks, runs last |

All derived tables include a `person` column.

---

## Compatibility Views

After migration, views reconstruct old table names for existing scripts:

```sql
-- Session-based views (EAV pivot)
sleep_sessions       -- all sleep sessions with common metrics as columns
training_sessions    -- all training sessions
polar_sleep_detail   -- sleep_sessions WHERE device_id LIKE 'polar%'
garmin_sleep         -- sleep_sessions WHERE device_id LIKE 'garmin%'
oura_sleep           -- sleep_sessions WHERE device_id LIKE 'oura%'
polar_trainings      -- training_sessions WHERE device_id LIKE 'polar%'

-- Renamed tables
symptomtagebuch      -- → symptoms
omron_blood_pressure -- → blood_pressure
migraene_anfaelle    -- → sessions(type='migraine') pivot
migraine_live        -- → sessions(type='migraine') WHERE ts_end IS NULL
```

Scripts reading `polar_heart_rate`, `apple_records`, `polar_temperature` directly are updated to query `measurements WHERE metric=... AND device_id=...` — no compatibility views for these (EAV principle).

---

## Export Profiles

`scripts/export_health.py` exports thematic data packages as CSV or JSON:

```bash
python export_health.py --profile cardiology --from 2026-01-01 --format csv
python export_health.py --profile general_practitioner --last 365d --person self --format csv
python export_health.py --profile research --person all --format json
```

`--format fhir` additionally builds a FHIR R4 Bundle for interoperability with
other clinical systems — see [FHIR_EXPORT.md](FHIR_EXPORT.md).

| Profile | Contents | Use case |
|---|---|---|
| `cardiology` | heart_rate, hrv, spo2, afib_burden, ecg, blood_pressure | Cardiologist |
| `sleep` | sleep_sessions (all sources), hypnogram, nocturnal spo2/hrv | Sleep specialist |
| `neurology` | migraine sessions, symptoms, HIT-6, MIDAS | Neurologist |
| `mental_health` | PHQ-9, GAD-7, stress, sleep, mood | Psychiatry / Psychology |
| `metabolic` (aliases: `diabetology`, `endocrinology`) | blood_glucose, cgm_readings, medications, body_composition | Metabolic / diabetology / endocrinology |
| `gynecology` | reproductive_health, temp_deviation, medications | Gynaecologist |
| `long_covid` | pem_correlation, hrv, spo2, symptoms (fatigue), sleep, clinical_findings | Long COVID clinic |
| `rheumatology` | symptoms (joint/pain/fatigue), inflammation labs, activity, sleep | Rheumatologist |
| `oncology` | lab_results, symptoms, weight, medications, heart_rate | Oncologist |
| `ent` | audio exposure, sore throat, dizziness, snoring | ENT specialist |
| `pulmonology` | spo2 (24/7 + sleep), respiration rate, cough/dyspnoea | Pulmonologist |
| `sports_medicine` | training_sessions, fitness_test, clinical_findings, hrv | Sports medicine |
| `nutrition` | nutrition_daily, nutrition_entries, blood_glucose, body_composition | Dietitian |
| `functional_medicine` | micronutrients, hormones, thyroid, metabolic markers, cgm, sleep, stress, symptoms, nutrition | Functional medicine |
| `immunology` | autoimmune labs (ANA, Sjögren, complement, immunoglobulins), MCAS markers, autonomic dysregulation, symptoms | Immunologist |
| `infectiology` | post-infectious course, PEM pattern, inflammation/serology labs, symptoms, autonomic function | Infectious disease specialist |
| `general_practitioner` | Daily aggregates across all domains — no raw time series | GP |
| `clinical_full` | All clinical tables including time series | Specialist / archive |
| `research` | Everything including ppi_raw, session_tracks, firmware history | Research / own analysis |

`--person self|partner|all` filters all tables by person. `--lang de|en` controls output language (default: `de`).

Profile definitions are JSON files in `scripts/exporters/profiles/` — add new profiles without touching Python code. See [CONTRIBUTING.md](CONTRIBUTING.md).
