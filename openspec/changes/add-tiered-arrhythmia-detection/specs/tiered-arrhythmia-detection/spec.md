## ADDED Requirements

### Requirement: Universal rhythm-irregularity score on all devices
Every `ppi_windows` row SHALL receive an `irregularity_score` and
`irregularity_class` (`normal|mildly_irregular|moderately_irregular|highly_irregular`)
derived from RMSSD/SDNN/CVRR/sample entropy/Poincaré SD1-SD2, regardless
of the originating device's sensor type.

#### Scenario: A window is computed for a PPG-only source
- **WHEN** `compute_arrhythmia.py` processes a `ppi_windows` row whose
  source device has `sensor_type` `optical_wrist` or `optical_wrist_gps`
- **THEN** `irregularity_score`/`irregularity_class` are still computed
  and stored, since these features only need beat-to-beat timing, not
  waveform morphology

#### Scenario: Class boundaries are calibrated, not hardcoded
- **WHEN** the irregularity-class boundaries are determined
- **THEN** they are derived from this project's own historical
  `ppi_windows` distribution (percentile-based), not a fixed population
  cutoff copied from a paper studying a different cohort

### Requirement: AFib screening declares its signal type
Every `arrhythmie_episoden` row SHALL carry a `signal_type` field
(`chest_strap|raw_ecg|optical_wrist|optical_wrist_gps`) reflecting the
originating device's actual signal capability.

#### Scenario: Episode detected from chest-strap RR data
- **WHEN** an AFib-pattern episode is detected from a `sensor_type ==
  'chest_strap'` source
- **THEN** `signal_type` is stored as `chest_strap`

#### Scenario: Episode detected from optical/PPG data
- **WHEN** an AFib-pattern episode is detected from a `sensor_type ==
  'optical_wrist'` or `'optical_wrist_gps'` source
- **THEN** `signal_type` is stored accordingly, and every report
  surfacing the episode (`analyse_arrhythmia.py`, `analyse_afib_burden.py`)
  displays it alongside the episode, never presenting it with the same
  implied confidence as a chest-strap-sourced episode

### Requirement: Ectopic-beat screening is gated to beat-to-beat-precision sources
The ectopic-beat/bigeminy/trigeminy detection tier SHALL only run on
`sensor_type == 'chest_strap'` sources or raw-ECG imports (Apple Watch
snapshot ECG, ECG Logger) — never on PPG-only (`optical_wrist`/
`optical_wrist_gps`) sources.

#### Scenario: Ectopy detection requested for a PPG-only source
- **WHEN** the ectopic-beat detector is invoked against data from a
  `sensor_type == 'optical_wrist'` (or `optical_wrist_gps`) source
- **THEN** it returns no result (skips entirely) rather than a
  low-confidence result — the gate is a hard capability boundary, not a
  confidence downgrade

#### Scenario: Ectopy detection on chest-strap data
- **WHEN** beat-to-beat `ppi_raw` data from a `sensor_type ==
  'chest_strap'` source shows a short-RR-interval beat followed by a
  compensatory pause
- **THEN** the episode is flagged in `ectopy_episoden` with
  `pattern_type` and the originating `signal_type`

#### Scenario: Alternating short/long RR sequence
- **WHEN** a chest-strap or raw-ECG source shows a regular alternating
  short/long RR pattern of sufficient length
- **THEN** it is classified as `bigeminy_suspected` or
  `trigeminy_suspected` as appropriate, not generic `possible_ectopy`

### Requirement: Persistent-irregularity flag is non-diagnostic
When AFib-tier or ectopy-tier episodes recur beyond a configured
threshold within a rolling window, a `persistent_irregular_rhythm` flag
SHALL be set with a fixed, non-diagnostic message recommending medical
evaluation — never naming a specific suspected condition.

#### Scenario: Threshold exceeded
- **WHEN** the number of AFib-or-ectopy-tier episodes within the
  configured rolling window meets or exceeds the configured threshold
- **THEN** `persistent_irregular_rhythm` is set and the fixed message
  ("persistent irregular rhythm detected, medical evaluation
  recommended" / localized equivalent) is shown — not a named diagnosis
  ("possible AFib", "possible PVCs", etc.)

#### Scenario: Threshold not met
- **WHEN** episode frequency stays below the configured threshold
- **THEN** no clinical-review flag is set, and no other part of the
  report implies escalation

### Requirement: Device capability gating uses the existing device registry
Availability of each detection tier SHALL be derived from
`device_registry.sensor_type` via the same registry-driven mechanism
used elsewhere in the project (`cross-cutting-conventions` spec), not a
per-script hardcoded device/brand list.

#### Scenario: New chest-strap device added to device_registry
- **WHEN** a Kyoro user adds a new device to `device_registry` with
  `sensor_type: chest_strap`
- **THEN** the ectopic-beat tier becomes available for that device's
  data automatically, without any code change

#### Scenario: Sensor type missing from device_registry
- **WHEN** a source's device has no `sensor_type` recorded in
  `device_registry`
- **THEN** the ectopic-beat tier does not run for that source (fails
  closed, not open) until the registry entry is completed
