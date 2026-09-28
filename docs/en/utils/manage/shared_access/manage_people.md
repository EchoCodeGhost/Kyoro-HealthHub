# manage_people.py — Personenregistratur für gemeinsam genutzte Kyoro-Instanzen

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/utils/manage/shared_access/manage_people.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Manages the mapping of person numbers to isolated Kyoro instance directories (each person has their own health.db + db_key). Built for the private multi-person context (e.g. family, friends) — Kyoro-HealthHub is deliberately scoped to private use, see SHARED_ACCESS_DEPLOYMENT.md. Optional interactive copy of shared devices.

## Relevance

Provides health data functions, essential for medical data processing

## Method

Reads/writes the person mapping in master.db (see create_master_schema.py). On `add`, creates a new instance directory with its own .config/kyoro/ + data/. `activate` only prints the export command — the actual authorization check happens in the broker (section 4.2 of the shared-access plan); this script itself has no login/roles concept.

## Data flow

- **Reads:** `~/.config/kyoro-master/master.db`, `(Personen-Zuordnung)`
- **Writes:** `~/.config/kyoro-master/master.db (Personen-Zuordnung), neue Instanzverzeichnisse`

## Limitations

No access-control layer — anyone with shell access to the machine can manually activate any instance directory. Physical/ OS-level access control (user accounts, file permissions) remains the operator's responsibility; the broker (section 4) only authorizes the web/API path via Kyoro SymptomTrack, not direct shell access.

## Usage

```bash
python3 scripts/utils/manage/shared_access/manage_people.py list
python3 scripts/utils/manage/shared_access/manage_people.py add "12345" "Familie-A"
python3 scripts/utils/manage/shared_access/manage_people.py deactivate PT-A3F9C21B
python3 scripts/utils/manage/shared_access/manage_people.py activate PT-A3F9C21B
```
