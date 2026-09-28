# manage_access_grants.py — Zugriffsfreigaben verwalten (erteilen/auflisten/widerrufen)

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/utils/manage/shared_access/manage_access_grants.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Manages access grants per person for a named purpose (scope) — e.g. "data export for Dr. X" or "review by family member Y". Each person can grant or revoke access separately per purpose. Without a valid grant, a person is excluded from the corresponding exports. Built for the private multi-person context, see SHARED_ACCESS_DEPLOYMENT.md.

## Relevance

Provides health data functions, essential for medical data processing

## Method

Reads/writes the grant table in master.db (see create_master_schema.py). Supports grant (new grant), list (show all grants), and revoke (revoke an existing grant).

## Data flow

- **Reads:** `~/.config/kyoro-master/master.db`, `(Freigabe-Tabelle`, `Personen-Zuordnung)`
- **Writes:** `~/.config/kyoro-master/master.db (Freigabe-Tabelle)`

## Limitations

No automatic validation of purpose labels — the operator is responsible for using meaningful, unambiguous identifiers. Revocation is not retroactive — already exported data remains unaffected.

## Usage

```bash
python3 scripts/utils/manage/shared_access/manage_access_grants.py grant --person PT-ABC12345 --scope export-2026-review
python3 scripts/utils/manage/shared_access/manage_access_grants.py list
python3 scripts/utils/manage/shared_access/manage_access_grants.py list --person PT-ABC12345
python3 scripts/utils/manage/shared_access/manage_access_grants.py revoke --person PT-ABC12345 --scope export-2026-review
```
