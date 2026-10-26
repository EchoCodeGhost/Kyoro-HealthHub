# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Tests for location column redaction in export_health.py.

@tier        unit
@purpose.de  Testet die Entfernung/Ersetzung von Ortsspalten im Export
@purpose.en  Tests removal/replacement of location columns in export
@method.de   Mockt die Location-Privacy-Konfiguration und prüft die Ergebnisse
@method.en   Mocks the location privacy configuration and checks results
@reads       location_privacy.json (mocked)
@writes      (nothing)
@limits.de   Nutzt pytest-mock für temporäre Dateien
@limits.en   Uses pytest-mock for temporary files
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))


@pytest.fixture
def mock_location_privacy_config(tmp_path, monkeypatch):
    """Erstellt eine temporäre location_privacy.json mit exports.allow."""
    config_dir = tmp_path / ".config" / "kyoro"
    config_dir.mkdir(parents=True, exist_ok=True)
    
    privacy_config = {
        "exports": {
            "allow": {
                "_comment": "Test comment",
                "_example_profile": "region",
                "test_region_profile": "region",
                "test_rounded_profile": 2,
                "test_allowed_profile": 3
            }
        }
    }
    
    privacy_file = config_dir / "location_privacy.json"
    privacy_file.write_text(json.dumps(privacy_config))
    
    monkeypatch.setattr("health_config.KYORO_CONFIG_DIR", config_dir)
    monkeypatch.setattr("health_config.CONFIG_PATH", config_dir / "health_config.json")
    
    # Erstelle eine minimale health_config.json
    health_config = {
        "user": {"name": "Test", "birthdate": "1990-01-01", "timezone": "UTC"},
        "paths": {"data_root": str(tmp_path / "data"), "analyses": str(tmp_path / "analyses")},
        "devices": {},
        "clinical": {}
    }
    (config_dir / "health_config.json").write_text(json.dumps(health_config))
    
    # Cache zurücksetzen
    from health_config import load
    load.cache_clear()

    # export_health hält eine Config-Instanz mit eigenem Cache; ohne Ersatz
    # hinge das Ergebnis von der Reihenfolge der Tests bzw. der echten Config ab
    import export_health
    monkeypatch.setattr(export_health, "_load_exports_allow", lambda: {
        k: v for k, v in privacy_config["exports"]["allow"].items() if not k.startswith("_")})


@pytest.mark.filterwarnings("ignore::UserWarning")
def test_location_columns_removed_when_profile_not_allowed(mock_location_privacy_config):
    """Wenn das Profil nicht in exports.allow ist, werden alle Ortsspalten entfernt."""
    from export_health import _redact_location_columns
    
    rows = [
        {"id": 1, "lat": 48.12345, "lon": 11.54321, "value": 100},
        {"id": 2, "latitude": 48.2, "longitude": 11.6, "value": 200},
        {"id": 3, "custom_lat": 48.3, "custom_lon": 11.7, "value": 300},
    ]
    
    result_rows, removed_count = _redact_location_columns(rows, "unknown_profile")
    
    # Alle Ortsspalten sollten entfernt sein
    for row in result_rows:
        assert "lat" not in row
        assert "lon" not in row
        assert "latitude" not in row
        assert "longitude" not in row
        assert "custom_lat" not in row
        assert "custom_lon" not in row
        assert "value" in row
        assert "id" in row
    
    assert removed_count == 6  # 3 Zeilen × 2 Spalten


@pytest.mark.filterwarnings("ignore::UserWarning")
def test_location_columns_replaced_with_region(mock_location_privacy_config):
    """Wenn das Profil 'region' erlaubt ist, werden Ortsspalten durch region ersetzt."""
    from export_health import _redact_location_columns
    
    rows = [
        {"id": 1, "lat": 48.12345, "lon": 11.54321, "value": 100},
        {"id": 2, "latitude": 48.2, "longitude": 11.6, "value": 200},
    ]
    
    result_rows, removed_count = _redact_location_columns(rows, "test_region_profile")
    
    # Ortsspalten sollten entfernt und durch region ersetzt sein
    for row in result_rows:
        assert "lat" not in row
        assert "lon" not in row
        assert "latitude" not in row
        assert "longitude" not in row
        assert "region" in row
        assert "value" in row
        assert "id" in row
    
    # Region sollte berechnet sein
    assert result_rows[0]["region"] in ["Bayern", "Unbekannt", "Unknown", "Abroad"]
    
    assert removed_count == 4  # 2 Zeilen × 2 Spalten


@pytest.mark.filterwarnings("ignore::UserWarning")
def test_location_columns_rounded(mock_location_privacy_config):
    """Wenn das Profil eine numerische Stufe erlaubt ist, werden Koordinaten gerundet."""
    from export_health import _redact_location_columns
    
    rows = [
        {"id": 1, "lat": 48.12345, "lon": 11.54321, "value": 100},
        {"id": 2, "lat": 48.98765, "lon": 11.23456, "value": 200},
    ]
    
    result_rows, removed_count = _redact_location_columns(rows, "test_rounded_profile")
    
    # Koordinaten sollten auf 2 Stellen gerundet sein
    for row in result_rows:
        assert "lat" in row
        assert "lon" in row
        assert "region" not in row
        assert "value" in row
        
        # Prüfe, dass die Werte gerundet sind
        if row["id"] == 1:
            assert row["lat"] == 48.12
            assert row["lon"] == 11.54
        elif row["id"] == 2:
            assert row["lat"] == 48.99
            assert row["lon"] == 11.23
    
    assert removed_count == 0  # Keine Spalten entfernt, nur gerundet


@pytest.mark.filterwarnings("ignore::UserWarning")
def test_example_profile_not_allowed(mock_location_privacy_config):
    """_example_profile wird nicht als erlaubt gewertet."""
    from export_health import _redact_location_columns
    
    rows = [
        {"id": 1, "lat": 48.12345, "lon": 11.54321, "value": 100},
    ]
    
    result_rows, removed_count = _redact_location_columns(rows, "_example_profile")
    
    # Alle Ortsspalten sollten entfernt sein
    assert "lat" not in result_rows[0]
    assert "lon" not in result_rows[0]
    assert removed_count == 2


@pytest.mark.filterwarnings("ignore::UserWarning")
def test_mixed_location_columns(mock_location_privacy_config):
    """Test mit verschiedenen Ortsspalten-Namen."""
    from export_health import _redact_location_columns
    
    rows = [
        {
            "id": 1,
            "lat": 48.12345,
            "lon": 11.54321,
            "latitude": 48.5,
            "longitude": 11.5,
            "gps_lat": 48.9,
            "gps_lon": 11.9,
            "value": 100
        },
    ]
    
    result_rows, removed_count = _redact_location_columns(rows, "test_rounded_profile")
    
    # Alle Ortsspalten sollten auf 2 Stellen gerundet sein
    row = result_rows[0]
    assert row["lat"] == 48.12
    assert row["lon"] == 11.54
    assert row["latitude"] == 48.5
    assert row["longitude"] == 11.5
    assert row["gps_lat"] == 48.9
    assert row["gps_lon"] == 11.9
    assert row["value"] == 100
    assert removed_count == 0


@pytest.mark.filterwarnings("ignore::UserWarning")
def test_non_numeric_location_values_removed(mock_location_privacy_config):
    """Nicht-numerische Werte in Ortsspalten werden entfernt."""
    from export_health import _redact_location_columns
    
    rows = [
        {"id": 1, "lat": "invalid", "lon": 11.54321, "value": 100},
        {"id": 2, "lat": 48.12345, "lon": "invalid", "value": 200},
    ]
    
    result_rows, removed_count = _redact_location_columns(rows, "test_rounded_profile")
    
    # Nicht-numerische Werte sollten entfernt sein
    assert "lat" not in result_rows[0]
    assert "lon" in result_rows[0]
    assert "lat" in result_rows[1]
    assert "lon" not in result_rows[1]
    
    assert removed_count == 2


@pytest.mark.filterwarnings("ignore::UserWarning")
def test_no_location_columns_unchanged(mock_location_privacy_config):
    """Zeilen ohne Ortsspalten bleiben unverändert."""
    from export_health import _redact_location_columns
    
    rows = [
        {"id": 1, "value": 100, "name": "test"},
        {"id": 2, "value": 200, "description": "another"},
    ]
    
    result_rows, removed_count = _redact_location_columns(rows, "test_rounded_profile")
    
    # Nichts sollte verändert sein
    assert result_rows == rows
    assert removed_count == 0


@pytest.mark.filterwarnings("ignore::UserWarning")
def test_empty_rows(mock_location_privacy_config):
    """Leere Zeilen werden korrekt behandelt."""
    from export_health import _redact_location_columns
    
    result_rows, removed_count = _redact_location_columns([], "test_rounded_profile")
    
    assert result_rows == []
    assert removed_count == 0


@pytest.mark.filterwarnings("ignore::UserWarning")
def test_region_uses_matching_pairs(mock_location_privacy_config):
    """Region kommt je Spaltenpaar gleicher Herkunft; Einzelspalten werden nur entfernt."""
    from export_health import _redact_location_columns

    rows = [{"id": 1, "start_lat": 48.12345, "start_lon": 11.54321,
             "end_lat": 28.12345, "end_lon": -14.12345, "orphan_lat": 48.5, "value": 1}]
    result_rows, removed_count = _redact_location_columns(rows, "test_region_profile")

    row = result_rows[0]
    assert row["start_region"] == "Bayern"
    assert row["end_region"] in ("Ausland", "Abroad")
    assert "orphan_region" not in row and "region" not in row
    assert not any(k.endswith(("_lat", "_lon")) for k in row)
    assert removed_count == 5


@pytest.mark.filterwarnings("ignore::UserWarning")
def test_boolean_level_is_not_a_precision(mock_location_privacy_config, monkeypatch):
    """true in exports.allow ist keine Genauigkeit und entfernt die Spalten."""
    import export_health
    monkeypatch.setattr(export_health, "_load_exports_allow", lambda: {"p": True})
    result_rows, removed_count = export_health._redact_location_columns(
        [{"lat": 48.12345, "lon": 11.54321}], "p")
    assert result_rows == [{}] and removed_count == 2
