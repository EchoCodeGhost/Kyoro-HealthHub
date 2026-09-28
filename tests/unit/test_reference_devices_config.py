# SPDX-License-Identifier: GPL-3.0-or-later
"""
Unit test for health_config.Config.reference_devices /
resolve_reference_device() / device_source_apps().

Part of the configurable-reference-devices change: lets an installation
name, per metric, which device it treats as the calibration/reference
scale, instead of that choice being hardcoded in compute_calibrate_sources.py
(ANCHORS) and compute_pem.py.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

from health_config import Config


def _bare_config(cfg_dict, monkeypatch, device_registry=None):
    """A Config instance backed by an in-memory dict, bypassing the real
    config file and the local registry.json override so the test is
    isolated from whatever is actually configured on the machine running
    it."""
    cfg = Config.__new__(Config)
    cfg._cfg = cfg_dict
    if device_registry is not None:
        cfg._cfg["device_registry"] = device_registry
    monkeypatch.setattr(Config, "_registry", lambda self: {})
    return cfg


# ── reference_devices / resolve_reference_device ────────────────────────────

def test_reference_devices_empty_by_default(monkeypatch):
    cfg = _bare_config({}, monkeypatch)
    assert cfg.reference_devices == {}


def test_resolve_reference_device_falls_back_when_unset(monkeypatch):
    cfg = _bare_config({}, monkeypatch)
    assert cfg.resolve_reference_device("hrv", default="DEV-default") == "DEV-default"


def test_resolve_reference_device_uses_configured_value(monkeypatch):
    cfg = _bare_config(
        {"clinical": {"reference_devices": {"hrv": "DEV-configured"}}}, monkeypatch)
    assert cfg.resolve_reference_device("hrv", default="DEV-default") == "DEV-configured"


def test_resolve_reference_device_only_affects_configured_metric(monkeypatch):
    cfg = _bare_config(
        {"clinical": {"reference_devices": {"hrv": "DEV-configured"}}}, monkeypatch)
    assert cfg.resolve_reference_device("spo2", default="DEV-spo2-default") == "DEV-spo2-default"


# ── device_source_apps ───────────────────────────────────────────────────────

def test_device_source_apps_returns_configured_list(monkeypatch):
    cfg = _bare_config({}, monkeypatch, device_registry=[
        {"device_id": "DEV-h10", "brand": "Polar", "source_apps": ["polar_connect"]},
    ])
    assert cfg.device_source_apps("DEV-h10") == ["polar_connect"]


def test_device_source_apps_none_without_source_apps_field(monkeypatch):
    """A device_registry entry that exists but predates this feature (no
    source_apps recorded yet) must be distinguishable from 'not found'."""
    cfg = _bare_config({}, monkeypatch, device_registry=[
        {"device_id": "DEV-old", "brand": "Garmin"},
    ])
    assert cfg.device_source_apps("DEV-old") is None


def test_device_source_apps_raises_for_unknown_device(monkeypatch):
    cfg = _bare_config({}, monkeypatch, device_registry=[
        {"device_id": "DEV-h10", "brand": "Polar", "source_apps": ["polar_connect"]},
    ])
    import pytest
    with pytest.raises(ValueError, match="DEV-nonexistent"):
        cfg.device_source_apps("DEV-nonexistent")


def test_device_source_apps_bundles_multiple_import_paths(monkeypatch):
    """The Hilo case: one physical device, two different source_app values
    depending on import path — both must come back in the list."""
    cfg = _bare_config({}, monkeypatch, device_registry=[
        {"device_id": "DEV-hilo", "brand": "Hilo",
         "source_apps": ["hilo_pdf", "hilo_app_screenshot"]},
    ])
    assert cfg.device_source_apps("DEV-hilo") == ["hilo_pdf", "hilo_app_screenshot"]
