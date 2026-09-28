## Why

`compute_arrhythmia.py` and `analyse_arrhythmia.py` are named generically
("arrhythmia detection"), but the actual detection logic
(`detection_method` defaults to `tateno_glass`, with `dash2009` for
optical-wrist sources) only recognises the irregular-RR-interval pattern
characteristic of atrial fibrillation. No other rhythm disturbance
(ectopic beats/PACs/PVCs, bigeminy/trigeminy, SVT, atrial flutter, AV
block, sustained brady-/tachycardia) is distinguished — a chest-strap
user with frequent extrasystoles and a PPG-only user with an AFib
episode currently produce the same generic `arrhythmie_episoden` row
shape, with no signal of which condition (if any) is actually present.

This also creates a device-capability-mismatch risk: PPG-based wearables
(Polar Loop, optical Vantage V3) measure mechanical pulse waves, not
electrical activity, and cannot reliably support beat-to-beat morphology
analysis (ectopic-beat detection, bigeminy/trigeminy patterns) the way
chest-strap RR data or actual ECG waveforms (Apple Watch snapshot ECG,
ECG Logger) can. Presenting the same detection capability across all
device types would overstate what PPG can actually deliver.

## What Changes

- **New universal rhythm-irregularity tier** (all devices, all sensor
  types): a `normal | mildly_irregular | moderately_irregular |
  highly_irregular` classification from RMSSD/SDNN/CVRR/sample
  entropy/Poincaré SD1-SD2 on the existing 5-minute `ppi_windows`
  aggregates — informational only, replaces nothing, available even on
  PPG-only sources.
- **AFib screening tier** (existing `tateno_glass`/`dash2009` logic,
  unchanged detection method) — now explicitly labelled with a
  `signal_type` reflecting the source's `device_registry.sensor_type`
  (`chest_strap` vs `optical_wrist`/`optical_wrist_gps`), so downstream
  reports never imply chest-strap-grade confidence for a PPG source.
- **New ectopic-beat screening tier** (`possible_ectopy` /
  `frequent_ectopy_suspected` / `bigeminy_suspected` /
  `trigeminy_suspected`): RR short-interval-then-compensatory-pause
  pattern detection on beat-to-beat data. **Gated to
  `sensor_type == 'chest_strap'` sources and raw-ECG sources
  (Apple Watch snapshot ECG, ECG Logger) only** — never runs on
  PPG-only data, per the device-capability-mismatch concern above.
- **New non-diagnostic clinical-review flag**: when the AFib or ectopy
  tier fires repeatedly over a configurable window, a
  `persistent_irregular_rhythm` flag is set alongside a fixed,
  non-alarmist note recommending medical evaluation — never phrased as
  a diagnosis (matches the project's existing ethics/DICOM-style
  non-diagnostic disclaimers used elsewhere).
- **No ML/CNN model in this phase** — classical RR-interval/Poincaré
  feature detection only, consistent with how every other compute
  script in this project works (published closed-form methods with a
  cited source, not a trained model with an opaque decision boundary).
  See `design.md` for why a PhysioNet/CinC-Challenge-style ML classifier
  is deferred rather than adopted now.
- **No new hardware or data source required** — everything above works
  from data already imported today (`ppi_raw`, `ppi_windows`, existing
  ECG sources).

## Capabilities

### New Capabilities
- `tiered-arrhythmia-detection`: multi-tier rhythm-abnormality
  classification (universal irregularity score → AFib screening →
  ectopic-beat screening → non-diagnostic clinical-review flag), with
  each tier's availability gated by the originating device's actual
  signal capability (PPG vs chest-strap RR vs raw ECG) so no tier
  implies a confidence level the source device cannot support.

### Modified Capabilities
- `compute_arrhythmia.py`'s existing AFib-only output gains an explicit
  `signal_type` field; no change to its existing detection method or
  stored episode shape otherwise.
