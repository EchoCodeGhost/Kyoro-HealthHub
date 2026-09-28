# Pan-Tompkins Re-Analyse einer gespeicherten ECG-Session

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/analysis/manual/analyse_ecg_session.py`

**Evidence tier:** research (peer-reviewed literature basis, but no formal clinical validation study with endpoints)

## Purpose

Performs Pan-Tompkins re-analysis on stored ECG sessions

## Relevance

Enables health data analysis, essential for medical diagnostics

## Method

Loads raw samples from ecg_samples, runs Pan-Tompkins QRS detection, derives RR intervals, and compares results against device classification.

## Data flow

- **Reads:** `ecg_samples`
- **Writes:** `rr_intervals_manual`

## Limitations

Heuristic QRS detection. Accuracy depends on signal quality.

## References

- Pan J, Tompkins WJ (1985). A Real-Time QRS Detection Algorithm. IEEE Transactions on Biomedical Engineering, BME-32(3):230-236. doi:10.1109/TBME.1985.325532

## Usage

```bash
python3 scripts/analysis/analyse_ecg_session.py --list
python3 scripts/analysis/analyse_ecg_session.py --session "2025-05-13T08:42:00"
python3 scripts/analysis/analyse_ecg_session.py --date 2025-05-13
python3 scripts/analysis/analyse_ecg_session.py --session "..." --plot
```
