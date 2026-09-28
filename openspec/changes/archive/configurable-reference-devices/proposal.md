## Why

Which device/source counts as the "reference scale" or calibration anchor for
a physiological metric is currently hardcoded in Python source in two places
that don't talk to each other: `compute_pem.py`'s HRV source-priority
hierarchy (Polar wrist devices first, with a hardcoded `OURA_LOOP_BIAS_MS`
correction only for the configured Oura device) and
`compute_calibrate_sources.py`'s `ANCHORS` list (per-metric calibration
anchor, e.g. HR/HRV: `polar_connect`, SpO2: `beurer_hmp`). An installation
without a Polar device — or with a different device combination entirely —
gets a scale/anchor choice that was never validated for its own setup, and
changing it requires editing source instead of config, which this project's
own conventions treat as the wrong place for anything installation-specific.

## What Changes

- Add a config-driven reference-device mechanism: users can name, per
  metric, which source/device is the reference scale that other sources are
  measured or corrected against.
- `compute_calibrate_sources.py`'s `ANCHORS` list is sourced from this config
  (with the current hardcoded anchors kept as the fallback default, so
  existing installations behave identically until they opt in).
- `compute_pem.py`'s HRV source-priority hierarchy reads the same config for
  which source is the reference and which gets a bias correction, instead of
  the hardcoded Polar-first / Oura-only-correction logic.
- Explicitly out of scope for this change unless scoping below says
  otherwise: replacing or duplicating `compute_canonical.py`'s existing
  `source_confidence`-table-driven mechanism — that already solves "which
  source wins per day for the canonical value" empirically; this change is
  about "which source defines the reference scale that others get judged or
  corrected against," a related but distinct concept the two calibration
  scripts currently each hardcode separately.
- **BREAKING**: none — every hardcoded value becomes the default, so an
  installation with no reference-device config set keeps today's behavior
  exactly.

## Capabilities

### New Capabilities
- `reference-device-configuration`: defines a config schema section naming,
  per metric, which source/device an installation treats as the reference
  scale (i.e. the calibration anchor, and — for metrics like HRV where a
  correction is applied to bring another device onto the same scale — the
  scale that correction targets), the fallback behavior when unset, and
  which compute scripts must read from it instead of hardcoding a choice.

### Modified Capabilities
(none — no existing spec currently documents calibration anchors or HRV
source priority as a requirement)

## Impact

- `scripts/compute/compute_calibrate_sources.py` — `ANCHORS` sourced from
  config, falling back to current hardcoded values.
- `scripts/compute/compute_pem.py` — HRV source-priority/bias-correction
  logic reads the same config instead of the hardcoded Polar/Oura choice.
- `scripts/health_config.py` — new `Config` property/schema section and
  validation for the reference-device config block.
- `templates/health_config.example.json` — documented example of the new
  section.
- `scripts/compute/compute_canonical.py` — read-only interaction check: no
  code change expected, but the design must state explicitly how the new
  mechanism relates to the existing `source_confidence` table so a future
  reader doesn't have to reverse-engineer it.
- Docs: docstrings of both compute scripts (`@method`, `@limits`) need to
  describe the new config-driven behavior; `docs/generated/*` regenerated
  accordingly.
