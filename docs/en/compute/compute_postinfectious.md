# Reaktionsmuster-Erkennung — Heuristische Identifizierung via rollierender persönlicher Baseline.

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/compute/compute_postinfectious.py`

**Evidence tier:** heuristic (deliberate design from domain knowledge, no formal literature or validation basis)

## Purpose

Detects reaction patterns after exertion by comparing exertion on day N with HRV/RHR deviations on day N+1 relative to an individual rolling baseline.

## Relevance

Enables post-infectious pattern analysis, essential for long-term monitoring

## Method

A rolling 28-day baseline sets person-specific thresholds for HRV (Root Mean Square of Successive Differences) and RHR (Resting Heart Rate). Days N+1, N+2 and N+3 after exertion are checked; a reaction pattern signal is raised when HRV on any of these days is more than 1 standard deviation below baseline OR RHR is more than 1 standard deviation above baseline (the strongest deviation of the three days is reported). Exertion is calculated from steps, active energy, and stress score.

## Scoring

```
direct = HRV_Abweichung * 40 + RHR_Abweichung * 30 + Belastungsintensitaet * 30
```

## Data flow

- **Reads:** `measurements`, `polar_nightly_hrv`, `daily_stress`, `sessions`
- **Writes:** `pem_correlation`

## Limitations

Heuristic method: The ±1 SD threshold is a statistical heuristic, not a clinically validated definition. The 28-day baseline is unstable with highly variable data and requires at least 20 days of valid data. Reaction pattern signals are based on individual patterns and are not generalizable. Does not replace medical diagnosis.

## References

- Carruthers BM, van de Sande MI, De Meirleir KL et al. (2011). Myalgic encephalomyelitis: International Consensus Criteria. Journal of Internal Medicine, 270(4):327-338. doi:10.1111/j.1365-2796.2011.02428.x
- [UNVERIFIZIERT] "Jason et al. 2021, Frontiers in Medicine, doi:10.3389/fmed.2021.637976" — DOI löst nicht auf, kein Jason-Paper 2021 in diesem Journal-Jahrgang auffindbar (Crossref-Journal-Direktsuche negativ). Vor Verwendung/Vertrauen manuell prüfen.

## Usage

```bash
python compute_postinfectious.py
python compute_postinfectious.py --update
python compute_postinfectious.py --from 2024-01-01 --to 2024-12-31
python compute_postinfectious.py --person self
```
