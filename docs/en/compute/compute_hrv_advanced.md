# Advanced HRV analysis from beat-to-beat interval data (ppi_raw, any device).

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/compute/compute_hrv_advanced.py`

**Evidence tier:** research (peer-reviewed literature basis, but no formal clinical validation study with endpoints)

## Purpose

Computes, per 5-minute window, the HRV metrics that Kubios HRV also produces — as far as reproducible in pure Python. Processes ppi_raw device-agnostically: which device delivered a window is determined and stored per window (column `device`), never assumed — the module previously claimed "Polar PPI" in its name/docstring, but ppi_raw in fact holds any source that delivers beat-to-beat intervals (chest strap, optical sensor, ECG reconstruction).

## Relevance

Enables heart rate variability analysis, essential for autonomic health monitoring

## Method

Time domain: RMSSD, SDNN, pNN50. Poincaré: SD1, SD2, SD1/SD2. Frequency: LF, HF, LF/HF, total power (Welch, 4 Hz). Non-linear: DFA alpha1 (Kubios scales 4–16 log-spaced: 4,5,6,7,8,9,10,12,14,16; min. 100 beats). Entropy: SampEn (m=2, r=0.2×SD). Baevsky stress index. Artefact correction per Kubios (dRR-based, 90-beat window, threshold 5.2×quartile deviation, linear interpolation) — applied before all metrics including DFA alpha1. Windows whose RMSSD is still above RMSSD_PLAUSIBLE_MAX_MS after correction are dropped rather than stored — a safety net for windows densely packed with dropout artifacts, where the local correction itself fails (see constant).

## Data flow

- **Reads:** `ppi_raw`
- **Writes:**

  ```
  ppi_hrv_advanced (PRIMARY KEY: (fenster_start, person)); Spalte `device`
  traegt die Geraete-Pseudonym-ID, die die meisten Beats des Fensters
  geliefert hat. Spalte `sensor_mode` traegt den effektiven Messmodus
  des Fensters ('ecg' | sensor_type von `device` | NULL), ermittelt aus
  ppi_raw.source ueber modules/ppi_provenance.py — genauer als `device`
  allein, da dasselbe Geraet je nach Aufnahmeweg unterschiedliche Modi
  liefern kann (z.B. eine optische Uhr mit zusaetzlicher
  EKG-Ableitung). Beide Spalten sind Rohangaben; Downstream-Leser wie
  compute_af_evidence.py ziehen daraus die Konfidenzstufe
  (modules/sensor_confidence.grade_for()).
  ```

## Limitations

Validation against Kubios: RMSSD/SDNN identical. SD1 uses the geometric Poincaré definition sqrt(var(diffs,ddof=1)/2); Kubios uses RMSSD/sqrt(2) — deviation <0.5 % for stationary HRV data. SD1²+SD2²=2×SDNN² (Poincaré identity) holds exactly. LF/HF ±5–15 % depending on window length.

## References

- Task Force of the European Society of Cardiology and the North American Society of Pacing and Electrophysiology (1996). Heart rate variability: standards of measurement, physiological interpretation, and clinical use. Circulation, 93(5), 1043-1065. doi:10.1161/01.CIR.93.5.1043
- Tarvainen MP, Niskanen JP, Lipponen JA, Ranta-aho PO, Karjalainen PA (2014). Kubios HRV – Heart rate variability analysis software. Computer Methods and Programs in Biomedicine, 113(1):210-220. doi:10.1016/j.cmpb.2013.07.024

## Usage

```bash
python compute_hrv_advanced.py
python compute_hrv_advanced.py --update
python compute_hrv_advanced.py --from 2024-01-01 --to 2024-12-31
python compute_hrv_advanced.py --rebuild
python compute_hrv_advanced.py --person partner_id
```
