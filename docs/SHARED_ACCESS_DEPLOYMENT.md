# Shared Access - Deployment and Management

> **German version:** [SHARED_ACCESS_DEPLOYMENT_DE.md](SHARED_ACCESS_DEPLOYMENT_DE.md)

**Scope note:** Kyoro-HealthHub is deliberately focused on **private use** — individuals, families, and friends managing their own health data. This is a regulatory choice, not just a description: professional/institutional deployment (a medical practice treating patients, a formal research study) raises entirely different obligations (e.g. under the EU AI Act and medical-device regulation) that this project does not pursue or claim to satisfy. The isolated-instance + permission-broker mechanism described below exists because **strong access control is a private-use feature too** — e.g. one family member wanting extra privacy for sensitive data, or a trusted person helping manage a relative's data with explicit, revocable permission — not because the project targets institutional deployment. If you use this mechanism in a professional/institutional context regardless, that is your own responsibility to assess against applicable regulation; this project does not intend to pursue certification for that use.  
**Responsible:** See the local shared-access multi-person plan document (not part of this repo).

---

## Overview

Kyoro-HealthHub is built for **equal operation in three private contexts**:

| Context | Isolation Level | Permission | Default Access |
|---------|----------------|--------------|------------------|
| Individual User | One `health.db` per person | None (local) | Full Control |
| Family / Friends (simple) | One `health.db` per person | None (local, trust-based) | Full Control |
| Family / Friends (access-controlled) | **Isolated instances** per person | **Broker-controlled** (Track B) | No Access (Default-Deny) |

> **Note:** The access-controlled variant uses the same security model regardless of who specifically is granting/receiving access within a household or friend group — no compromises depending on the relationship.

---

## Understanding Concurrency: Why There Are Two Access Paths

**This question comes up first whenever someone sets this up for more than one person, which is why it is addressed here at the very beginning, in detail and with a concrete real-world example — not just as a technical footnote.**

Kyoro-HealthHub has **two completely independent access paths** to a person's data — not to make things complicated, but because it reflects two fundamentally different activities that actually occur at different times and in different ways:

| | **Path 1: CLI Scripts** (Import, Compute, Analysis) | **Path 2: Kyoro SymptomTrack Web App** (Symptom Tracking) |
|---|---|---|
| Who uses it? | Whoever manages the data, usually once/periodically per person | People themselves + whoever helps them, continuously throughout the day |
| How does a process work? | One terminal command that runs for a few seconds to minutes, then done | Many short requests (clicks/inputs) throughout the day to a continuously running server |
| How many people simultaneously **in one process**? | One — for the duration of the single command | Many — the server serves multiple people in the same second |
| Access mechanism | Environment variable `KYORO_ACTIVE_PATIENT_DIR` (per terminal window/process) | Explicit parameter `patient_pseudo` in each individual request + permission check |
| Why this mechanism? | Only affects the one running process — no need to rebuild 385 existing scripts | One server process serves many people simultaneously — a global variable would "leak" between them |

### A Concrete Household Morning

**8:00 AM — Anna enters symptoms in the Kyoro SymptomTrack app on her own phone.**

Her phone communicates over the internet with **a single, continuously running server** (the Kyoro SymptomTrack backend process). This server runs around the clock and may be serving several people at the same moment, all typing on their phones simultaneously. Each individual request from Anna's phone explicitly tells the server who she is (`patient_pseudo=PT-XXXX`) — similar to online banking where each request includes the account ID. The server checks **each individual request** anew: is this person authorized for this data? This is why **a parameter must be sent with each request** — a global setting like "currently processing Anna" would not work because in the same moment Ben is also communicating with the same server from his phone.

**8:05 AM — at the same time, Sam (helping manage the household's data) opens a terminal window to import Ben's fitness tracker data** (which they do, for example, once a week per person with wearables).

```bash
export KYORO_ACTIVE_PATIENT_DIR=~/.config/kyoro-master/patients/PT-BEN/
python3 scripts/import_all.py       # runs e.g. 10 minutes
python3 scripts/compute_all.py      # then also runs for several minutes
```

This is a **completely separate process**, independent of the running web server. For the duration of this single terminal window, "Ben" is set — but this affects **only this one window**, not the whole household and not the web server that continues running in parallel and serves Anna's phone inputs.

### "But Import/Compute take a while — doesn't that block everything else?"

**No.** The environment variable `KYORO_ACTIVE_PATIENT_DIR` only applies **to the single process in which it was set** — it does not "radiate" to other terminal windows, other users, or the web server. This is basic operating system behavior: environment variables are inherited by a process from its parent process (the terminal) at startup and are then isolated — two parallel running terminal windows have independent copies.

**Concretely:** Sam opens **a second terminal window** and **simultaneously** imports Anna's data:

```bash
# Terminal Window 1 (already running since 8:05 AM)
export KYORO_ACTIVE_PATIENT_DIR=~/.config/kyoro-master/patients/PT-BEN/
python3 scripts/import_all.py       # still running

# Terminal Window 2 (newly opened, 8:07 AM)
export KYORO_ACTIVE_PATIENT_DIR=~/.config/kyoro-master/patients/PT-ANNA/
python3 scripts/import_all.py       # runs PARALLEL to Window 1, without conflict
```

This works **completely fine in parallel**, for two reasons:

1. **Separate processes, separate environment variables.** Window 1 knows nothing about Window 2's setting and vice versa.
2. **Separate files.** Ben's data is in `PT-BEN/data/health.db`, Anna's in `PT-ANNA/data/health.db` — two completely independent SQLite files. One script writes to file A, the other to file B. There is **no common location** where they could interfere with each other.

**The only real limitation:** *Within a single* terminal window/process, "Ben" and "Anna" cannot be set simultaneously — a running `import_all.py` process is fixed to one person for the duration of its run. However, this is not a new limitation introduced by the multi-person model: a single process could only process one import after another sequentially anyway, regardless of whether it involved one or many people.

**Realistic picture for a household with several people:** There is **no artificial bottleneck in the design** that forces "only one person after another." As many parallel terminal windows/processes can be opened as the machine can handle in terms of computing power and I/O capacity — the limit is pure hardware capacity, not the architecture. The only case that would actually serialize (run sequentially instead of simultaneously) is: **the same** person's import is accidentally started twice simultaneously — then the normal SQLite locking logic (WAL mode, `busy_timeout`) applies to **this one** file, just as it does in single-user operation today.

### Why the Web Server (Kyoro SymptomTrack) Must Solve This Differently

The web server is a **single, continuously running process** that answers requests from many different people simultaneously throughout the day — unlike CLI scripts that only run briefly and then terminate. An environment variable like "currently processing person X" would apply to **all simultaneous requests** in this single process — Anna's request and Ben's request would arrive at the same server process within fractions of a second, and a global variable could not have different values for both at the same time. Therefore, **each individual request** receives its own, explicit `patient_pseudo` parameter (see section "Example: Check Access" below), and the permission broker (`authz.check_patient_access()`) checks each request anew to see if the requesting person is authorized for exactly this data.

**Short version:** One process per session (CLI, batch-like) → environment variable is sufficient, saves rebuilding 385 existing scripts, and multiple people can still work in parallel on different data because each terminal window is its own, independent process. Many simultaneous requests in a single running process (web backend) → parameter per request is mandatory, otherwise data from different people would mix in the same process.

---

## Architecture: Two Tracks

### Track A — Instance Isolation (Base)

Each person gets their own **directory** with:

```
~/.config/kyoro-master/patients/
├── PT-A1B2C3D4/          # patient_pseudo (SHA-256 hash of person_number + group_id)
│   ├── .config/kyoro/
│   │   ├── health_config.json  # person-specific config
│   │   └── identity.db         # local identity mapping (empty, as pseudo)
│   └── data/
│       ├── health.db           # encrypted health data (wearables/sensors)
│       ├── medicine.db         # encrypted clinical values (lab, medications, assessments)
│       └── db.key              # encryption key
└── PT-E5F6G7H8/
    └── ...
```

`medicine.db` (clinical values a doctor measures or orders — lab results,
medications, assessments; see [ARCHITECTURE.md](ARCHITECTURE.md)) is isolated
per instance the same way as `health.db`: `templates/health_config.example.json`
carries a `paths.medicine_db` entry, `onboard.py`'s path-rewrite step points it
at the instance directory, and `onboard.py` runs `create_medicine_schema.py`
alongside `init_db.py` so the schema exists before any clinical-value importer
(`import_lab_csv.py`, `import_saliva_ph.py`, `import_urine_strip.py`,
`import_genetics_aniva.py --mode biomarker`) runs against the instance.

**Management:** `scripts/utils/manage/shared_access/manage_people.py`

| Command | Description |
|--------|--------------|
| `python3 scripts/utils/manage/shared_access/manage_people.py add "NUMBER" --group-id "Group-ID"` | Creates new instance directory |
| `python3 scripts/utils/manage/shared_access/manage_people.py list` | Shows all people |
| `python3 scripts/utils/manage/shared_access/manage_people.py activate PT-A1B2C3D4` | Prints export command for shell |
| `python3 scripts/utils/manage/shared_access/manage_people.py deactivate PT-A1B2C3D4` | Marks as inactive (no deletion) |

**Activation for Scripts:**

```bash
# Shell session for a specific person
export KYORO_ACTIVE_PATIENT_DIR="$HOME/.config/kyoro-master/patients/PT-A1B2C3D4"

# All health scripts now automatically use this path
python3 scripts/import_polar.py
python3 scripts/analyse_hrv.py
```

> **Note:** The scripts themselves do **not** need to be changed. Redirection is handled via `KYORO_ACTIVE_PATIENT_DIR` in `scripts/health_config.py`.

---

### Track B — Permission Broker (Kyoro SymptomTrack Backend)

**Note:** Track B is implemented, but — per the scope note above — this documents the built design for private, access-controlled multi-person use, not a certification for institutional deployment.

The broker is implemented in **Kyoro SymptomTrack (PWA Backend)** and uses:

1. **`patient_assignments` table** (`pwa/backend/db.py`):
   - `user_id` (the person granted access)
   - `patient_pseudo` (whose data)
   - `role` (`owner` | `staff_readonly` | `staff_readwrite` | `admin`)
   - `granted_at`, `granted_by`, `revoked_at`

2. **`access_log` table** (audit trail):
   - Every access (allowed or denied) is logged
   - Fields: `user_id`, `patient_pseudo`, `action` (`read` | `write` | `denied`), `ts`, `detail`

**Default-Deny:** Without an entry in `patient_assignments` → **403 Forbidden**.

---

## Permission Model

### Roles

| Role | Description | Write Access |
|------|--------------|----------------|
| `owner` | The person themselves | ✅ |
| `staff_readwrite` | A trusted person with write permission (e.g. helping manage the data) | ✅ |
| `staff_readonly` | A trusted person with read-only access | ❌ |
| `admin` | Administrator (still needs explicit assignment entry) | ✅ |

> **Important:** Even `admin` needs an **explicit entry** per person. There is no global "super-admin" role. Role names are unchanged internal identifiers (`staff_readwrite`/`staff_readonly`) — they apply equally to any trusted person helping manage someone's data, not specifically to professional staff.

### Example: Creating an Assignment

```sql
-- Anna (user_id = 'anna') may read and write to her own data, PT-A1B2C3D4
INSERT INTO patient_assignments 
  (user_id, patient_pseudo, role, granted_by, granted_at)
VALUES 
  ('anna', 'PT-A1B2C3D4', 'owner', 'admin', datetime('now'));

-- Sam (user_id = 'sam') may only read, helping keep an eye on things
INSERT INTO patient_assignments 
  (user_id, patient_pseudo, role, granted_by, granted_at)
VALUES 
  ('sam', 'PT-A1B2C3D4', 'staff_readonly', 'anna', datetime('now'));
```

### Example: Checking Access (in code)

```python
# In FastAPI routes (pwa/backend/main.py)
from authz import check_patient_access

@app.get("/api/migraine/history")
def migraine_history(patient_pseudo: str, date_from: str, date_to: str,
                     user: CurrentUser):
    check_patient_access(user, patient_pseudo)  # 403 if not authorized
    return db.get_migraine_history(patient_pseudo, date_from, date_to)

# Or as FastAPI dependency
from authz import require_patient_access

@app.get("/api/entries")
def get_entries(patient_pseudo: str,
               user: Annotated[CurrentUser, Depends(require_patient_access(patient_pseudo))]):
    return db.get_entries_for_range(patient_pseudo, ...)
```

---

## Tool Integration: "Gated via Instance Selection"

**Principle:** Tools like Datasette, Grafana, or Kyoro SymptomTrack itself **do not check permissions**. Instead:

1. The **broker** decides which instance a person is allowed to open
2. Once the instance is released, tools may **work freely** within that instance
3. The restriction is achieved through **instance isolation**, not tool-specific ACLs

### Datasette

```bash
export KYORO_ACTIVE_PATIENT_DIR="$HOME/.config/kyoro-master/patients/PT-A1B2C3D4"
python3 scripts/utils/serve_instance_tools.py datasette --port 8001
```

### Grafana

Not integrated by this project. If you want dashboards beyond what Datasette
provides, set up Grafana yourself against a decrypted copy of the instance's
`health.db` — installation-specific, not part of this repo. The same gating
principle above still applies: whatever instance's DB you point Grafana at
is the only data it can see.

### Kyoro SymptomTrack (PWA)

Kyoro SymptomTrack already uses the backend permission system. The frontend routes are tied to the authorization checks in `pwa/backend/authz.py`.

---

## Privacy & Security by Design

### 1. Anonymization/Pseudonymization

- **`identity.db`** (in `~/.config/kyoro/`) holds the only mapping between plaintext IDs and pseudonyms
- **`health.db`** contains **only pseudonyms** (`person`, `patient_pseudo`)
- **`patient_number_map`** in `master.db` (`~/.config/kyoro-master/master.db`) stores person numbers as **internal file numbers**, not as plain names

**Example:**
```python
# In scripts/utils/manage/shared_access/manage_people.py
def _pseudo(person_number: str, group_id: str = "") -> str:
    h = hashlib.sha256((person_number + group_id).encode()).hexdigest()
    return "PT-" + h[:8].upper()
```

### 2. Security by Default

- New person instance: **isolated + encrypted by default**
- New trusted person: **no access by default** (Default-Deny)
- All data: **encrypted in health.db and medicine.db** (SQLCipher)

### 3. Audit Trail

Every access attempt is logged in `access_log`:

```sql
SELECT * FROM access_log WHERE patient_pseudo = 'PT-A1B2C3D4';
-- action: 'read' | 'write' | 'denied'
-- detail: e.g., 'no assignment' or 'readonly role, write attempted'
```

---

## Setup: Step-by-Step

### 1. Prerequisites

- [ ] `pwa/` merged back to `main` (completed)
- [ ] `scripts/utils/create_identity_schema.py` runs without errors
- [ ] `python3 scripts/utils/create_identity_schema.py` (creates/upgrades `identity.db`)

### 2. Setting Up Track A

```bash
# 1. Initialize person registry
python3 scripts/utils/manage/shared_access/manage_people.py add "NR-001" --group-id "Household-A"
# → Creates ~/.config/kyoro-master/patients/PT-XXXXXXXX/

# 2. Onboard person (run from anywhere — onboard.py is driven by the env
#    var, not by the working directory; no "cd" into the instance needed)
export KYORO_ACTIVE_PATIENT_DIR="$HOME/.config/kyoro-master/patients/PT-XXXXXXXX"
python3 ~/Kyoro-HealthHub/onboard.py

# 3. Add more people
python3 scripts/utils/manage/shared_access/manage_people.py add "NR-002" --group-id "Household-A"
```

### 3. Setting Up Track B (Kyoro SymptomTrack Backend)

```bash
# 1. Configure auth system
cd pwa/backend
python3 auth.py --setup
# → JWT secret + create first user
# → Scan TOTP QR code (e.g., Google Authenticator, Aegis)

# 2. Add more users
python3 auth.py --add-user anna --name "Anna"
python3 auth.py --add-user sam --name "Sam" --readonly

# 3. Assign people (SQL or Admin UI)
# See section "Example: Creating an Assignment" above

# 4. Test TOTP end-to-end (required before enabling Track B for real use)
python3 auth.py --totp-now anna  # show current code
# → Enter in authenticator app
# → POST /auth/login with user_id + totp_code
# → Test token against real endpoint
```

### 4. Integrating Broker into Routes

```python
# In pwa/backend/main.py (example for migraine routes)
from authz import check_patient_access

@app.get("/api/migraine/history")
def migraine_history(patient_pseudo: str, date_from: str, date_to: str,
                     user: CurrentUser):
    check_patient_access(user, patient_pseudo)
    return db.get_migraine_history(user.user_id, patient_pseudo, date_from, date_to)
```

---

## Migration of Existing Installations

### Existing Single-User Installations

No changes needed. The existing `health.db` in `~/Kyoro-HealthHub/data/` continues to work:

- `KYORO_ACTIVE_PATIENT_DIR` not set → default behavior
- All scripts work as before

### Switching to Shared, Access-Controlled Operation

1. **Create Backups:**
   ```bash
   cp -r ~/Kyoro-HealthHub/data ~/kyoro-backup/
   cp ~/.config/kyoro/health_config.json ~/kyoro-backup/
   ```

2. **Use First Person as Base:**
   ```bash
   mkdir -p ~/.config/kyoro-master/patients/PT-BASE
   cp -r ~/Kyoro-HealthHub/data ~/.config/kyoro-master/patients/PT-BASE/
   cp ~/.config/kyoro/health_config.json ~/.config/kyoro-master/patients/PT-BASE/.config/kyoro/
   ```

3. **Register Person:**
   ```bash
   python3 scripts/utils/manage/shared_access/manage_people.py add "NR-001" --group-id "Household-A"
   # → Creates PT-XXXXXXXX
   ```

4. **Migrate Data:**
   ```bash
   cd ~/.config/kyoro-master/patients/PT-XXXXXXXX/
   rm -rf data/ .config/kyoro/health_config.json
   cp -r ~/kyoro-backup/data .
   cp ~/kyoro-backup/health_config.json .config/kyoro/
   ```

---

## Bulk Anonymized Export (Multiple People at Once)

Beyond exporting a single person's data, `scripts/exporters/export_research_cohort.py`
merges the existing `research` export profile across **all active, consented**
instances into one anonymized dataset. This is a general-purpose tool for
combining several people's data into one de-identified dataset — usable for
whatever private purpose you have (e.g. comparing anonymized trends across
a family), not exclusively for formal research. See
`openspec/specs/research-cohort-export/spec.md` for the full requirements.

### 1. Record a grant before exporting

The exporter refuses to include any instance without an active
(non-revoked) grant record for the requested scope — no silent skip, hard
abort listing which people are missing a grant:

```bash
python3 scripts/utils/manage/shared_access/manage_access_grants.py grant \
    --person PT-A1B2C3D4 --scope export-2026-hrv-comparison
python3 scripts/utils/manage/shared_access/manage_access_grants.py list --person PT-A1B2C3D4
python3 scripts/utils/manage/shared_access/manage_access_grants.py revoke \
    --person PT-A1B2C3D4 --scope export-2026-hrv-comparison
```

Revoking does not delete the grant row (kept for audit history) — a
person can re-grant under the same scope afterwards; the CLI creates a
new row rather than reusing the revoked one.

### 2. Run the export

```bash
python3 scripts/exporters/export_research_cohort.py \
    --scope export-2026-hrv-comparison \
    --profile research \
    --quasi-identifiers age_band,timezone \
    --k 5 --age-band-width 5 \
    --date-from 2020-01-01 --date-to 2026-12-31
```

If any active instance lacks a grant for the scope, the tool aborts
**before writing any output** and lists which people are missing a grant.
If an instance's own export subprocess fails (e.g. a locked or corrupted
database), the whole run aborts rather than silently shipping an
incomplete dataset — check stderr for which instance failed.

### 3. What gets de-identified, and how

- **Date shifting**: every date/timestamp value is shifted by an offset
  that is deterministic per person (same person → same offset across
  repeated runs) but not recoverable from the output. Column names are
  matched by a broadened heuristic (`_at`, `_date`, `_start`, `_end`,
  `_from`, `_to`, `_dt`, plus `ts`/`date`/`datetime`/`timestamp`/`day`) **and**
  by inspecting the value itself (anything that looks like an ISO-8601
  date/datetime gets shifted even if its column name wasn't anticipated) —
  this defense-in-depth matters because a single unshifted real date next
  to a shifted one lets a recipient recompute the person's offset and
  reverse every other column.
- **Age banding**: birthdates (where present) become N-year bands (default
  5) instead of exact dates.
- **k-anonymity**: rows are grouped by the `--quasi-identifiers` columns
  you specify; any group smaller than `--k` is suppressed from the
  deliverable and written instead to a locally-retained `suppressed/`
  directory (never delivered). If none of the requested quasi-identifier
  columns exist on a given table, the tool prints a loud warning and
  records it in `manifest.json` — it will **not** silently pretend the
  check ran.

### 4. Reading the output

```
KYORO_MASTER_DIR/research_exports/<date>/
├── deliverable/        # what you actually hand over
│   ├── measurements.csv
│   └── ...
├── suppressed/         # k-anonymity dropouts — kept locally, never shipped
└── manifest.json        # k, age-band width, QI columns, instance counts,
                          # rows suppressed per table, any missing-QI warnings
                          # (deliberately does NOT record per-person date
                          #  offsets or pseudonyms — that would defeat them)
```

### 5. Known limitation

Date shifting removes cross-person temporal alignment by design (each
person's offset is independent) — a use case that genuinely needs to know
"did everyone's HRV move together during the same calendar week" cannot
use this tool's output as-is; that would require a separate, more
carefully scoped export path.

---

## Compliance & Ethics

- **No Profiling** (see `docs/ETHICS.md`)
- **No use by insurers/employers**
- **Private use only** — see scope note at the top of this document
- **Same rules for everyone using the access-controlled variant**
- **Privacy by Design & by Default** (see guiding principles in the local plan document)

---

## Troubleshooting

### "No access assigned to this person"

1. Check if user exists:
   ```bash
   python3 pwa/backend/auth.py --list
   ```

2. Check if assignment exists:
   ```sql
   SELECT * FROM patient_assignments 
   WHERE user_id = '<user_id>' AND patient_pseudo = '<patient_pseudo>'
     AND revoked_at IS NULL;
   ```

3. Create assignment (if missing):
   ```sql
   INSERT INTO patient_assignments 
     (user_id, patient_pseudo, role, granted_by, granted_at)
   VALUES 
     ('<user_id>', '<patient_pseudo>', 'staff_readwrite', 'admin', datetime('now'));
   ```

### TOTP Login Fails

1. Check secret:
   ```bash
   python3 pwa/backend/auth.py --totp-now <user_id>
   ```

2. Authenticator app: synchronize time
3. Enter code within 30 seconds (validation window: ±1 code)

---

## Glossary

| Term | Explanation |
|------|-----------|
| `patient_pseudo` | `PT-` + SHA-256(person_number + group_id)[0:8] (e.g., `PT-A1B2C3D4`) — internal identifier name unchanged from earlier versions |
| `person_number` | Internal file number (e.g., `NR-001`), **not a plain name** |
| `instance_dir` | Full path to person's directory (e.g., `/home/user/.config/kyoro-master/patients/PT-A1B2C3D4`) |
| `user_id` | User identifier (e.g., `anna`, `sam`) |
| Default-Deny | No access without explicit assignment |
