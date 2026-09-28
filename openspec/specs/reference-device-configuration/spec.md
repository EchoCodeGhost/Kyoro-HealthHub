# reference-device-configuration Specification

## Purpose
Which device or source counts as the "reference scale" or calibration
anchor for a physiological metric used to be hardcoded in Python source in
two places that never talked to each other: `compute_pem.py`'s HRV
source-priority hierarchy and `compute_calibrate_sources.py`'s `ANCHORS`
list. An installation without the project's default device combination
got a scale/anchor choice that was never validated for its own setup, and
changing it meant editing source instead of config. This capability lets
an installation name, per metric, which device it treats as the reference
scale — with every prior hardcoded value preserved as the fallback default,
so an installation with no reference-device config keeps today's behavior
exactly.
## Requirements
### Requirement: Per-metric reference-device configuration
The system SHALL provide a config section (read via `health_config.py`) that
lets an installation name, per metric, which source or device it treats as
the reference scale — the calibration anchor other sources are compared
against, and, for metrics where a correction is applied to align a device
onto that scale (e.g. HRV), the scale that correction targets.

#### Scenario: Installation configures its own HRV reference device
- **WHEN** an installation sets a reference device for the `hrv` metric in
  its config to a device it owns that is not the project's hardcoded
  default
- **THEN** `compute_calibrate_sources.py` and `compute_pem.py` both treat
  that configured device as the reference for HRV, without any source
  change

#### Scenario: Config names a device not present in device_registry
- **WHEN** a configured reference-device value does not match any
  `device_id` in `device_registry`
- **THEN** the affected compute script exits with a clear error message
  identifying the invalid metric/device pairing, rather than silently
  falling back or producing scores calibrated against nothing

### Requirement: Hardcoded defaults remain the fallback
When no reference device is configured for a given metric, the system
SHALL fall back to the project's current hardcoded choice for that metric
(e.g. `polar_connect` for HR/HRV, `beurer_hmp` for SpO2), so an
installation with no reference-device config behaves identically to before
this change.

#### Scenario: Installation has no reference-device config at all
- **WHEN** `health_config.json` has no reference-device section
- **THEN** `compute_calibrate_sources.py`'s anchors and
  `compute_pem.py`'s HRV source priority/bias target are exactly the
  values hardcoded before this change

#### Scenario: Config sets a reference for one metric but not another
- **WHEN** an installation configures a reference device for `hrv` but not
  for `spo2`
- **THEN** the SpO2 anchor still falls back to the hardcoded default while
  the HRV reference uses the configured value

### Requirement: compute_calibrate_sources.py anchors are config-driven
`compute_calibrate_sources.py`'s per-metric calibration anchor(s) SHALL be
sourced from the reference-device config (falling back per the previous
requirement) instead of the hardcoded `ANCHORS` list being the sole source
of truth.

#### Scenario: Calibration run picks up a configured anchor
- **WHEN** `compute_calibrate_sources.py` runs for a metric that has a
  configured reference device
- **THEN** the Pearson-r / Bland-Altman comparison uses the configured
  device as the anchor, and the hardcoded default for that metric is not
  used

### Requirement: device_registry source_apps field for anchor resolution
`device_registry` entries SHALL support an optional `source_apps` field
(list of strings) naming every `source_app` value that device's data can
appear under in `measurements`/`sessions` (multiple import paths for the
same physical device, e.g. a PDF import and an app-screenshot import of
the same reading, yield distinct `source_app` values that still refer to
one device). `compute_calibrate_sources.py` SHALL resolve a configured
reference `device_id` to its anchor `source_app` list via this field.

#### Scenario: Configured device has source_apps recorded
- **WHEN** a `device_registry` entry used as a configured reference device
  has a non-empty `source_apps` list
- **THEN** `compute_calibrate_sources.py` uses that full list as the
  anchor's source_app synonyms, matching how the existing hardcoded
  multi-source_app anchors (e.g. the Hilo PDF/app-screenshot bundle) are
  defined today

#### Scenario: Configured device has no source_apps recorded yet
- **WHEN** a configured reference `device_id` exists in `device_registry`
  but has no `source_apps` field set
- **THEN** `compute_calibrate_sources.py` cannot resolve an anchor from it
  and falls back to that metric's hardcoded `ANCHORS` default (per the
  "Hardcoded defaults remain the fallback" requirement), while logging
  that the configured reference device is missing `source_apps` so the
  gap is visible rather than silently ignored

### Requirement: compute_pem.py HRV reference is config-driven
`compute_pem.py`'s HRV source-priority hierarchy SHALL determine which
source is the reference scale and which source(s) receive a bias
correction toward it from the reference-device config (falling back per
the "hardcoded defaults" requirement), instead of always treating
`polar_nightly_hrv` as the reference and only ever bias-correcting the
configured Oura device.

#### Scenario: Non-Polar installation configures a different HRV reference
- **WHEN** an installation with no Polar device configures its Oura device
  (or another device) as the HRV reference
- **THEN** `compute_pem.py` treats that device's HRV as uncorrected/
  reference-scale, and applies bias correction (if a calibration bias value
  exists for the pairing) to other devices instead of assuming Polar is the
  scale

#### Scenario: Bias correction has no value to apply
- **WHEN** a device is configured to receive bias correction toward the
  reference but no calibration bias has been computed/configured for that
  device pairing
- **THEN** that device's readings are used uncorrected rather than the
  computation failing, consistent with the existing behavior for
  unconfigured/unfiltered devices

### Requirement: Distinction from source_confidence-based selection
The reference-device configuration SHALL be documented (in the config
schema and in both compute scripts' docstrings) as a distinct concept from
`compute_canonical.py`'s existing `source_confidence`-table-driven source
selection: reference-device config controls what a metric is calibrated or
corrected *against*, while `source_confidence` controls which source's
*value* is chosen as the canonical daily value once confidence scores are
known. This change SHALL NOT alter `compute_canonical.py`'s existing
selection mechanism.

#### Scenario: Contributor reads both mechanisms' docstrings
- **WHEN** a contributor reads `compute_canonical.py`'s and
  `compute_calibrate_sources.py`'s docstrings after this change
- **THEN** each docstring states which of the two concepts (canonical
  source selection vs. calibration reference) it implements, so the two
  are not confused as duplicates of each other

