# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Tests for location privacy configuration loading.

@tier        unit
@purpose.de  Testet das Laden der location_privacy-Konfiguration
@purpose.en  Tests loading of location_privacy configuration
@method.de   Mockt die Konfigurationsdatei und prüft die Rückgabewerte
@method.en   Mocks the configuration file and checks return values
@reads       ~/.config/kyoro/location_privacy.json (mocked)
@writes      (nothing)
@limits.de   Nutzt pytest-mock für temporäre Dateien
@limits.en   Uses pytest-mock for temporary files
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))


def test_location_privacy_missing_file_returns_empty_dict(tmp_path, monkeypatch):
    """When location_privacy.json does not exist, Config.location_privacy returns {}."""
    from health_config import Config
    
    # Create a fake config dir without location_privacy.json
    config_dir = tmp_path / ".config" / "kyoro"
    config_dir.mkdir(parents=True, exist_ok=True)
    
    # Mock KYORO_CONFIG_DIR
    monkeypatch.setattr("health_config.KYORO_CONFIG_DIR", config_dir)
    
    cfg = Config()
    result = cfg.location_privacy
    
    assert result == {}


@pytest.mark.filterwarnings("ignore::UserWarning")
def test_location_privacy_missing_file_issues_warning(tmp_path, monkeypatch):
    """When location_privacy.json does not exist, a warning is issued."""
    from health_config import Config
    import warnings
    
    config_dir = tmp_path / ".config" / "kyoro"
    config_dir.mkdir(parents=True, exist_ok=True)
    
    monkeypatch.setattr("health_config.KYORO_CONFIG_DIR", config_dir)
    
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        cfg = Config()
        _ = cfg.location_privacy
        
        # Should have at least one warning about missing file
        assert len(w) >= 1
        assert any("Location privacy config" in str(warning.message) or 
                   "location_privacy" in str(warning.message).lower() for warning in w)


@pytest.mark.filterwarnings("ignore::UserWarning")
def test_location_privacy_valid_file_returns_config(tmp_path, monkeypatch):
    """When location_privacy.json exists with valid JSON, it is returned."""
    from health_config import Config
    
    config_dir = tmp_path / ".config" / "kyoro"
    config_dir.mkdir(parents=True, exist_ok=True)
    
    # Create a valid location_privacy.json
    privacy_config = {
        "default": {"store": "none", "precision": 0},
        "importers": {
            "import_skin": {"*": {"precision": 2}}
        },
        "zones": {"enabled": True, "radius_m": 500, "zone_precision": 2},
        "external_api": {"precision": 2},
        "llm": {"default": "none", "allow": {}},
        "exports": {"allow": {}}
    }
    
    privacy_file = config_dir / "location_privacy.json"
    privacy_file.write_text(json.dumps(privacy_config, indent=2))
    
    monkeypatch.setattr("health_config.KYORO_CONFIG_DIR", config_dir)
    
    cfg = Config()
    result = cfg.location_privacy
    
    assert result == privacy_config


@pytest.mark.filterwarnings("ignore::UserWarning")
def test_location_privacy_invalid_json_returns_empty(tmp_path, monkeypatch):
    """When location_privacy.json contains invalid JSON, returns {} with warning."""
    from health_config import Config
    import warnings
    
    config_dir = tmp_path / ".config" / "kyoro"
    config_dir.mkdir(parents=True, exist_ok=True)
    
    # Create an invalid JSON file
    privacy_file = config_dir / "location_privacy.json"
    privacy_file.write_text("invalid json {{{")
    
    monkeypatch.setattr("health_config.KYORO_CONFIG_DIR", config_dir)
    
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        cfg = Config()
        result = cfg.location_privacy
        
        assert result == {}
        assert any("location_privacy.json" in str(warning.message).lower() for warning in w)


@pytest.mark.filterwarnings("ignore::UserWarning")
def test_location_privacy_caches_result(tmp_path, monkeypatch):
    """The location_privacy property returns the same object on repeated access."""
    from health_config import Config
    
    config_dir = tmp_path / ".config" / "kyoro"
    config_dir.mkdir(parents=True, exist_ok=True)
    
    privacy_config = {"default": {"store": "none"}}
    privacy_file = config_dir / "location_privacy.json"
    privacy_file.write_text(json.dumps(privacy_config))
    
    monkeypatch.setattr("health_config.KYORO_CONFIG_DIR", config_dir)
    
    cfg = Config()
    result1 = cfg.location_privacy
    result2 = cfg.location_privacy
    
    # Should be the same object (cached)
    assert result1 is result2


@pytest.mark.filterwarnings("ignore::UserWarning")
def test_location_db_path_property(tmp_path, monkeypatch):
    """Config.location_db_path returns the path from config or default."""
    from health_config import Config
    from pathlib import Path
    
    config_dir = tmp_path / ".config" / "kyoro"
    config_dir.mkdir(parents=True, exist_ok=True)
    
    # Test with default path
    monkeypatch.setattr("health_config.KYORO_CONFIG_DIR", config_dir)
    monkeypatch.setattr("health_config._BASE_HOME", tmp_path)
    
    cfg = Config()
    default_path = cfg.location_db_path
    
    # Default should be Kyoro-HealthHub/data/location.db under home
    assert isinstance(default_path, Path)
    assert "location.db" in str(default_path)


@pytest.mark.filterwarnings("ignore::UserWarning")
def test_location_db_path_from_config(tmp_path, monkeypatch):
    """Config.location_db_path reads from config paths.location_db."""
    from health_config import Config, save
    import json
    
    config_dir = tmp_path / ".config" / "kyoro"
    config_dir.mkdir(parents=True, exist_ok=True)
    
    # Create a health_config.json with custom location_db path
    health_config = {
        "user": {"name": "Test", "birthdate": "1990-01-01", "timezone": "UTC"},
        "paths": {"location_db": str(tmp_path / "custom" / "location.db")},
        "devices": {},
        "clinical": {}
    }
    
    config_file = config_dir / "health_config.json"
    config_file.write_text(json.dumps(health_config))
    
    monkeypatch.setattr("health_config.CONFIG_PATH", config_file)
    monkeypatch.setattr("health_config.KYORO_CONFIG_DIR", config_dir)
    
    # Clear cache
    from health_config import load
    load.cache_clear()
    
    cfg = Config()
    result = cfg.location_db_path
    
    assert str(result) == str(tmp_path / "custom" / "location.db")


@pytest.mark.filterwarnings("ignore::UserWarning")
def test_template_importers_exist_as_files(tmp_path, monkeypatch):
    """Every importer key in location_privacy.example.json (not starting with _ and not fetch_daily)
    corresponds to an existing scripts/importers/<name>.py file."""
    import json
    
    # Load the template
    repo_root = Path(__file__).parent.parent.parent
    template_path = repo_root / "templates" / "location_privacy.example.json"
    template_content = json.loads(template_path.read_text())
    
    importers_cfg = template_content.get("importers", {})
    
    # Get all non-comment, non-fetch_daily keys
    importer_names = [
        name for name in importers_cfg.keys()
        if not name.startswith("_") and name != "fetch_daily"
    ]
    
    # Check that each importer has a corresponding .py file
    importers_dir = repo_root / "scripts" / "importers"
    
    missing_files = []
    for name in importer_names:
        expected_file = importers_dir / f"{name}.py"
        if not expected_file.exists():
            missing_files.append(name)
    
    assert missing_files == [], f"Missing importer files: {missing_files}"
