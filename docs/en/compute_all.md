# Master Compute — Orchestriert die Ausführung aller Compute-Skripte.

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/compute_all.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Orchestrates the execution of all compute scripts in the correct dependency order. Ensures all derived metrics are up-to-date before queries or analyses are performed.

## Relevance

Provides health data functions, essential for medical data processing

## Method

Execution order is dependency-based. Scripts are started sequentially, with each script only executing if its dependencies (input tables) are available. On errors, execution continues but the error is logged.

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
python3 compute_all.py --from 2024-01-01 --to 2024-12-31
python3 compute_all.py --person self
```
