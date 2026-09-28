# Flüssigkeitsaufnahme × Orthostatische Intoleranz

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/analysis/cardiovascular/analyse_fluid_orthostatic.py`

**Evidence tier:** heuristic (deliberate design from domain knowledge, no formal literature or validation basis)

## Purpose

Analyses whether adequate fluid and salt intake improves orthostatic tolerance: daily targets, previous-day correlation, sodium effect and caffeine timing.

## Relevance

Enables cardiovascular analysis, essential for cardiac diagnostics

## Method

Fluid target 2,500 ml/day + 3,000 mg sodium (Raj 2013); Pearson correlation previous-day fluid × orthostatic HR delta. No clinically randomised data points.

## Scoring

```
Fluid target: >=2500 ml/day + >=3000 mg Na/day
Orthostatic tolerance: HR delta <20 bpm acceptable | 20-30 bpm borderline | >=30 bpm orthostatic intolerance
Correlation strength: |r| <0.2 weak | 0.2-0.4 moderate | 0.4-0.7 strong | >0.7 very strong
```

## Data flow

- **Reads:** `fluid_intake`, `sessions`, `session_metrics`
- **Writes:** `analyses/cardiovascular/*.{md,png} (kein DB-Write)`

## Limitations

Heuristic method: Validated components: fluid target 2,500 ml + 3,000 mg Na (Raj 2013, doi:10.1161/CIRCULATIONAHA.112.144501), orthostatic criterion >=30 bpm (Sheldon 2015, doi:10.1016/j.hrthm.2015.03.029). Heuristic: Pearson correlation previous-day fluid × HR delta, borderline threshold at 20 bpm. Fluid logging is manual and incomplete. Orthostatic HR delta from consumer device without standardised protocol. No control group. n=1.

## References

- Raj SR (2013). Postural Tachycardia Syndrome (POTS). Circulation, 127(23):2336-2342. doi:10.1161/CIRCULATIONAHA.112.144501
- Arnold et al. 2018, Heart Rhythm (DOI ausstehend)
- Sheldon RS, Grubb BP, Olshansky B et al. (2015). 2015 Heart Rhythm Society Expert Consensus Statement on the Diagnosis and Treatment of Postural Tachycardia Syndrome, Inappropriate Sinus Tachycardia, and Vasovagal Syncope. Heart Rhythm, 12(6):e41-e63. doi:10.1016/j.hrthm.2015.03.029

## Usage

```bash
python analyse_fluid_orthostatic.py
python analyse_fluid_orthostatic.py --help
python analyse_fluid_orthostatic.py --from 2024-01-01 --to 2024-12-31
```
