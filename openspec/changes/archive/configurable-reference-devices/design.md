## Context

Two compute scripts each hardcode their own answer to "which source is
ground truth for this metric":

- `compute_calibrate_sources.py`'s `ANCHORS` list keys by metric to a
  `source_app` string (e.g. `heart_rate`/`hrv_rmssd` → `polar_connect`,
  `spo2` → `beurer_hmp`; HR additionally gets a second anchor,
  Hilo/Aktiia). Anchors here are **source-app granularity** — "any Polar
  wrist device," not one physical device — because the calibration compares
  daily aggregates per `(metric, source_app)`, not per `device_id`.
- `compute_pem.py`'s HRV loading hardcodes `polar_nightly_hrv` as the
  reference scale and bias-corrects only the specific device matching
  `cfg.oura_device_id` — **device-id granularity**, because the bias
  constant (`OURA_LOOP_BIAS_MS`) was calibrated against one physical Oura
  ring, and `device_registry` already has one entry per physical device.

`compute_canonical.py` already reads a *different* thing — per-day,
per-source confidence, from the `source_confidence` table — to decide which
source's *value* becomes the canonical daily value. That mechanism is not
touched by this change; see the "Distinction from source_confidence-based
selection" requirement in the spec.

## Goals / Non-Goals

**Goals:**
- One config-driven way to name a reference device/source per metric that
  both `compute_calibrate_sources.py` and `compute_pem.py` read.
- Zero behavior change for installations that don't set it.
- Reconcile the source-app-granularity need (calibrate_sources) with the
  device-id-granularity need (compute_pem's bias target) without two
  separate config shapes.

**Non-Goals:**
- Replacing or touching `compute_canonical.py`'s `source_confidence`-based
  canonical-value selection.
- A UI/CLI wizard for setting this — it's a config file edit, like every
  other `clinical.*` setting.
- Retroactively recalibrating bias constants for a newly configured
  reference device — if an installation switches its HRV reference to a
  device with no existing bias calibration, it gets uncorrected values
  (per the spec's "Bias correction has no value to apply" scenario), same
  as today's behavior for any non-Oura, non-preferred device.

## Decisions

**Config value is `device_id`-keyed, not `source_app`-keyed.**
`clinical.reference_devices` maps metric name → `device_id` (e.g.
`{"hrv": "DEV-<hex>", "hr": "DEV-<hex>", "spo2": "DEV-<hex>"}`, each
`device_id` an opaque pseudonym already assigned to that device in
`device_registry` — never a real device model/serial, per the
identifier-pseudonymization spec), matching `device_registry`'s
granularity. `compute_pem.py` uses the `device_id` directly (same shape it
needs today for `oura_device_id`).

**`device_registry` gains an optional `source_apps: list[str]` field per
entry, used to resolve a configured `device_id` to the `source_app`
value(s) `compute_calibrate_sources.py` needs.** Discovered during
implementation: `device_registry` today has no field that maps a device to
its `source_app` string(s), and the mapping isn't 1:1 anyway —
`ANCHORS`'s existing Hilo entry bundles two distinct `source_app` values
(`hilo_pdf`, `hilo_app_screenshot`) as *one* logical anchor because they're
the same physical device reached via two different import paths, and
per-path they'd each fail the 20-day overlap threshold alone. A device_id
→ single-source_app resolver can't represent that bundle. `source_apps` is
a list for exactly this reason — one device, one config entry, all its
import-path source_app values. Optional and additive: existing
`device_registry` entries without it are unaffected, and
`compute_calibrate_sources.py` cannot resolve a configured reference
device for a metric until its `source_apps` is also filled in (see the new
spec requirement) — falling back to the hardcoded `ANCHORS` default for
that metric in the meantime, per the existing "hardcoded defaults remain
the fallback" requirement, rather than guessing a mapping from `brand`.

**New `Config.reference_devices` property, same pattern as `pem_config`.**
```python
@property
def reference_devices(self) -> dict:
    """Per-metric calibration/reference device_id. Override via
    clinical.reference_devices. Empty dict -> every metric falls back to
    its hardcoded default anchor."""
    return self._cfg.get("clinical", {}).get("reference_devices", {})
```
Mirrors `pem_config`'s existing `clinical.<key>` nesting and empty-dict
default — no new top-level config section, no new patterns to learn.

**Hardcoded values become named default constants, not deleted.**
`ANCHORS`'s current hardcoded source_app strings and `compute_pem.py`'s
Polar-first/Oura-bias logic stay in source as the literal fallback,
consulted only when `cfg.reference_devices` has no entry for that metric.
This is what makes the change non-breaking: no config means byte-identical
behavior to before.

**Validation happens once, at the point each script resolves the config
value — not proactively at config load.** A configured `device_id` that
doesn't exist in `device_registry` is only a problem for the metric it was
set for, so `health_config.py` doesn't validate `reference_devices`
eagerly (it also doesn't validate `device_registry` entries against, say,
`oura_device_id`'s fallback today — consistent with existing config-loading
behavior of trusting the file and failing at first use). Each compute
script SHALL raise a clear error (per the spec's second scenario) when it
tries to resolve an invalid entry, not silently ignore it — silently
falling back would be worse than failing loudly, since a silently-ignored
typo in a reference-device id would look identical to "not configured" and
nobody would notice their calibration is running against the wrong device.

**Scope: HRV, HR, SpO2 — not blood pressure, for this change.**
The proposal flagged BP as an open scoping question. Looking at current
code: `ANCHORS` already has a real anchor for SpO2 (`beurer_hmp`) that this
change's mechanism can absorb at no extra design cost (same shape as HRV/HR).
Blood pressure has no equivalent today — Hilo/Aktiia appear only as a
*second* anchor for HR (a device with a pulse side-value), not as a BP
calibration anchor in their own right — so there's no existing hardcoding
to migrate for BP, and inventing a first BP reference-device concept from
scratch is a separate, unscoped piece of work. Deferred to a follow-up
change if/when BP calibration is actually built.

## Risks / Trade-offs

- **[Risk] A user sets a `reference_devices` entry to a device_id that's
  correct today but gets removed from `device_registry` later (device
  retired/sold).** → Mitigation: the "clear error, not silent fallback"
  decision above means this surfaces immediately as a compute-script error
  the next time it runs, not a silent data-quality regression.
- **[Risk] `device_registry`'s schema is read by many importers already
  (device disambiguation, sensor_type checks) — adding `source_apps` is
  additive/optional, but touches a widely-used config structure.** →
  Mitigation: the field is purely additive (no existing reader iterates
  unknown keys defensively-incorrectly; absence is the documented normal
  case for any device not used as a configured reference), and only
  `compute_calibrate_sources.py`'s new resolution path reads it.
- **[Risk] Two config mechanisms for "which source matters" (this one, and
  `source_confidence`) could get confused by future contributors.** →
  Mitigation: the spec's explicit "Distinction from source_confidence-based
  selection" requirement forces both scripts' docstrings to state which
  concept they implement.
- **[Trade-off] device_id granularity for `compute_calibrate_sources.py`
  means resolving through `device_registry` adds one indirection compared
  to today's direct `source_app` string match.** Accepted: the alternative
  (two separate config shapes, one per granularity) is more config surface
  for users to understand for a marginal simplicity gain in one script.

## Migration Plan

No DB migration — this is config schema (`health_config.py`) plus two
compute scripts reading it. Deploy as a normal code change:
1. Add `Config.reference_devices` property, the optional `source_apps`
   field to the `device_registry` schema, and document both in
   `templates/health_config.example.json`.
2. Update `compute_calibrate_sources.py` to resolve `ANCHORS` through it
   (fallback preserved, including when a configured device has no
   `source_apps` yet).
3. Update `compute_pem.py`'s HRV loading to resolve the reference/bias
   target through it (fallback preserved).
4. Update both scripts' docstrings (`@method`, `@limits`) per the spec's
   documentation requirement.
Rollback: revert the two script changes and the `Config` property; no data
was written anywhere, so there's nothing to roll back at the DB level.

## Open Questions

- Exact `device_id` to use for a metric with no natural single device
  (e.g. would a household with two Polar wrist devices ever want to name
  one specifically as the HRV reference, overriding the current
  "all Polar wrist devices are one undifferentiated scale" treatment)? Left
  for implementation-time judgment — the config shape supports it
  (`device_id`, not `source_app`), but `compute_pem.py`'s Polar-first
  branch doesn't currently need to change unless a concrete need shows up.
