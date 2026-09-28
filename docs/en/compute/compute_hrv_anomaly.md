# HRV-Anomalie-Detektion — Z-Score gegen rollendes 30-Tage-Baseline

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/compute/compute_hrv_anomaly.py`

**Evidence tier:** research (peer-reviewed literature basis, but no formal clinical validation study with endpoints)

## Purpose

Computes daily Z-scores for RMSSD and DFA alpha1 from ppi_hrv_advanced against a rolling 30-day baseline window.  Sets hrv_anomaly_flag when |z| > Z_THRESHOLD for at least one metric.

## Relevance

Enables heart rate variability analysis, essential for autonomic health monitoring

## Method

Daily aggregate: AVG(rmssd_ms) and AVG(dfa_alpha1) per day from ppi_hrv_advanced (5-minute windows, already artefact-corrected via kubios_artifact_correction). Baseline: 30-day window *before* target date (target date excluded). Z-score: (value − baseline_mean) / baseline_std. Requires at least MIN_BASELINE_N non-null values in window; else no entry. flag=1 if |z_rmssd| > Z_THRESHOLD OR |z_dfa1| > Z_THRESHOLD. If only one metric is available, Z-score is computed for that metric only.

## Data flow

- **Reads:** `ppi_hrv_advanced`
- **Writes:**

  ```
  measurements  (metrics: hrv_anomaly_rmssd_z, hrv_anomaly_dfa1_z,
  hrv_anomaly_flag)
  ```

## Limitations

– No clinical validation; Z=2 corresponds to 5% level under normality, which does not always hold for HRV. – Short recording gaps (travel, device break) can deflate baseline std, causing false positives. – dfa_alpha1 is from ppi_hrv_advanced (artefact-corrected); for same-day anomaly signals, ppi_dfa.alpha1 (5-min, raw RR) may be more sensitive. – Day-level granularity only.  Intraday anomalies are not detected.

## References

- [UNVERIFIZIERT] "Roeschmann et al. 2020, Front Physiol, doi:10.3389/fphys.2020.573483" — DOI löst nicht auf (weder Crossref noch doi.org), kein passendes Paper trotz intensiver Suche (Crossref-Volltextsuche, Frontiers-Journal-Direktsuche, Websuche) gefunden. Möglicherweise fehlerhaft erinnertes/fabriziertes Zitat — vor Verwendung/Vertrauen manuell prüfen.
- Flatt & Esco 2016, Int J Sports Physiol Perform (DOI ausstehend) (coefficient-of-variation for HRV change detection — informs MIN_BASELINE_N;
- die zuvor hier stehende DOI 10.1123/ijspp.2015-0640 löst nicht auf (404) und wurde entfernt statt durch eine ungeprüfte Vermutung ersetzt)

## Usage

```bash
python compute_hrv_anomaly.py
python compute_hrv_anomaly.py --help
python compute_hrv_anomaly.py --from 2024-01-01 --to 2024-12-31
```
