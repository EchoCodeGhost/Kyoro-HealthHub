# Empirische Kalibrierung der source_confidence-Scores aus eigenen Overlap-Daten.

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/compute/compute_calibrate_sources.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Computes Pearson r per (metric, source) against a gold-standard anchor and blends it with the literature baseline score: empirical_score = 0.6 × literature + 0.4 × r. Result is stored in source_confidence.notes (JSON) and optionally updates the confidence value — only if ≥ MIN_OVERLAP_DAYS overlap days.

## Relevance

Enables calibration of data sources, essential for data quality

## Method

Daily aggregates (AVG) per source are compared with anchor aggregates on shared dates. Bland-Altman bias and Pearson r are computed. Minimum 20 shared days per source pair required. Each metric's primary anchor (heart_rate/hrv_rmssd/spo2) is configurable via clinical.reference_devices (a device_id that must have source_apps set in device_registry) — unconfigured, or without source_apps, falls back to the hardcoded ANCHORS default (_resolve_metric_anchors()). This is a different mechanism from compute_canonical.py's source_confidence table: reference_devices decides WHAT a metric is calibrated against (the anchor itself), source_confidence decides which source's VALUE wins as the daily canonical value once confidence scores are known — this change doesn't touch the latter.

## Data flow

- **Reads:** `measurements`, `source_confidence`, `clinical.reference_devices`, `(config)`
- **Writes:** `source_confidence (notes + optional confidence update)`

## Limitations

One or more anchors per metric (ANCHORS list). With multiple anchors, every non-anchor source is compared against each anchor separately (anchors are also compared against each other) — for source_confidence, only the result with the most overlap days per source is persisted, all others are reported only, not stored. HR/HRV: polar_connect. Steps: apple_health as proxy anchor (no medical gold standard). SpO2: Beurer PO60 (beurer_hmp, medical fingerclip pulse oximeter). HR additionally: Hilo/Aktiia (hilo_pdf/hilo_app_screenshot, CE medical wrist BP device with a pulse side-value) as a second anchor. < 20 overlap days (e.g. while a device is rarely worn) → skipped. IMPORTANT: "polar_connect" as an anchor is NOT automatically chest-strap quality — the source value is identical across every Polar wrist device and the H7/H10 chest strap (see import_polar.py). Whether a given comparison actually has ECG reference quality depends on which physical device was worn in that period (see device_registry, _is_ecg_reference() for --device-a/--device-b). Wrist-PPG sources like the Polar Loop are fundamentally not an ECG-equivalent source (see @refs).

## References

- Kinnunen H, Rantanen A, Kenttä T, Koskimäki H (2022). Accuracy assessment of Oura Ring nocturnal heart rate and heart rate variability in comparison with electrocardiography in time and frequency domains. J Med Internet Res.
- 2022;24(1):e27487. https://www.jmir.org/2022/1/e27487 — low bias for HR/RMSSD, good fit for nocturnal RMSSD specifically (weaker for SDNN/LF/HF). Validity of the Polar H10 sensor for heart rate variability analysis during
- resting state and incremental exercise (2022), PMC9459793, https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9459793/ — r=0.95/ICC=0.95 at rest, r>0.93/ICC>0.93 during incremental exercise, vs. ECG. Wrist-worn PPG devices generally: HRV literature aggregated across several validation studies reports RMSSD correlations of only r≈0.62-0.79 against clinical ECG in healthy adults, worse with movement/darker skin tones/older age; treat the exact r-range as an approximate literature summary, not a single-paper citation, until a specific source is pinned down.

## Usage

```bash
python3 compute_calibrate_sources.py              # Kalibrierung + Scores aktualisieren
python3 compute_calibrate_sources.py --dry-run    # Nur Report, keine DB-Schreibvorgänge
python3 compute_calibrate_sources.py --metric heart_rate
python3 compute_calibrate_sources.py --windowed --source-a polar_connect --source-b apple_watch --metric hrv_rmssd
```
