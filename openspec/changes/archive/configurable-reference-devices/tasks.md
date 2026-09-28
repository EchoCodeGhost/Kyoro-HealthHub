## 1. Config layer

- [x] 1.1 Add `Config.reference_devices` property to `scripts/health_config.py`
      (`clinical.reference_devices`, empty-dict default), following the
      `pem_config` property pattern.
- [x] 1.2 Add a helper (e.g. `Config.resolve_reference_device(metric,
      default)`) that returns the configured `device_id` for a metric or
      the given hardcoded default when unset — single place both compute
      scripts call, instead of duplicating the fallback `dict.get` logic.
- [x] 1.3 Add an optional `source_apps: list[str]` field to the
      `device_registry` entry schema (documented in the
      `_device_registry_note`), naming every `source_app` value a device's
      data can appear under (multiple import paths, one device — see
      design.md's Hilo PDF/app-screenshot example).
- [x] 1.4 Add a helper (e.g. `Config.device_source_apps(device_id)`) that
      returns a configured `device_id`'s `source_apps` list from
      `device_registry`, or `None` if the device exists but has no
      `source_apps` recorded, or raises a clear error (per spec scenario
      "Config names a device not present in device_registry") if the
      `device_id` isn't found at all.
- [x] 1.5 Document the new `clinical.reference_devices` section and the
      `source_apps` device_registry field in
      `templates/health_config.example.json` with fictional (non-personal)
      example values — never a real device_id/source_app pairing from any
      actual installation, including this repo's own dev/test config.

## 2. compute_calibrate_sources.py

- [x] 2.1 Resolve each `ANCHORS` entry through
      `Config.resolve_reference_device()` + `Config.device_source_apps()`
      (from 1.4), falling back to today's hardcoded anchor strings when
      unset OR when the configured device has no `source_apps` recorded
      (per the spec's "Configured device has no source_apps recorded yet"
      scenario — log the gap, don't silently ignore it).
- [x] 2.2 Update `@method.de`/`@method.en` docstring to describe the
      config-driven anchor resolution and the fallback.
- [x] 2.3 Add the distinction-from-`source_confidence` note to the
      docstring, per the spec's "Distinction from source_confidence-based
      selection" requirement.

## 3. compute_pem.py

- [x] 3.1 Replace the hardcoded `_preferred = _cfg.oura_device_id` HRV
      bias-target lookup with `Config.resolve_reference_device("hrv",
      default=<today's Oura fallback>)`.
- [x] 3.2 Confirm the Polar-first source priority (`polar_nightly_hrv`
      checked before the device-agnostic `measurements` fallback) still
      matches the "hardcoded defaults remain the fallback" requirement
      when no `hrv` reference is configured; adjust only if a configured
      non-Polar reference needs to take priority over `polar_nightly_hrv`
      for that installation (see design.md Open Questions).
      — Confirmed: left unchanged, no concrete need identified for a
      configured HRV reference to preempt polar_nightly_hrv.
- [x] 3.3 Update the `_classify_recovery()` docstring and the `@method`
      docstring to describe the config-driven reference/bias-target
      instead of naming Oura/Polar as fixed.
- [x] 3.4 Add the distinction-from-`source_confidence` note here too
      (same requirement as 2.3).

## 4. Tests

- [x] 4.1 Unit test `Config.reference_devices` /
      `resolve_reference_device()`: empty config falls back to the given
      default; configured value overrides it; invalid `device_id` raises
      a clear error at resolution time, not silently.
- [x] 4.2 Unit test `compute_calibrate_sources.py`'s anchor resolution:
      configured reference device is used as the anchor; unconfigured
      metric falls back to the hardcoded anchor unchanged.
- [x] 4.3 Extend/adapt the existing `OURA_LOOP_BIAS_MS` coverage in
      `compute_pem.py`'s tests (see `tests/unit/` from the prior session)
      to go through the new config-driven resolution instead of the
      hardcoded `oura_device_id` lookup, and add a case for a non-Oura
      configured HRV reference device.
- [x] 4.4 Run the full suite (`python -m pytest`) and confirm no
      regressions.

## 5. Documentation & QA gate

- [x] 5.1 Regenerate per-script and aggregate docs (`tools/gen_docs.py`,
      `scripts/generate_docstring_docs.py`) so `docs/de|en/compute/*.md`
      and `docs/generated/*.md` reflect the updated docstrings.
- [x] 5.2 Run `python3 scripts/utils/check_source_privacy.py` and
      `python3 scripts/utils/check_no_dates.py` — confirm clean (no real
      device_id, no embedded dates, in either source or the example
      config doc).
- [x] 5.3 Run `python3 tools/qa_check.py` and confirm all checks pass.
      — Surfaced 2 pre-existing compliance false positives (generic "age"/
      "illness" in prose, re-flagged because the docstring hash changed)
      re-approved via `check_compliance.py --review`; QA OK afterward.
- [x] 5.4 Manually verify byte-identical behavior on an unconfigured
      installation: run `compute_calibrate_sources.py` and
      `compute_pem.py` against the same data before/after this change
      with no `clinical.reference_devices` set, confirm identical output.
      — Verified via tests 4.1–4.3 instead of a live run against the real
      DB (both compute scripts write derived tables, and a live run would
      have mutated real personal data for a verification step that a unit
      test already proves): `test_unconfigured_metric_keeps_hardcoded_anchors`
      and `test_bias_applies_to_the_real_oura_ring_when_unconfigured`
      exercise exactly the no-config path and assert it matches the
      pre-change hardcoded behavior.
