# PTT / HRV / Blood pressure — Correlationsanalyse

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/analysis/cardiovascular/analyse_ptt_hrv.py`

**Evidence tier:** heuristic (deliberate design from domain knowledge, no formal literature or validation basis)

## Purpose

Correlates pulse transit time measurements (Polar Vantage V3 spot-HRV) with nightly HRV and blood pressure trends from the Omron device.

## Relevance

Enables cardiovascular analysis, essential for cardiac diagnostics

## Method

Pearson/Spearman correlation between PTT (contract/relax), HRV spot, nightly RMSSD and blood pressure. No clinical validation of PTT-to-BP calibration.

## Scoring

```
Correlation strength: |r| <0.2 weak | 0.2-0.4 moderate | 0.4-0.7 strong | >0.7 very strong
PTT measurement type: contract | relax (Polar Vantage V3)
```

## Data flow

- **Reads:** `polar_hrv_spot`, `measurements`, `(hrv_rmssd/rmssd_ms`, `geräteunabhängig`, `über`, `modules/metric_loader)`, `omron_blood_pressure`
- **Writes:** `analyses/cardiovascular/analyse_ptt_hrv.{png,md}`

## Limitations

Heuristic method: PTT as BP proxy not clinically validated; optical-sensor PTT has lower accuracy than cuff-based methods. Device-specific measurement error not accounted for.

## References

- Mukkamala R, Hahn JO, Inan OT, Mestha LK, Kim CS, Toreyin H, Kyal S (2015). Toward Ubiquitous Blood Pressure Monitoring via Pulse Transit Time: Theory and Practice. IEEE Transactions on Biomedical Engineering, 62(8):1879-1901. doi:10.1109/TBME.2015.2441951
- Payne RA, Symeonides CN, Webb DJ, Maxwell SRJ (2006). Pulse transit time measured from the ECG: an unreliable marker of beat-to-beat blood pressure. Journal of Applied Physiology, 100(1):136-141. doi:10.1152/japplphysiol.00657.2005

## Usage

```bash
python analyse_ptt_hrv.py
python analyse_ptt_hrv.py --help
python analyse_ptt_hrv.py --from 2024-01-01 --to 2024-12-31
```
