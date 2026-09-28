# serve_instance_tools.py — Tools only for the active data instance.

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/utils/serve_instance_tools.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Starts Datasette (a DB inspection web UI) for the currently active data instance (KYORO_ACTIVE_PATIENT_DIR).

## Relevance

Provides utility functions for data processing, essential for system functionality

## Method

Reads KYORO_ACTIVE_PATIENT_DIR from the environment (set by `manage_people.py activate`); `health_config.load()` then automatically resolves the instance's db_path/db_key (see `health_config.py`: KYORO_CONFIG_DIR is computed relative to KYORO_ACTIVE_PATIENT_DIR when set). Decrypts the instance DB (if SQLCipher-encrypted) via `modules.datasette_utils.decrypt_to_temp` into an instance-uniquely-named temp copy and starts Datasette on it.

## Data flow

- **Reads:** `$KYORO_ACTIVE_PATIENT_DIR/.config/kyoro/health_config.json`, `(via`, `health_config.load())`, `the`, `instance's`, `health.db`
- **Writes:** `Temporäre entschlüsselte Kopie der Instanz-health.db`

## Limitations

No access-control layer — anyone who can set the environment variable manually can open any instance (same limitation as manage_people.py). Grafana is not integrated by this project — if you want dashboards beyond Datasette, set up Grafana yourself against a decrypted copy of the instance DB (installation- specific, not part of this repo).

## Usage

```bash
export KYORO_ACTIVE_PATIENT_DIR="$HOME/kyoro-patients/PT-A1B2C3D4"
python3 scripts/utils/serve_instance_tools.py datasette --port 8001
```
