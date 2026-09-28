## 1. Universal rhythm-irregularity tier (all devices)

- [ ] 1.1 Add `irregularity_score` (0.0-1.0, from normalised RMSSD/SDNN/CVRR/sample-entropy/Poincaré-SD1-SD2 blend) and `irregularity_class` (`normal|mildly_irregular|moderately_irregular|highly_irregular`) columns to `ppi_windows`
- [ ] 1.2 Implement the blend in a new `modules/rhythm_irregularity.py` (shared, reusable — not duplicated per compute script)
- [ ] 1.3 Class-boundary calibration against this project's own historical `ppi_windows` distribution (percentile-based, matching the pattern in `compute_pem.py`'s `_rolling_percentile_thresholds`), not a hardcoded population cutoff
- [ ] 1.4 Backfill: compute for existing `ppi_windows` rows via a migration script

## 2. AFib screening: signal-type labelling

- [ ] 2.1 Add `signal_type` column to `arrhythmie_episoden` (`chest_strap|raw_ecg|optical_wrist|optical_wrist_gps`), derived from `device_registry.sensor_type` at detection time
- [ ] 2.2 `analyse_arrhythmia.py` / `analyse_afib_burden.py`: display signal_type alongside every episode, so PPG-sourced and chest-strap-sourced episodes are never presented with equal implied confidence
- [ ] 2.3 `@limits` update on both analysis scripts documenting the confidence difference explicitly

## 3. Ectopic-beat screening tier (chest-strap / raw-ECG sources only)

- [ ] 3.1 New `modules/ectopy_detection.py`: short-RR-then-compensatory-pause pattern detection from beat-to-beat `ppi_raw`
- [ ] 3.2 Bigeminy/trigeminy pattern detection (regular alternating short/long RR sequences of length >= N)
- [ ] 3.3 Device-capability gate: function refuses to run (returns `None`/skips, not a low-confidence result) when `sensor_type` isn't `chest_strap` or the source isn't a raw-ECG import — enforce in one place, not per caller
- [ ] 3.4 New table `ectopy_episoden` (mirrors `arrhythmie_episoden` shape: episode_start/end, pattern_type, n_beats, signal_type, person, confidence)
- [ ] 3.5 Wire into `compute_arrhythmia.py`'s existing per-window pipeline rather than a fully separate compute script, since it reads the same `ppi_raw`/`ppi_windows` inputs
- [ ] 3.6 New `analyse_ectopy.py` (or extend `analyse_arrhythmia.py` with a second section) — pattern, frequency, time-of-day, trigger correlation, matching the existing AFib analysis script's structure

## 4. Non-diagnostic clinical-review flag

- [ ] 4.1 Config thresholds in `clinical.pem` (or a new `clinical.arrhythmia` section) — e.g. N AFib-or-ectopy-tier episodes within a rolling window
- [ ] 4.2 Fixed, non-alarmist, non-diagnostic message text (DE+EN via `t()`) — reviewed against `docs/ETHICS.md`'s non-diagnosis boundary before merge
- [ ] 4.3 Surfaced in `analyse_arrhythmia.py`'s report output and (optionally) `analyse_overview.py`'s summary

## 5. Documentation

- [ ] 5.1 `@refs`/`@method`/`@limits` updates on `compute_arrhythmia.py`, `analyse_arrhythmia.py` reflecting the new tiers
- [ ] 5.2 New `@refs` entries: Tateno & Glass 2001 (already present), a citation for the ectopic-beat RR-pattern method (needs its own Crossref-verified source before merge — do not guess a DOI, follow this session's established citation-verification discipline)
- [ ] 5.3 `docs/generated/` regeneration (`tools/gen_docs.py`)

## 6. Review

- [ ] 6.1 Privacy/compliance gates (`check_source_privacy.py`, `check_compliance.py`, `qa_check.py`)
- [ ] 6.2 Cross-check against `cross-cutting-conventions` spec (device-agnostic fallback chain, no hardcoded IANA timezone, bilingual output)
- [ ] 6.3 Confirm no tier ever implies a diagnosis, per `docs/ETHICS.md`
