# Orthostatik-Protokoll (kurz + voll) → health.db (sessions + session_metrics)

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/importers/import_orthostatic_manual.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Imports manually recorded orthostatic protocols in two variants: short morning-routine protocol (HR-only) and full Schellong/NASA Lean Test protocol (HR + blood pressure, 0/1/2/3/5/7/10 min standing, see docs/test_protocols/ORTHOSTATIC_TEST_PROTOCOL.md).

## Relevance

Enables import of health data, essential for comprehensive data analysis

## Method

Simple morning routine protocol: 3 min lying down -> stand up -> HR at 1/3/5/10 min standing. No Kubios required - any HR sensor (chest strap, BP monitor or smartwatch display). Differences from import_kubios_orthostatic.py: - No Kubios export required - Faster morning workflow (< 15 min) - HR at multiple time points (HR rise curve) - Optional symptom recording during test Short CSV format: ts,hr_supine,hr_stand_1m,hr_stand_3m,hr_stand_5m,hr_stand_10m,hr_peak, spo2_supine,spo2_stand,dizzy,fatigue,notes Full protocol (--template-full): additionally hr_stand_0m,hr_stand_2m,hr_stand_7m, hr_supine_2m plus blood pressure columns bp_sys_*/bp_dia_* for supine (2 readings, 1 min apart) and standing (0/1/2/3/5/7/10 min) — device-agnostic, any blood pressure monitor (manual or with automatic series measurement like Withings BPM Core START-3). All columns optional (empty = not measured), both variants share the same schema — no mode flag needed on import, only on template export (--template vs --template-full).

## Data flow

- **Reads:** `CSV-Dateien`, `aus`, `~/Kyoro-HealthHub/imports/orthostatic_manual/`
- **Writes:** `sessions, session_metrics`

## Limitations

hr_peak important for POTS evaluation. Blood pressure values land as session_metrics (mmHg), not in the cross-device blood_pressure table — sufficient for evaluating this one test, but not part of general BP trend analysis.

## Usage

```bash
python3 import_orthostatic_manual.py                  # alle CSVs
python3 import_orthostatic_manual.py --update          # nur neue Daten
python3 import_orthostatic_manual.py --manual           # interaktive Eingabe (Kurzprotokoll)
python3 import_orthostatic_manual.py --template          # CSV-Vorlage Kurzprotokoll
python3 import_orthostatic_manual.py --template-full     # CSV-Vorlage volles Schellong-/NASA-Lean-Test-Protokoll
```
