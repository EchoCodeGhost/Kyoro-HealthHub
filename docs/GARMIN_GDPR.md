<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
# Importing the Garmin GDPR export

For most users, the **GDPR data export** is the most convenient way to
import their Garmin data: **one download, no API login, no rate limit** —
and it contains data that the Garmin Connect API does **not** expose.

## 1. Requesting the export

1. [Garmin Account](https://www.garmin.com/account/) → **Data & Privacy** →
   *"Export Your Data"*
2. Garmin emails a download link after a few hours/days.
3. Download and unzip. You get a folder named after a UUID
   (e.g. `dae8d692-f131-469c-99b5-150d7813904a_1`).

> The export contains many domains (Aviation, Marine, Shop, …). Health data
> lives under **`DI_CONNECT/`**.

## 2. Importing

```bash
python3 scripts/importers/import_garmin_gdpr.py --dir /path/to/UUID-folder
```

Individual parts (default is all):
`--ecg` · `--stress` (intraday stress/HR/SpO2/respiration from FIT) · `--uds`
(daily summaries) · `--sleep` · `--fitness` (VO2max) · `--abnormal` (high HR) ·
`--lifestyle` (lifestyle tags from `LifestyleLogging.json`)

Requirement: `pip install fitparse` (in `requirements.txt`).

## 3. What gets imported

| Source in export | → DB | Notes |
|---|---|---|
| `DI-Connect-Health-ECG/*.json` | `ecg_sessions` + `ecg_samples` | ECG waveform (128 Hz), rhythm classification, AFib evidence for AFES |
| `DI-Connect-Uploaded-Files/*.zip` (monitoring FIT) | `measurements`: `stress`, `heart_rate`, `spo2`, `respiration_rate` | **intraday, full history** — the API only serves ~3 months of intraday |
| `DI-Connect-Aggregator/UDSFile_*.json` | `measurements`: steps, resting/min/max HR, intensity minutes, floors, distance, kcal | clean daily summaries |
| `DI-Connect-Wellness/*sleepData.json` | `sessions(type=sleep)` + `session_metrics` | score breakdown, SpO2, respiration, breathingSeverity, RestlessMoments |
| `DI-Connect-Wellness/*fitnessAgeData*` | `measurements`: `vo2max`, `fitness_age` | **VO2max** — the API returns `null` for non-runners |
| `DI-Connect-Wellness/*AbnormalHrEvents.json` | `measurements`: `high_hr_event` | |
| `DI-Connect-Wellness/*LifestyleLogging*.json` | `user_context` | daily lifestyle tags entered in the Garmin Connect app (alcohol, caffeine, training intensity, meal timing, sauna, light therapy, massage, acupuncture, etc.), presence-coded per day+tag name — same target table as the Oura tags from `import_oura_csv.py` |

Source in the DB: `source_app='garmin_gdpr'`; `device_id` is resolved per
measurement by date: `device_for_date()` picks the Garmin device with
`sensor_type=optical_wrist_gps` from `device_registry` whose
`date_from`/`date_to` window covers the measurement date (with several
watches used sequentially, each measurement gets the device that was
correct at that point in time). Fallback when no registry window matches:
`paths.garmin_gdpr_device_id` from the config.
Sleep sessions use the same ID as the API import (`garmin_sleep_<date>_<person>`)
→ `INSERT OR IGNORE` merges instead of duplicating.

## 4. Technical notes

- **Intraday HR** uses FIT `timestamp_16` reconstruction against the last full
  `timestamp` (FIT epoch 1989-12-31). For users **without** Apple or another
  HR source, this is the only dense HR history available.
- **SpO2 + respiration rate** come from **reverse-engineered**, undocumented
  FIT message types (`unknown_269.unknown_0` = SpO2 %, `unknown_297.unknown_0` =
  respiration rate ×100). Imported defensively with a plausibility range.
  **Firmware-dependent** — can change; missing values are not an error.
- **No DFA-α1**: the FIT files contain **no** beat-to-beat RR (wrist). The
  ECG is only ~30 s (~40 beats) — too short for stable DFA-α1. DFA still
  requires the Polar H10 chest strap (see `compute_ppi_dfa.py`).

## 5. GDPR export vs. Connect API

| | GDPR export | Connect API (`import_garmin.py`) |
|---|---|---|
| Setup | 1 download, no login | OAuth login + MFA |
| Rate limit | none | yes (large backfills risky) |
| Intraday depth | **full history** | only ~last 3 months |
| VO2max | **yes** | `null` (for non-runners) |
| ECG | **yes** | no |
| Freshness | as of export | live |

**Recommendation:** GDPR export for the large initial import (depth + ECG +
VO2max), API (`--update`) for ongoing updates.
