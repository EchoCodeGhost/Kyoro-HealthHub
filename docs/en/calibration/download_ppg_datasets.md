# PPG-Kalibrierungsdatensätze Download (BIDMC, Pulse Transit Time PPG, PPG-BP, MIMIC-III-Ext-PPG)

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/calibration/download_ppg_datasets.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Downloads public PPG datasets for presyncope-detector calibration (BACK-26, local feature backlog) — basis for signal pipeline, respiratory rate, and quality validation, not syncope-specific data itself.

## Relevance

Enables download of reference data, essential for calibration and validation

## Method

BIDMC + Pulse Transit Time PPG: open PhysioNet WFDB databases (Open Data Commons Attribution License, NO credentialed access needed), via the wfdb library already used elsewhere in this project (see download_afdb.py). PPG-BP: open Figshare dataset (CC-BY), via the Figshare API (dynamically resolved download URLs, no hardcoded file links). MIMIC-III-Ext-PPG: ONLY with the user's own PhysioNet credentialed credentials (environment variables, never in code) — its Credentialed Health Data License forbids redistribution, so skipped by default.

## Data flow

- **Reads:** `PhysioNet`, `(bidmc`, `pulse-transit-time-ppg`, `databases)`, `Figshare`, `API`, `(online)`
- **Writes:**

  ```
  data/calibration/bidmc/, data/calibration/pulse_transit_time_ppg/,
  data/calibration/ppgbp/, data/calibration/mimic_iii_ext_ppg/ (--credentialed only)
  ```

## Limitations

Requires internet connection + wfdb library + requests. PhysioNet database slugs (`bidmc`, `pulse-transit-time-ppg`) may change with future versions — check the physionet.org project page for a new slug/version path if downloads fail. The MIMIC-III-Ext-PPG download path is inferred from PhysioNet's own documented wget pattern, not independently tested (no access to physionet.org from the development environment this was written in).

## References

- Pimentel MAF, Johnson AEW, Charlton PH et al. (2017). Toward a Robust Estimation of Respiratory Rate From Pulse Oximeters. IEEE Transactions on Biomedical Engineering, 64(8):1914-1923. doi:10.1109/TBME.2016.2613124
- Liang Y, Chen Z, Liu G, Elgendi M (2018). A new, short-recorded photoplethysmogram dataset for blood pressure monitoring in China. Scientific Data, 5(1). doi:10.1038/sdata.2018.20
- Goldberger AL, Amaral LAN, Glass L, et al. 2000, Circulation,
- Goldberger AL, Amaral LAN, Glass L et al. (2000). PhysioBank, PhysioToolkit, and PhysioNet. Circulation, 101(23). doi:10.1161/01.CIR.101.23.e215

## Usage

```bash
python3 scripts/calibration/download_ppg_datasets.py                # open datasets only
python3 scripts/calibration/download_ppg_datasets.py --only bidmc
python3 scripts/calibration/download_ppg_datasets.py --only ptt-ppg
python3 scripts/calibration/download_ppg_datasets.py --only ppgbp
# Credentialed (needs an approved PhysioNet account for this specific project):
PHYSIONET_USER=<user> PHYSIONET_PASSWORD=<pw> \
    python3 scripts/calibration/download_ppg_datasets.py --credentialed
```
