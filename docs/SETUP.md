# Setup

> **Deutsche Version:** [SETUP_DE.md](SETUP_DE.md)

## Requirements

- Python 3.11+
- SQLite 3.35+

## Installation

```bash
git clone https://github.com/EchoCodeGhost/Kyoro-HealthHub.git
cd Kyoro-HealthHub
python3 onboard.py   # creates .venv, installs deps, copies config, initialises DB
```

`onboard.py` runs everything in one step. To install manually instead:

```bash
pip install -r requirements.txt
# or pinned versions for reproducible installs:
pip install -r requirements-lock.txt
```

Security audit:

```bash
pip-audit -r requirements-lock.txt
```

## Configuration

`onboard.py` copies `templates/health_config.example.json` to `~/.config/kyoro/health_config.json`
automatically. Edit that file with your personal data:

```bash
# All personal data lives outside the repository
$EDITOR ~/.config/kyoro/health_config.json
python3 scripts/health_config.py --setup   # alternative: interactive setup
```

`templates/health_config.example.json` contains a fully annotated synthetic biography
(Max Mustermann, b. 1967) that shows the depth expected for LLM-assisted analysis.

Key settings:

| Key | Description |
|-----|-------------|
| `user.name` / `user.birthdate` / `user.gender` | Basic demographics |
| `user.height_cm` / `user.weight_kg` | Required for HRV and training zone calculations |
| `user.timezone` | IANA timezone, e.g. `"Europe/Berlin"` |
| `clinical.hrv_baseline_from` | Start of HRV reference period (before illness onset) |
| `clinical.hrv_baseline_to` | End of HRV reference period |
| `clinical.infection_date` | Date of first infection (derived automatically from `events`) |
| `location.lat` / `location.lon` | Home coordinates for weather lookup |

### Medical biography sections

Beyond `clinical.events`, the config supports several sections that provide context
for LLM-assisted analysis and zoonosis risk assessment:

**Allergies** — drug allergies, food intolerances, insect venom. Recommended:
the interactive tool, which stores entries in `~/.config/kyoro/allergies.json`
(not committed to the repo) rather than inline in `health_config.json`:

```bash
python3 scripts/utils/manage/personal/manage_allergies.py add
python3 scripts/utils/manage/personal/manage_allergies.py list
```

Or fill in `allergies[]` in `health_config.json` directly — it is merged with
the external file as a fallback:

```json
"allergies": [
  {"allergen": "Penicillin", "type": "Arzneimittel", "severity": "schwer",
   "reaction": "Urtikaria, Angioödem", "diagnosed": "1977-10-17"}
]
```

**Family history** — first-degree relatives and relevant conditions. Recommended:
the interactive tool, which stores entries in `~/.config/kyoro/family_history.json`
(not committed to the repo):

```bash
python3 scripts/utils/manage/personal/manage_family_history.py add
python3 scripts/utils/manage/personal/manage_family_history.py list --by-condition
```

Or fill in `family_history[]` in `health_config.json` directly — legacy entries
(`relation`/`conditions[]`/`deceased`/`cause_of_death`) are normalized into the
tool's schema (`relative`/`side`/`condition`/`status`/`notes`) automatically:

```json
"family_history": [
  {"relation": "father", "birth_year": 1939, "conditions": ["CHD", "myocardial infarction 1996"],
   "deceased": true, "death_year": 2009, "death_cause": "cardiac"},
  {"relation": "mother", "birth_year": 1942, "conditions": ["Hashimoto thyroiditis"]}
]
```

**Exposure history** — animal contacts, occupation, sexual history (relevant for
zoonosis risk). Recommended: the interactive tool, which stores data in
`~/.config/kyoro/exposure_history.json` (not committed to the repo):

```bash
python3 scripts/utils/manage/personal/manage_exposure_history.py childhood
python3 scripts/utils/manage/personal/manage_exposure_history.py animal add
python3 scripts/utils/manage/personal/manage_exposure_history.py occupation add
python3 scripts/utils/manage/personal/manage_exposure_history.py sexual set
python3 scripts/utils/manage/personal/manage_exposure_history.py sti add
python3 scripts/utils/manage/personal/manage_exposure_history.py show
```

Or fill in `exposure_history{}` in `health_config.json` directly (fallback,
used only if the external file does not exist):

```json
"exposure_history": {
  "childhood_environment": "rural — farm; Q fever endemic area",
  "animal_contacts": [
    {"animal": "cattle", "exposure": "regular", "period": "1970–1985",
     "context": "grandparents' farm; Coxiella exposure during calving"}
  ],
  "occupational_exposures": [
    {"occupation": "field technician", "period": "1990–present",
     "exposure": "international travel, animal contact sites, tropical climates"}
  ],
  "sexual_history": {
    "multiple_partners": true,
    "sti_screening": [
      {"date": "2023-05-20", "panel": ["HIV-Ak/p24-Ag", "HCV-Ak", "Syphilis-TPPA",
       "Gonorrhoea-PCR", "Chlamydia-PCR"], "result": "all negative"}
    ]
  }
}
```

**Travel history** — with climate zone and exposure context:

```json
"travel_history": [
  {"destination": "Morocco", "country_iso": "MA", "year": 1986,
   "climate_zone": "semi-arid", "context": "hiking, animal market contact"}
]
```

See `templates/health_config.example.json` for the complete annotated example.

### Lab results

**PDF reports (OCR pipeline):**

```bash
python3 scripts/importers/import_lab_results.py laborbefund.pdf
# → writes medicine/laborbefunde/YYYY-MM-DD_labor_ocr.csv
# Open the CSV, correct OCR errors, save as YYYY-MM-DD_labor.csv
# import_lab_csv.py then picks it up automatically on the next run
```

**Manual CSV (no PDF):** Use `labor.example.csv` as a template:

```bash
cp labor.example.csv imports/manual/labor.csv
# fill in your values, then:
python3 scripts/importers/import_lab_csv.py
# or it runs automatically with import_all.py
```

CSV format (`datum` column, `wert` accepts numbers and text like "negativ"):
```
datum,parameter,kategorie,wert,einheit,ref_min,ref_max,labor,status,kommentar
2024-03-15,Hämoglobin,Blutbild,14.2,g/dl,13.5,17.5,Labor XY,,
2024-03-15,HIV-Antikörper,Infektionsdiagnostik,negativ,,,,Labor XY,,
```

### Clinical Events (`clinical.events`)

Long COVID, ME/CFS, and MCAS analysis scripts **only run when** at least one entry with `"type": "infection"` is present. That date is then used automatically as `infection_date`.

```json
"clinical": {
  "events": [
    {"name": "COVID infection",    "date": "YYYY-MM-DD", "type": "infection"},
    {"name": "Long COVID diagnosis","date": "YYYY-MM-DD", "type": "diagnosis"},
    {"name": "Medication X start", "date": "YYYY-MM-DD", "type": "medication_start"}
  ]
}
```

Valid types: `infection`, `reinfection`, `diagnosis`, `medication_start`, `medication_stop`,
`relapse`, `hospitalization`, `surgery`, `symptom_onset`, `remission`, `vaccination`, `other`.

Access via `cfg.events` / `cfg.events_of_type(*types)`.
`cfg.infection_date` resolves to the index infection (explicit `clinical.infection_date`, else an `"index": true` event, else the earliest infection after `data_start`, else the earliest infection overall).

### LLM Provider

All scripts that call an LLM use `scripts/utils/llm_provider.py`. Configure the provider in the `"llm"` block:

```json
{
  "llm": {
    "provider": "openvino",
    "openvino_path": "/path/to/model"
  }
}
```

Supported providers: `openvino`, `ovms`, `ollama`, `lmstudio`, `mlx`, `openrouter`, `anthropic`, `mistral`, `perplexity`, `mammouth`, `huggingface`, `nvidia`, `azure`.
Each provider has its own keys (e.g. `openrouter_api_key`, `anthropic_api_key`, `ollama_model`). See the header of `scripts/utils/llm_provider.py` for the full list.

### External API Keys

Optional external APIs are configured under the `"apis"` block:

```json
{
  "apis": {
    "aemet_api_key": "your-aemet-key"
  }
}
```

| Key | Description |
|-----|-------------|
| `apis.aemet_api_key` | AEMET Open Data API key (Spain weather — optional) |

## Database key and security

### Encryption

The database is optionally encrypted with [SQLCipher](https://www.zetetic.net/sqlcipher/).
Without a key configured, a plain SQLite database is used.

To enable SQLCipher, generate a strong key and store it securely (see below):

```bash
# Generate a key (example — use your own)
python3 -c "import secrets; print(secrets.token_hex(32))"
```

### Key management

`open_db()` looks for the key in this priority order:

| Priority | Source | How to set up |
|---|---|---|
| 1 | Environment variable `KYORO_DB_KEY` | `export KYORO_DB_KEY="..."` in `~/.profile` |
| 2 | System keyring (`keyring` package, optional) | `pip install keyring` + set keyring entry |
| 3 | `~/.config/kyoro/db.key` (recommended) | see below |
| 4 | `health_config.json["db_key"]` | fallback, prints migration hint |

**Recommended: key file `~/.config/kyoro/db.key`**

```bash
echo "YOUR_KEY" > ~/.config/kyoro/db.key
chmod 600 ~/.config/kyoro/db.key
```

**Migrate from `health_config.json` (if the key is still stored there):**

```bash
python3 scripts/health_config.py --migrate-key
# moves the key automatically and sets db_key=null in the config
```

**Test the connection:**

```bash
python3 scripts/health_config.py --test-db
# → "DB-Verbindung OK (N Tabellen/Views)"
```

**System keyring (optional, strongest protection):**

```bash
pip install keyring secretstorage
python3 -c "import keyring; keyring.set_password('kyoro-healthhub', 'db_key', 'YOUR_KEY')"
```

### File permissions

```bash
chmod 600 ~/.config/kyoro/health_config.json   # API tokens etc.
chmod 600 ~/.config/kyoro/db.key                # DB key
chmod 600 data/health.db                 # DB file itself
```

### Threat model

| Scenario | Protected by encryption |
|---|---|
| Device stolen / backup without key | ✅ Fully |
| Other local user without sudo | ✅ With correct file permissions |
| User with `sudo` rights | ❌ Key is readable — system trust required |
| Docker group (= effectively root) | ❌ Filesystem can be mounted |

→ Encryption protects against theft — it does **not** protect against data
loss. Back up `data/`, your config, and the key itself (wherever it
actually lives): [docs/BACKUP.md](docs/BACKUP.md)

## Import data

**Unsorted device exports:** drop files straight into `imports/_inbox/` — no
need to sort them into the right subdirectory yourself. `process_inbox.py`
recognises file types by name pattern (ZIP archives from Apple Health, Polar
GDPR, Garmin GDPR, Oura CSV; single files like Hilo, RENPHO, Wellue O2Ring, Kubios,
HRV4Training, migraine app, Shotsy, PDF lab results, GPX, ...), moves each to
the matching `imports/*/` directory, then moves it to `_inbox/processed/`
once handled.

```bash
python3 scripts/process_inbox.py --dry-run           # preview what would be recognised
python3 scripts/process_inbox.py --import            # sort + import_all.py --update in one step
```

```bash
python3 scripts/import_all.py                        # all configured sources
python3 scripts/import_all.py --update               # new data only
python3 scripts/import_all.py --person partner       # one specific person only
```

Some importers require an explicit file or directory argument and must be called manually:

```bash
# Lab results — PDF via OCR (produces review CSV)
python3 scripts/importers/import_lab_results.py laborbefund.pdf
# Lab results — reviewed/manual CSV → DB (also runs via import_all.py)
python3 scripts/importers/import_lab_csv.py

# HRV4Training
python3 scripts/importers/import_hrv4training.py --file export.csv
python3 scripts/importers/import_hrv4training.py --dir ~/Downloads/

# ECGLogger / Polar H10 beat-to-beat
python3 scripts/importers/import_hrv_logger.py --dir imports/hrv_logger/
python3 scripts/importers/import_ecg_logger.py --dir imports/ecglogger/

# Kubios HRV
python3 scripts/importers/import_kubios_orthostatic.py --file export.txt
python3 scripts/importers/import_kubios_screenshot.py --file screenshot.png

# EcoWitt local weather station (CSV export from app or ecowitt.net)
python3 scripts/importers/import_ecowitt_csv.py /path/to/ecowitt_export.csv

# Garmin GDPR data export
python3 scripts/importers/import_garmin_gdpr.py --dir /path/to/DI_CONNECT/

# AEMET (Spanish weather service — requires api key in config)
python3 scripts/importers/import_aemet.py --lat 40.4 --lon -3.7
```

## Compute metrics

Computes derived tables from raw data (stress, PEM, arrhythmia, advanced HRV,
clinical criteria, data quality). Must be run after every import — analysis scripts
and `health_query.py` depend on these tables.

```bash
python3 scripts/compute_all.py
```

→ Dependency order and target tables: [ARCHITECTURE.md](ARCHITECTURE.md#derived-tables)

## Query

```bash
python3 scripts/query/health_query.py "How has my HRV changed?"
python3 scripts/query/health_query.py "Wie hat sich meine HRV entwickelt?" --lang de
```

## Export

```bash
python3 scripts/export_health.py --profile cardiology --last 365d --format csv
python3 scripts/export_health.py --profile general_practitioner --from 2026-01-01 --person self --format csv
python3 scripts/export_health.py --profile research --person all --format json
```

Options: `--person self|partner|all` (default: `self`), `--lang de|en` (default: `de`), `--from YYYY-MM-DD`, `--to YYYY-MM-DD`, `--last Nd`

Profiles: `cardiology`, `sleep`, `neurology`, `mental_health`, `metabolic` (aliases: `diabetology`, `endocrinology`), `gynecology`, `long_covid`, `rheumatology`, `oncology`, `ent`, `pulmonology`, `sports_medicine`, `nutrition`, `functional_medicine`, `immunology`, `infectiology`, `general_practitioner`, `clinical_full`, `research`

## Specialist analyses (`scripts/analysis/`)

95 standalone analysis scripts for statistical evaluations, correlations, and clinical
reports. Each script writes a Markdown report to `analyses/<topic>/`.

```bash
# Examples
python3 scripts/analysis/infectious/analyse_postinfectious_its.py --cutoff YYYY-MM-DD --plot
python3 scripts/analysis/neurology/analyse_pem_threshold.py --plot
python3 scripts/analysis/cardiovascular/analyse_hrv_fatigue.py --plot
python3 scripts/analysis/cardiovascular/analyse_dfa_alpha1.py --plot
python3 scripts/analysis/sleep/analyse_sleep_apnea.py --plot

# Sleep hypnogram (single night or trend)
python3 scripts/analysis/sleep/analyse_hypnogram.py --date YYYY-MM-DD
python3 scripts/analysis/sleep/analyse_hypnogram.py --from YYYY-MM-DD --to YYYY-MM-DD
python3 scripts/analysis/sleep/analyse_hypnogram.py --date YYYY-MM-DD --source polar

# Sleep multi-source incl. environment
python3 scripts/analysis/sleep/analyse_sleep_multisource.py --plot --no-llm

# Options (all scripts)
--plot          show Matplotlib charts
--no-llm        statistics output without LLM evaluation
--from YYYY-MM-DD / --to YYYY-MM-DD   restrict date range
--lang de|en    output language (default: de)
```

Full list of scripts with required tables: [ARCHITECTURE.md](ARCHITECTURE.md)
