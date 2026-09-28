# PEM-Kaskaden-Analyse — Post-Exertional Malaise Lag-Korrelation

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/analysis/neurology/analyse_pem_cascade.py`

**Evidence tier:** heuristic (deliberate design from domain knowledge, no formal literature or validation basis)

## Purpose

Examines the time-lagged relationship between physical activity (training load, steps) and HRV drop / symptom worsening (typical PEM pattern: 24–72 h lag).

## Relevance

Enables neurological analysis, essential for nervous system diagnostics

## Method

Pearson correlation (pure Python) for activity(t) × HRV(t+lag) across a lag scan of 0–lag_max days; direct access to raw training and HRV data without compute layer.

## Scoring

```
HRV-Abfall-Warnung (heuristisch, projektintern):
HRV-Deviation < −10% = PEM-Proxy-Signal (heuristisch, nicht kalibriert)
Aktivitätsproxy: (steps − 2000) × 0.05 kcal-Äquivalent (heuristisch)
24–72 h Lag: klinisch beschrieben für PEM; Lag-Max projektintern wählbar (default 4 Tage)
Basis: Lag-Fenster orientiert an PEM-Literatur; alle Schwellenwerte projektintern.
```

## Data flow

- **Reads:** `sessions`, `session_metrics`, `measurements`, `symptoms`
- **Writes:** `analyses/postinfectious/pem_cascade_*.{md,png}`

## Limitations

Heuristic method: HRV drop threshold −10% as PEM proxy is heuristic and not calibrated from study data; Pearson correlation without significance threshold or multiple testing correction; does not use the calibrated pem_evidence_scores layer; small data basis; causal direction not determinable.

## References

- Task Force of the European Society of Cardiology and the North American Society of Pacing and Electrophysiology (1996). Heart rate variability: standards of measurement, physiological interpretation, and clinical use. Circulation, 93(5), 1043-1065. doi:10.1161/01.CIR.93.5.1043
- Davenport TE, Stevens SR, VanNess MJ, Snell CR, Little T (2010). Conceptual model for physical therapist management of chronic fatigue syndrome/myalgic encephalomyelitis. Physical Therapy, 90(4):602-614. doi:10.2522/ptj.20090047

## Usage

```bash
python analyse_pem_cascade.py
python analyse_pem_cascade.py --help
python analyse_pem_cascade.py --from 2024-01-01 --to 2024-12-31
```
