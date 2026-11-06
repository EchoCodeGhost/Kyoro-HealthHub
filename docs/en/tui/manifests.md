# Manifest-Typen und Ausschlüsse der Pipeline-TUI.

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/tui/manifests.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Describes scripts without a registry of their own, and defines which flags the TUI may pass and which tools it never offers.

## Relevance

Prevents the interface from weakening protections

## Method

Allowlist: build_args() creates arguments only from declared fields, and an entry with a blocked flag cannot be created at all. Paths in EXCLUDED are relative to scripts/; * also matches across directories.

## Data flow

- **Reads:** `Keine`, `Tabellen`
- **Writes:** `Keine Tabellen`

## Limitations

Entries for manual importers and utilities are still missing. --person stays open until the question about the person field is settled.

## Usage

```bash
entry = ScriptEntry("analysis/manual/analyse_ecg_session.py", ("EKG", "ECG"), "analyse_manual",
                    fields=(IntField("--session", required=True), BoolField("--plot")))
entry.build_args({"--session": 42, "--plot": True})
is_excluded("utils/decrypt_db.py")
```
