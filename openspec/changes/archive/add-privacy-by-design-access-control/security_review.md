# Security review: authz.py

## Conducted by: Mistral Vibe

## Security issues found

### 1. Race condition between authorization check and data access (7.2a)

**Problem:** In `check_patient_access()`, authorization is checked, but the subsequent data access in the API endpoints is not atomic. A user could lose authorization between the check and the actual data access.

**Example scenario:**
1. User A has access to patient P
2. `check_patient_access()` gives the green light
3. An administrator revokes A's authorization for P
4. A performs the data access (no re-check)

**Recommendation:**
- Implement a row-level security mechanism in the database
- Or: perform the authorization check directly in the SQL queries with a JOIN on patient_assignments
- Or: use database transactions with SERIALIZABLE isolation

### 2. Audit-log timing problem (7.2b)

**Problem:** In `check_patient_access()`, logging happens AFTER the authorization check. If a crash occurs after a successful authorization check but before logging, there is no audit trail of an unauthorized access attempt.

**Example scenario:**
1. Attacker attempts access with an invalid token
2. `check_patient_access()` raises an exception
3. The process crashes before logging
4. No audit entry despite the access attempt

**Recommendation:**
- Perform logging BEFORE the authorization check
- Or: use database transactions that make logging and the check atomic
- Or: implement a separate, buffered audit-log system

### 3. Missing validation of patient_pseudo (7.2c)

**Problem:** There is no validation of whether `patient_pseudo` is valid (not empty, correct format). An empty or invalid patient_pseudo could lead to unexpected behavior.

**Example scenario:**
- Attacker sends `patient_pseudo=""` (empty)
- The SQL query could return unexpected results
- Or: SQL-injection risk (see 7.2d)

**Recommendation:**
- Validate patient_pseudo before use
- Format check (e.g. `PAT-[A-Z0-9]{4}`)
- Reject empty or invalid values

### 4. Potential SQL-injection risk (7.2d)

**Problem:** The `patient_pseudo` parameter is used directly in SQL queries even though it comes from outside. The query does use parameterized queries, but there is no additional validation.

**Example scenario:**
- Attacker attempts SQL injection via specially crafted patient_pseudo values
- Already protected by parameterized queries, but additional validation would be better

**Recommendation:**
- Additional validation of the patient_pseudo format
- Whitelist-based validation
- Length limit

## Summary

The issues found are:
- **7.2a**: Race condition (critical)
- **7.2b**: Audit-log timing (medium)
- **7.2c**: Missing validation (low)
- **7.2d**: SQL-injection risk (low, but present)

## Next steps

These issues should be fixed in order of criticality:
1. Race condition (7.2a) - highest priority
2. Audit-log timing (7.2b) - medium priority
3. Validation (7.2c) and SQL injection (7.2d) - can be fixed together

## Documentation

These issues were documented as new tasks 7.2a-7.2d in tasks.md and should be fixed before the production release.

## Addendum: Fix (Claude)

All four findings were fixed in `pwa/backend/authz.py`, `pwa/backend/db.py`
and `pwa/backend/main.py`; details and the actually observed load-test
numbers (task 7.1) are in `tasks.md` under 7.1/7.2a-7.2d. Short version:

- **7.2a** (race condition): new `authz.authorized_connection()`, keeps
  the check + data access within one `BEGIN IMMEDIATE` transaction.
- **7.2b** (audit-log timing): check + log entry now on the same
  connection, one shared commit().
- **7.2c/7.2d** (validation/defense-in-depth): strict format gate
  (`^PT-[0-9A-F]{8}$`, the real format produced by `manage_patients.py`,
  not the guessed one from the review) before every DB query.

The load test (7.1) uncovered an additional effect not anticipated in
the original review: an obvious-seeming optimization (`BEGIN IMMEDIATE`
only for write routes, deferred `BEGIN` for read routes) produced
`SQLITE_BUSY_SNAPSHOT` errors under load, because every route — including
read routes — triggers an `access_log` write due to 7.2b. This was fixed
with universal `BEGIN IMMEDIATE` (details in `authz.py` comments and
`tasks.md` 7.1).
