# Supported Devices & Data Sources

> **Deutsche Version:** [DEVICES_DE.md](DEVICES_DE.md)

All devices are registered in the `devices` table with a unique `device_id`. See [CONTRIBUTING.md](CONTRIBUTING.md) for how to add new devices.

---

## Wearables

| Device | Example `device_id` | `sensor_type` | Importer |
|---|---|---|---|
| Polar (wrist — Ignite, Vantage, Loop, …) | `polar_vantage` | `optical_wrist_gps` | `import_polar.py` |
| Polar (chest strap — H7, H10) | `polar_h10` | `chest_strap` | `import_polar.py` |
| Apple Watch | `apple_watch` | `optical_wrist_gps` | `import_apple.py` |
| Oura Ring | `oura` | `ring` | `import_oura.py` |
| Garmin (wrist) | `garmin_fenix` | `optical_wrist_gps` | `import_garmin.py` |
| Garmin (handheld GPS) | `garmin_gpsmap` | `handheld_gps` | `import_garmin.py` |

Choose your own `device_id` values — they are arbitrary slugs used as foreign keys throughout the database. Add one row per physical device in `create_schema.py`. See [CONTRIBUTING.md](CONTRIBUTING.md).

**Polar** — export via account.polar.com → Data Export (GDPR). Covers all models with a GDPR export: nightly HRV, 24/7 HR, PPI intervals, sleep sessions, hypnogram, PPT.

> **Polar wrist serial numbers:** Set the `serial` field for each Polar wrist device in `device_registry` (see `templates/health_config.example.json`). `import_polar.py` reads this list automatically to identify which watch sessions contain H7/H10 chest-strap RR intervals — no manual code editing needed.

**Apple Health** — export from the iPhone Health app (Profile → Export All Health Data → `export.zip`). Covers: HR, HRV SDNN, SpO₂, ECG, workouts, symptoms.

**Oura Ring** — connects via API token (cloud.ouraring.com → Personal Access Token). Covers: sleep, HRV, HR, skin temperature, cardiovascular age, stress, readiness, resilience, tags.

**Garmin** — connects via `python-garminconnect` or Garmin Connect manual export. Covers: workouts, HR, sleep.

---

## Medical Devices

| Device | Example `device_id` | `sensor_type` | Importer |
|---|---|---|---|
| Blood pressure monitor (e.g. Omron) | `bp_monitor` | `bp_monitor` | `import_omron.py` |
| Withings BPM Core (BP, ECG, valvular/interval findings) | `withings_bpm` | `bp_monitor` | `import_withings.py` |
| Scale / body composition (e.g. Beurer) | `scale` | `scale` | `import_beurer.py` |
| Withings scale (weight, height, body composition) | `withings_scale` | `scale` | `import_withings.py` |
| RENPHO smart tape (body circumferences) | `renpho_tape` | `tape_measure` | `import_renpho_tape.py` |
| Glucose meter (e.g. Beurer GL-series) | `glucometer` | `glucometer` | `import_beurer.py` |
| Thermometer (e.g. Beurer FT-series) | `thermometer` | `thermometer` | `import_beurer.py` |
| CGM (e.g. Freestyle Libre 3) | `cgm` | `cgm` | `import_cgm.py` |
| Wellue O2Ring S (continuous SpO2/pulse, second-resolution) | `wellue_o2ring_s` | `pulse_oximeter` | `import_wellue_o2ring.py` |

Shared devices (`person = NULL`) — person is determined at measurement time via `persons.device_user_id`.

**Omron** — export via Omron Connect App → Share Data → CSV.

**Beurer** — export via Beurer Health Manager Pro → CSV Export.

**Withings** — export via Withings ZIP export (Health Mate → account data export); the importer reads the needed CSV members directly from the ZIP. Covers blood pressure, weight/height, manually logged SpO2, and BPM Core ECG waveforms.

**RENPHO** — export via the RENPHO app; CSV dropped into `imports/_inbox/` (`RENPHO*.csv`).

**Wellue O2Ring** — export via the ViHealth app CSV export.

---

## Smartphones

Smartphones provide GPS data for timezone resolution via Home Assistant.

| Device | Example `device_id` | `sensor_type` |
|---|---|---|
| iPhone / Android | `iphone_self` | `smartphone` |

---

## Smart Home & Environment

| Device | Example `device_id` | `sensor_type` | Importer |
|---|---|---|---|
| Home Assistant | `homeassistant` | `hub` | `import_homeassistant.py` |
| Local weather station (e.g. EcoWitt) | `weather_station` | `weather_station` | `import_ecowitt_csv.py` |

**Home Assistant** provides: indoor environment sensors, presence detection, device GPS (Companion App), home timezone.

### Environment sensor via Home Assistant (example)

Stored in `home_environment` (daily aggregates) and `home_environment_ts` (raw ~2-min timeseries).

| HA Entity | `sensor_type` | Unit |
|---|---|---|
| `sensor.your_device_temperature` | `temperature` | °C |
| `sensor.your_device_humidity` | `humidity` | % |
| `sensor.your_device_sound_pressure` | `noise` | dB |
| `sensor.your_device_illuminance` | `light` | lx |

Use `import_homeassistant.py --discover` to list available sensors in your HA instance.

---

## HRV Analysis Tools

| Tool | Importer | Data |
|---|---|---|
| KubiosHRV Mobile | `import_kubios_screenshot.py` | PNS/SNS index, stress index, RMSSD, SDNN |
| KubiosHRV (orthostatic) | `import_kubios_orthostatic.py` | Orthostatic test metrics |
| HRV4Training | `import_hrv4training.py` | Morning HRV, readiness, context variables |
| ECG Logger | `import_ecg_logger.py` | ECG trace 130 Hz, RR intervals, arrhythmia detection |
| HRV Logger | `import_hrv_logger.py` | Beat-to-beat RR interval sessions (chest strap) → `ppi_raw` |

---

## Apps & Protocol Tools

| App | Importer | Data |
|---|---|---|
| Sleep Cycle | `import_sleep_cycle.py` | Sleep times, quality, stage aggregates |
| WomanLog Pro | `import_womanlog.py` | Cycle phases, symptoms, ovulation |
| Flo | `import_flo.py` *(not yet implemented)* | Cycle, symptoms |
| FDDB | `import_fddb.py` | Nutrition diary (kcal, macros), weight |
| Migraine app | `import_migraine.py` | Episodes, intensity, aura, HIT-6, MIDAS, PGIC |
| Symptom diary | `import_symptom_diary.py` | Daily values (energy, pain, exhaustion, …) |
| Shotsy | `import_shotsy.py` | Injection log (drug, dose, route, site, side effects — e.g. GLP-1) |
| Headspace | `import_headspace.py` *(not yet implemented)* | Meditation sessions |
| Freeletics / Gymondo | `import_freeletics.py` / `import_gymondo.py` *(not yet implemented)* | Indoor training sessions |
| Strava / Komoot | `import_strava.py` / `import_komoot.py` *(not yet implemented)* | Outdoor training with GPS |

---

## Lab Results & Medical Documents

| Source | Script | Data |
|---|---|---|
| Lab report PDF | `import_lab_results.py` | OCR → review CSV → LLM analysis |
| Scanned documents (VLM) | `medical/tables_llm.py` | Table extraction via OpenVINO VLM (Qwen2.5-VL) |
| Scanned documents (OCR) | `medical/extract_tables.py` | Table extraction via PPStructureV3 (paddleocr 3.x), output → `exports/tables/`, input from `medicine/` |
| Oura Lab integration | `import_oura.py` | Blood panels → `lab_results` |

---

## Export Instructions

| Source | How to export |
|---|---|
| **Polar** | account.polar.com → Data Export (GDPR) |
| **Apple Health** | Health app → Profile → Export All Health Data → `export.zip` |
| **Oura** | cloud.ouraring.com → Personal Access Token (API) |
| **Garmin** | `python-garminconnect` library, or Garmin Connect manual export |
| **Beurer** | Beurer Health Manager Pro → CSV Export |
| **Omron** | Omron Connect app → Share Data → CSV |
| **Withings** | Health Mate → account data export → ZIP |
| **RENPHO** | RENPHO app → export → CSV into `imports/_inbox/` |
| **Wellue O2Ring** | ViHealth app → export → CSV |
| **HRV4Training** | Profile → Export → "Export CSV" |
| **ECG Logger** | Tap session → Share → "Export ECG (CSV)" |
| **HRV Logger** | Session → Share/Export → CSV or Kubios-compatible file |
| **Sleep Cycle** | Settings → Export Data → CSV |
| **WomanLog** | Settings → Export Data → CSV |
| **FDDB** | My FDDB → Export diary → CSV |
| **Migraine app** | Settings → Create backup → `.mbu` file |
| **Shotsy** | Settings → Export data → JSON or CSV |
| **Lab reports** | PDF from lab/doctor, no special export needed |
| **EcoWitt** | EcoWitt API or local station export |
| **Home Assistant** | HA REST API or statistics export |
