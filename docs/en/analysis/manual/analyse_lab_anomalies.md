# analyse_lab_anomalies.py — Chronische Mangel-/Überschuss-Erkennung aus Laborwerten

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/analysis/manual/analyse_lab_anomalies.py`

**Evidence tier:** heuristic (deliberate design from domain knowledge, no formal literature or validation basis)

## Purpose

Automatically finds lab parameters that sit below (or above) the reference range across most of the measured time points — instead of relying on memory of which deficiencies are "already known".

## Relevance

Automates detection of chronic deficiencies/excesses, essential for not overlooking them

## Method

Reads lab_all (health.db+medicine.db via open_lab_db) for all quantitative measurements (wert_num + ref_min/ref_max set). Per parameter: fraction of measurements below ref_min ("deficiency rate") or above ref_max ("excess rate"). Flagged as chronic when the rate exceeds a threshold AND enough measurements exist (prevents a single outlier from triggering an alert). No LLM involved — purely statistical.

## Scoring

```
Pro (Kategorie, Parameter)-Gruppe mit mindestens --min-measurements
(Default 3) Messungen: rate_low = Anteil der Messungen unter
ref_min, rate_high = Anteil über ref_max (je Messung gegen die
EIGENE Referenzspanne dieser Zeile verglichen, nicht gegen eine
gemeinsame). rate_low >= --threshold (Default 0.5) → "mangel",
sonst rate_high >= threshold → "ueberschuss". Beide Richtungen
sind gleich gewichtet, keine Richtung bevorzugt.
```

## Data flow

- **Reads:** `medicine.db`, `(lab_manual)`, `health.db`, `(lab_results)`, `via`, `lab_all`
- **Writes:** `Analyseergebnis als Markdown (analyses/manual/)`

## Limitations

Reference ranges come from the DB (lab-dependent, can vary slightly between labs). Qualitative values (negative/positive) are not considered, only numeric ones. Detects statistical patterns only, no clinical judgment — not a substitute for a doctor's assessment.

## Usage

```bash
python3 analyse_lab_anomalies.py
python3 analyse_lab_anomalies.py --threshold 0.6 --min-measurements 5
python3 analyse_lab_anomalies.py --from 2020-01-01
```
