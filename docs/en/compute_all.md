# Master Compute — Orchestriert die Ausführung aller Compute-Skripte.

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/compute_all.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Orchestrates the execution of all compute scripts in the correct dependency order. Ensures all derived metrics are up-to-date before queries or analyses are performed.

## Relevance

Provides health data functions, essential for medical data processing

## Method

Execution order is dependency-based. Scripts are started sequentially. On errors, execution continues but the error is logged. --only-exact runs only the named scripts, in the same order. --on-demand runs one script outside the full run and logs it.

## Data flow

- **Reads:** `Keine`, `direkten`, `Eingabetabellen`, `(orchestriert`, `andere`, `Skripte)`
- **Writes:**

  ```
  compute_log in health.db (Skriptname, Git-Commit, Returncode, Laufzeit
  pro Compute-Lauf — s. modules/pipeline_runner.py); sonst keine direkten
  Ausgabetabellen (orchestriert andere Skripte)
  ```

## Limitations

No medical interpretation. Pure technical orchestration. Failures of individual scripts do not abort the entire process, but may result in incomplete data.

## Usage

```bash
python3 compute_all.py                  # alle Compute-Scripts
python3 compute_all.py --skip-quality   # ohne abschließende Qualitätsprüfung
python3 compute_all.py --recompute      # bestehende Ergebnisse neu berechnen
python3 compute_all.py --only-exact compute_stress,compute_canonical
python3 compute_all.py --on-demand compute_orthostatic_detection -- --date-from 2020-01-01
```
