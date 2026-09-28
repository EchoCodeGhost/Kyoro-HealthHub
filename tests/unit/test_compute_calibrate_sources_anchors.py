# SPDX-License-Identifier: GPL-3.0-or-later
"""
Unit test for compute/compute_calibrate_sources.py::_resolve_metric_anchors.

Part of the configurable-reference-devices change: the primary anchor per
metric is now resolvable from clinical.reference_devices, falling back to
the hardcoded ANCHORS default when unconfigured or when the configured
device has no source_apps recorded in device_registry.
"""

import sys
from pathlib import Path

repo_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(repo_root / "scripts"))
sys.path.insert(0, str(repo_root / "scripts" / "compute"))

import compute_calibrate_sources as ccs


class FakeCfg:
    def __init__(self, reference_devices=None, device_source_apps_map=None):
        self._reference_devices = reference_devices or {}
        self._device_source_apps_map = device_source_apps_map or {}

    def resolve_reference_device(self, metric, default):
        return self._reference_devices.get(metric) or default

    def device_source_apps(self, device_id):
        if device_id not in self._device_source_apps_map:
            raise ValueError(f"unknown device_id={device_id!r}")
        return self._device_source_apps_map[device_id]


HARDCODED_HR_ANCHORS = [
    ("polar_connect", ["polar_connect"]),
    ("hilo", ["hilo_pdf", "hilo_app_screenshot"]),
    ("beurer_po60", ["beurer_hmp"]),
]


def test_unconfigured_metric_keeps_hardcoded_anchors(monkeypatch):
    monkeypatch.setattr(ccs, "_cfg", FakeCfg())
    result = ccs._resolve_metric_anchors("heart_rate", HARDCODED_HR_ANCHORS)
    assert result == HARDCODED_HR_ANCHORS


def test_configured_device_replaces_primary_anchor_only(monkeypatch):
    monkeypatch.setattr(ccs, "_cfg", FakeCfg(
        reference_devices={"hr": "DEV-configured"},
        device_source_apps_map={"DEV-configured": ["some_source_app"]},
    ))
    result = ccs._resolve_metric_anchors("heart_rate", HARDCODED_HR_ANCHORS)
    assert result[0] == ("DEV-configured", ["some_source_app"])
    # secondary anchors (hilo, beurer_po60) are untouched
    assert result[1:] == HARDCODED_HR_ANCHORS[1:]


def test_configured_device_without_source_apps_falls_back(monkeypatch, capsys):
    """The device exists in device_registry (so device_source_apps() doesn't
    raise) but has no source_apps field recorded yet -> None, not an error."""
    class NoSourceAppsCfg(FakeCfg):
        def device_source_apps(self, device_id):
            return None

    monkeypatch.setattr(ccs, "_cfg", NoSourceAppsCfg(
        reference_devices={"hr": "DEV-no-source-apps"}))

    result = ccs._resolve_metric_anchors("heart_rate", HARDCODED_HR_ANCHORS)

    assert result == HARDCODED_HR_ANCHORS
    assert "DEV-no-source-apps" in capsys.readouterr().out


def test_metric_not_in_scope_is_unaffected(monkeypatch):
    """'steps' has an ANCHORS entry but is deliberately out of scope for
    reference_devices (see design.md) — must never be resolved."""
    monkeypatch.setattr(ccs, "_cfg", FakeCfg(reference_devices={"steps": "DEV-x"}))
    steps_anchors = [("oura_app", ["oura_app"])]
    result = ccs._resolve_metric_anchors("steps", steps_anchors)
    assert result == steps_anchors


def test_hrv_uses_hrv_config_key_not_metric_name(monkeypatch):
    """ANCHORS keys the metric as 'hrv_rmssd', but the config key is the
    shorter 'hrv' — the mapping must bridge that, not require exact-name match."""
    monkeypatch.setattr(ccs, "_cfg", FakeCfg(
        reference_devices={"hrv": "DEV-hrv-ref"},
        device_source_apps_map={"DEV-hrv-ref": ["some_hrv_source"]},
    ))
    hrv_anchors = [("polar_connect", ["polar_connect"])]
    result = ccs._resolve_metric_anchors("hrv_rmssd", hrv_anchors)
    assert result[0] == ("DEV-hrv-ref", ["some_hrv_source"])
