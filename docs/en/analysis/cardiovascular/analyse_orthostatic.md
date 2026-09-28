# Orthostatic-Evaluation

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/analysis/cardiovascular/analyse_orthostatic.py`

**Evidence tier:** heuristic (deliberate design from domain knowledge, no formal literature or validation basis)

## Purpose

Analyses all stored orthostatic tests for POTS criterion, vagal response (RMSSD drop), resting heart rate and trajectory over the test series.

## Relevance

Enables cardiovascular analysis, essential for cardiac diagnostics

## Method

POTS criterion: ΔHR ≥30 bpm (validated per Sheldon 2015); borderline limits (20/15 bpm) and RMSSD drop threshold (70%) are heuristic without guideline basis.

## Scoring

```
ΔHR-Klassifikation (4 Stufen):
  POTS-Kriterium  : ΔHR ≥30 bpm  (validiert: Sheldon 2015 doi:10.1016/j.hrthm.2015.03.029)
  Deutlich erhöht : ΔHR 20–29 bpm (heuristisch — kein Leitlinien-Standard)
  Grenzwertig     : ΔHR 15–19 bpm (heuristisch — kein Leitlinien-Standard)
  Normal          : ΔHR <15 bpm
RMSSD-Drop:
  >70 % Abfall    = stark eingeschränkte vagale Antwort (heuristisch — kein validierter Grenzwert)
Validierte Komponenten: POTS-Kriterium ≥30 bpm (Sheldon 2015).
Heuristische Komponenten: Borderline-Grenzen (20/15 bpm), RMSSD-Drop-Schwelle (70%).
```

## Data flow

- **Reads:** `sessions`, `session_metrics`
- **Writes:** `analyses/cardiovascular/orthostatic_*.{md,png}`

## Limitations

Heuristic method: Sheldon 2015 criterion requires sustained ΔHR over 10 minutes — peak HR is used here (tendency to over-detect short spikes); Kubios provides mean segment HR, not the peak stand-up HR; RMSSD drop threshold (70%) not validated; RHR_ELEVATED = 80 bpm is project-internal (clinical reference value starts at 100 bpm).

## References

- Sheldon RS, Grubb BP 2nd, Olshansky B, et al. (2015). 2015 Heart Rhythm Society expert consensus statement on the diagnosis and treatment of postural tachycardia syndrome, inappropriate sinus tachycardia, and vasovagal syncope. Heart Rhythm, 12(6), e41-e63. doi:10.1016/j.hrthm.2015.03.029
- Hogwood AC et al. 2025. Determinants of Exercise Intolerance in Postural Orthostatic Tachycardia Syndrome: A Systematic Review. Exercise, Sport,
- Hogwood AC, Abbate G, Thomas G et al. (2025). Determinants of Exercise Intolerance in Postural Orthostatic Tachycardia Syndrome: A Systematic Review. Exercise, Sport and Movement, 3(4). doi:10.1249/ESM.0000000000000055

## Usage

```bash
python analyse_orthostatic.py
python analyse_orthostatic.py --help
python analyse_orthostatic.py --from 2024-01-01 --to 2024-12-31
```
