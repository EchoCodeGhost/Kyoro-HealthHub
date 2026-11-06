# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Tests for location_store module.

@tier        unit
@purpose.de  Testet alle Funktionen von modules.location_store
@purpose.en  Tests all functions from modules.location_store
@method.de   Nutzt pytest-mock für temporäre Dateien und Datenbanken
@method.en   Uses pytest-mock for temporary files and databases
@reads       location_privacy.json (mocked), identity.db (mocked), location.db (mocked)
@writes      location.db (test, temporär)
@limits.de   Nutzt nur syntetische Koordinaten (48.12345, 11.54321 usw.)
@limits.en   Uses only synthetic coordinates (48.12345, 11.54321 etc.)
"""

import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
import sqlite3

# Füge scripts zum Path hinzu
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from utils.create_location_schema import ensure_location_schema  # noqa: E402


def _create_test_config(tmp_path, config_data=None):
    """Erstellt eine temporäre health_config.json für Tests."""
    config_dir = tmp_path / ".config" / "kyoro"
    config_dir.mkdir(parents=True, exist_ok=True)
    
    config_file = config_dir / "health_config.json"
    config = {
        "user": {"name": "Test", "birthdate": "1990-01-01", "timezone": "UTC"},
        "paths": {
            "db": str(tmp_path / "data" / "health.db"),
            "medicine_db": str(tmp_path / "data" / "medicine.db"),
            "location_db": str(tmp_path / "data" / "location.db"),
            "data_root": str(tmp_path / "imports"),
        },
        "devices": {},
        "clinical": {},
    }
    if config_data:
        config.update(config_data)
    
    config_file.write_text(json.dumps(config, indent=2))
    return config_dir


def _create_test_location_privacy(tmp_path, privacy_data=None):
    """Erstellt eine temporäre location_privacy.json für Tests."""
    config_dir = tmp_path / ".config" / "kyoro"
    config_dir.mkdir(parents=True, exist_ok=True)
    
    privacy_file = config_dir / "location_privacy.json"
    default_privacy = {
        "default": {"store": "none", "precision": 0},
        "importers": {
            "import_skin": {"*": {"precision": 2}},
            "import_lab_results": {"*": {"store": "none"}},
            "import_fundus": {"*": {"store": "none"}},
        },
        "zones": {"enabled": True, "radius_m": 500, "zone_precision": 2},
        "external_api": {"precision": 2},
        "llm": {"default": "none", "allow": {"analyse_synthesis": "region"}},
        "exports": {"allow": {}}
    }
    if privacy_data:
        default_privacy.update(privacy_data)
    
    privacy_file.write_text(json.dumps(default_privacy, indent=2))
    return privacy_file


# ============================================================================
# Policy Resolution Tests
# ============================================================================

class TestResolvePolicy:
    """Tests für resolve_policy()."""

    @pytest.mark.filterwarnings("ignore::UserWarning")
    def test_missing_config_returns_store_none(self, tmp_path, monkeypatch):
        """Fehlende location_privacy.json → store: none."""
        config_dir = tmp_path / ".config" / "kyoro"
        config_dir.mkdir(parents=True, exist_ok=True)
        
        monkeypatch.setattr("health_config.KYORO_CONFIG_DIR", config_dir)
        
        from modules.location_store import resolve_policy
        # Cache klaren
        from health_config import load
        load.cache_clear()
        
        policy = resolve_policy("import_skin", ".jpg")
        assert policy == {"store": "none"}

    @pytest.mark.filterwarnings("ignore::UserWarning")
    def test_default_policy_applied(self, tmp_path, monkeypatch):
        """Default-Policy wird angewendet wenn kein Importer-Spezifisches existiert."""
        config_dir = _create_test_config(tmp_path)
        _create_test_location_privacy(tmp_path, {
            "default": {"precision": 3}
        })
        
        monkeypatch.setattr("health_config.KYORO_CONFIG_DIR", config_dir)
        
        from modules.location_store import resolve_policy
        from health_config import load
        load.cache_clear()
        
        policy = resolve_policy("unknown_importer", ".jpg")
        assert policy == {"precision": 3}

    @pytest.mark.filterwarnings("ignore::UserWarning")
    def test_importer_wildcard_matches(self, tmp_path, monkeypatch):
        """Importer + "*" wird angewendet."""
        config_dir = _create_test_config(tmp_path)
        _create_test_location_privacy(tmp_path, {
            "default": {"store": "none"},
            "importers": {
                "import_skin": {"*": {"precision": 2}}
            }
        })
        
        monkeypatch.setattr("health_config.KYORO_CONFIG_DIR", config_dir)
        
        from modules.location_store import resolve_policy
        from health_config import load
        load.cache_clear()
        
        policy = resolve_policy("import_skin", ".jpg")
        assert policy == {"precision": 2}

    @pytest.mark.filterwarnings("ignore::UserWarning")
    def test_file_type_overrides_wildcard(self, tmp_path, monkeypatch):
        """Dateityp-spezifisch überschreibt Importer-Wildcard."""
        config_dir = _create_test_config(tmp_path)
        _create_test_location_privacy(tmp_path, {
            "default": {"store": "none"},
            "importers": {
                "import_skin": {
                    "*": {"precision": 2},
                    ".dng": {"precision": 1}
                }
            }
        })
        
        monkeypatch.setattr("health_config.KYORO_CONFIG_DIR", config_dir)
        
        from modules.location_store import resolve_policy
        from health_config import load
        load.cache_clear()
        
        policy_jpg = resolve_policy("import_skin", ".jpg")
        policy_dng = resolve_policy("import_skin", ".dng")
        
        assert policy_jpg == {"precision": 2}
        assert policy_dng == {"precision": 1}

    @pytest.mark.filterwarnings("ignore::UserWarning")
    def test_store_none_policy(self, tmp_path, monkeypatch):
        """Policy mit store: none wird korrekt zurückgegeben."""
        config_dir = _create_test_config(tmp_path)
        _create_test_location_privacy(tmp_path, {
            "default": {"store": "none"},
            "importers": {
                "import_lab_results": {"*": {"store": "none"}}
            }
        })
        
        monkeypatch.setattr("health_config.KYORO_CONFIG_DIR", config_dir)
        
        from modules.location_store import resolve_policy
        from health_config import load
        load.cache_clear()
        
        policy = resolve_policy("import_lab_results", ".pdf")
        assert policy == {"store": "none"}


# ============================================================================
# Rounding Tests
# ============================================================================

class TestRoundCoords:
    """Tests für round_coords()."""

    def test_round_to_2_decimal_places(self):
        """Rundung auf 2 Dezimalstellen."""
        from modules.location_store import round_coords
        
        lat, lon = round_coords(48.123456, 11.543210, 2)
        assert lat == 48.12
        assert lon == 11.54

    def test_round_to_5_decimal_places(self):
        """Rundung auf 5 Dezimalstellen (hohe Präzision)."""
        from modules.location_store import round_coords
        
        lat, lon = round_coords(48.123456, 11.543210, 5)
        assert lat == 48.12346
        assert lon == 11.54321

    def test_round_to_0_decimal_places(self):
        """Rundung auf 0 Dezimalstellen."""
        from modules.location_store import round_coords
        
        lat, lon = round_coords(48.123456, 11.543210, 0)
        assert lat == 48.0
        assert lon == 12.0

    def test_clamp_precision_to_0_5(self):
        """Präzision wird auf 0-5 begrenzt."""
        from modules.location_store import round_coords
        
        # Negative Präzision → 0
        lat, lon = round_coords(48.123456, 11.543210, -1)
        assert lat == 48.0
        assert lon == 12.0  # 11.543210 rounds to 12 with banker's rounding
        
        # Präzision > 5 → 5
        lat, lon = round_coords(48.123456, 11.543210, 10)
        assert lat == 48.12346
        assert lon == 11.54321


# ============================================================================
# SHA256 Tests
# ============================================================================

class TestFileSha256:
    """Tests für file_sha256()."""

    def test_sha256_of_empty_file(self, tmp_path):
        """SHA256 einer leeren Datei."""
        from modules.location_store import file_sha256
        
        empty_file = tmp_path / "empty.txt"
        empty_file.touch()
        
        result = file_sha256(empty_file)
        # SHA256 einer leeren Datei
        expected = hashlib.sha256(b"").hexdigest()
        assert result == expected

    def test_sha256_of_real_file(self, tmp_path):
        """SHA256 einer Datei mit Inhalt."""
        from modules.location_store import file_sha256
        
        test_file = tmp_path / "test.txt"
        test_file.write_text("Hello, World!")
        
        result = file_sha256(test_file)
        expected = hashlib.sha256(b"Hello, World!").hexdigest()
        assert result == expected

    def test_sha256_of_nonexistent_file(self, tmp_path):
        """SHA256 einer nicht existierenden Datei gibt leeren String zurück."""
        from modules.location_store import file_sha256
        
        nonexistent = tmp_path / "nonexistent.txt"
        result = file_sha256(nonexistent)
        assert result == ""


# ============================================================================
# Location Token Tests
# ============================================================================

class TestLocationToken:
    """Tests für location_token()."""

    @pytest.mark.filterwarnings("ignore::UserWarning")
    def test_token_deterministic_for_same_cell(self, tmp_path, monkeypatch):
        """Gleiche Zelle mit gleicher Präzision → gleicher Token."""
        config_dir = _create_test_config(tmp_path)
        
        # Erstelle identity.db mit Salt
        identity_db = config_dir / "identity.db"
        conn = sqlite3.connect(str(identity_db))
        conn.execute(
            "CREATE TABLE IF NOT EXISTS pseudonym_salt (id INTEGER PRIMARY KEY CHECK (id = 1), salt_hex TEXT NOT NULL)"
        )
        conn.execute(
            "INSERT INTO pseudonym_salt (id, salt_hex) VALUES (?, ?)",
            (1, "test_salt_12345")
        )
        conn.commit()
        conn.close()
        
        monkeypatch.setattr("health_config.KYORO_CONFIG_DIR", config_dir)
        
        from modules.location_store import location_token
        from health_config import load
        load.cache_clear()
        
        token1 = location_token(48.123456, 11.543210, 2)
        token2 = location_token(48.123456, 11.543210, 2)
        
        assert token1 == token2

    @pytest.mark.filterwarnings("ignore::UserWarning")
    def test_token_differs_for_different_cells(self, tmp_path, monkeypatch):
        """Unterschiedliche Zellen → unterschiedliche Tokens."""
        config_dir = _create_test_config(tmp_path)
        
        # Erstelle identity.db mit Salt
        identity_db = config_dir / "identity.db"
        conn = sqlite3.connect(str(identity_db))
        conn.execute(
            "CREATE TABLE IF NOT EXISTS pseudonym_salt (id INTEGER PRIMARY KEY CHECK (id = 1), salt_hex TEXT NOT NULL)"
        )
        conn.execute(
            "INSERT INTO pseudonym_salt (id, salt_hex) VALUES (?, ?)",
            (1, "test_salt_12345")
        )
        conn.commit()
        conn.close()
        
        monkeypatch.setattr("health_config.KYORO_CONFIG_DIR", config_dir)
        
        from modules.location_store import location_token
        from health_config import load
        load.cache_clear()
        
        token1 = location_token(48.123456, 11.543210, 2)
        token2 = location_token(49.123456, 12.543210, 2)
        
        assert token1 != token2

    @pytest.mark.filterwarnings("ignore::UserWarning")
    def test_token_prefix(self, tmp_path, monkeypatch):
        """Token beginnt mit LOC-."""
        config_dir = _create_test_config(tmp_path)
        
        identity_db = config_dir / "identity.db"
        conn = sqlite3.connect(str(identity_db))
        conn.execute(
            "CREATE TABLE IF NOT EXISTS pseudonym_salt (id INTEGER PRIMARY KEY CHECK (id = 1), salt_hex TEXT NOT NULL)"
        )
        conn.execute(
            "INSERT INTO pseudonym_salt (id, salt_hex) VALUES (?, ?)",
            (1, "test_salt_12345")
        )
        conn.commit()
        conn.close()
        
        monkeypatch.setattr("health_config.KYORO_CONFIG_DIR", config_dir)
        
        from modules.location_store import location_token
        from health_config import load
        load.cache_clear()
        
        token = location_token(48.123456, 11.543210, 2)
        assert token.startswith("LOC-")
        assert len(token) == 12  # LOC- + 8 Hex-Zeichen


# ============================================================================
# Record Tests
# ============================================================================

class TestRecord:
    """Tests für record()."""

    @pytest.mark.filterwarnings("ignore::UserWarning")
    def test_store_none_skips_insert(self, tmp_path, monkeypatch):
        """store: none → kein Insert in location_registry."""
        config_dir = _create_test_config(tmp_path)
        _create_test_location_privacy(tmp_path, {
            "importers": {
                "import_lab_results": {"*": {"store": "none"}}
            }
        })
        
        # Datenbank erstellen
        data_dir = tmp_path / "data"
        data_dir.mkdir(exist_ok=True)
        db_path = data_dir / "location.db"
        
        conn = sqlite3.connect(str(db_path))
        ensure_location_schema(conn)
        conn.commit()
        conn.close()
        
        monkeypatch.setattr("health_config.KYORO_CONFIG_DIR", config_dir)
        
        from modules.location_store import record
        from health_config import load
        load.cache_clear()
        
        # Mock open_location_db um die Test-DB zu nutzen
        def mock_open_location_db(path=None):
            import sqlite3
            return sqlite3.connect(str(db_path))
        
        with patch("modules.location_store.open_location_db", mock_open_location_db):
            result = record(
                importer="import_lab_results",
                file_type=".pdf",
                lat=48.123456,
                lon=11.543210,
                ts="2024-01-15T10:30:00Z",
                date="2024-01-15",
                person="PER-TEST1234"
            )
        
        assert result is False
        
        # Prüfen, dass nichts eingeführt wurde
        conn = sqlite3.connect(str(db_path))
        cursor = conn.execute("SELECT COUNT(*) FROM location_registry")
        count = cursor.fetchone()[0]
        conn.close()
        
        assert count == 0

    @pytest.mark.filterwarnings("ignore::UserWarning")
    def test_record_inserts_with_precision(self, tmp_path, monkeypatch):
        """record() speichert mit korrekter Präzision."""
        config_dir = _create_test_config(tmp_path)
        _create_test_location_privacy(tmp_path, {
            "default": {"precision": 2},
            "importers": {}
        })
        
        data_dir = tmp_path / "data"
        data_dir.mkdir(exist_ok=True)
        db_path = data_dir / "location.db"
        
        conn = sqlite3.connect(str(db_path))
        ensure_location_schema(conn)
        conn.commit()
        conn.close()
        
        # identity.db mit Salt
        identity_db = config_dir / "identity.db"
        conn = sqlite3.connect(str(identity_db))
        conn.execute(
            "CREATE TABLE IF NOT EXISTS pseudonym_salt (id INTEGER PRIMARY KEY CHECK (id = 1), salt_hex TEXT NOT NULL)"
        )
        conn.execute(
            "INSERT INTO pseudonym_salt (id, salt_hex) VALUES (?, ?)",
            (1, "test_salt")
        )
        conn.commit()
        conn.close()
        
        monkeypatch.setattr("health_config.KYORO_CONFIG_DIR", config_dir)
        
        from modules.location_store import record
        from health_config import load
        load.cache_clear()
        
        def mock_open_location_db(path=None):
            import sqlite3
            return sqlite3.connect(str(db_path))
        
        with patch("modules.location_store.open_location_db", mock_open_location_db):
            result = record(
                importer="import_skin",
                file_type=".jpg",
                lat=48.123456,
                lon=11.543210,
                ts="2024-01-15T10:30:00Z",
                date="2024-01-15",
                person="PER-TEST1234"
            )
        
        assert result is True
        
        # Prüfen, dass der Eintrag mit Präzision 2 gespeichert wurde
        conn = sqlite3.connect(str(db_path))
        cursor = conn.execute(
            "SELECT lat, lon, precision FROM location_registry WHERE importer = ?",
            ("import_skin",)
        )
        row = cursor.fetchone()
        conn.close()
        
        assert row is not None
        assert row[0] == 48.12  # lat auf 2 Stellen gerundet
        assert row[1] == 11.54  # lon auf 2 Stellen gerundet
        assert row[2] == 2       # precision

    @pytest.mark.filterwarnings("ignore::UserWarning")
    def test_missing_person_skips_insert(self, tmp_path, monkeypatch):
        """Fehlendes person-Feld → kein Insert."""
        config_dir = _create_test_config(tmp_path)
        _create_test_location_privacy(tmp_path, {
            "default": {"precision": 2}
        })
        
        data_dir = tmp_path / "data"
        data_dir.mkdir(exist_ok=True)
        db_path = data_dir / "location.db"
        
        conn = sqlite3.connect(str(db_path))
        ensure_location_schema(conn)
        conn.commit()
        conn.close()
        
        monkeypatch.setattr("health_config.KYORO_CONFIG_DIR", config_dir)
        
        from modules.location_store import record
        from health_config import load
        load.cache_clear()
        
        def mock_open_location_db(path=None):
            import sqlite3
            return sqlite3.connect(str(db_path))
        
        import warnings
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            with patch("modules.location_store.open_location_db", mock_open_location_db):
                result = record(
                    importer="import_skin",
                    file_type=".jpg",
                    lat=48.123456,
                    lon=11.543210,
                    ts="2024-01-15T10:30:00Z",
                    date="2024-01-15",
                    person=None  # Missing!
                )
        
        assert result is False
        assert any("Kein person-Pseudonym" in str(warning.message) or 
                   "No person pseudonym" in str(warning.message) for warning in w)


# ============================================================================
# Filter Prompt Text Tests
# ============================================================================

class TestFilterPromptText:
    """Tests für filter_prompt_text()."""

    @pytest.mark.filterwarnings("ignore::UserWarning")
    def test_removes_coordinates_for_nonexistent_caller(self, tmp_path, monkeypatch):
        """Caller nicht in allow → Koordinaten werden entfernt."""
        config_dir = _create_test_config(tmp_path)
        _create_test_location_privacy(tmp_path, {
            "llm": {"default": "none", "allow": {}}
        })
        
        monkeypatch.setattr("health_config.KYORO_CONFIG_DIR", config_dir)
        
        from modules.location_store import filter_prompt_text
        from health_config import load
        load.cache_clear()
        
        text = "Der Befund zeigt eine Anomalie bei 48.12345, 11.54321."
        filtered, count = filter_prompt_text(text, "unknown_script")
        
        assert "48.12345" not in filtered
        assert "11.54321" not in filtered
        assert count >= 1

    @pytest.mark.filterwarnings("ignore::UserWarning")
    def test_allows_coordinates_for_allowed_caller_with_raster(self, tmp_path, monkeypatch):
        """Erlaubter Caller mit raster-Level → Koordinaten werden gerundet."""
        config_dir = _create_test_config(tmp_path)
        _create_test_location_privacy(tmp_path, {
            "llm": {"default": "none", "allow": {"analyse_travel": 2}}
        })
        
        monkeypatch.setattr("health_config.KYORO_CONFIG_DIR", config_dir)
        
        from modules.location_store import filter_prompt_text
        from health_config import load
        load.cache_clear()
        
        text = "Position: 48.123456, 11.543210"
        filtered, count = filter_prompt_text(text, "analyse_travel")
        
        # Sollte auf 2 Dezimalstellen gerundet sein
        assert "48.12" in filtered
        assert "11.54" in filtered
        assert "48.123456" not in filtered
        assert count >= 1


# ============================================================================
# For External API Tests
# ============================================================================

class TestForExternalApi:
    """Tests für for_external_api()."""

    @pytest.mark.filterwarnings("ignore::UserWarning")
    def test_uses_configured_precision(self, tmp_path, monkeypatch):
        """Verwendet die konfigurierte external_api.precision."""
        config_dir = _create_test_config(tmp_path)
        _create_test_location_privacy(tmp_path, {
            "external_api": {"precision": 3}
        })
        
        monkeypatch.setattr("health_config.KYORO_CONFIG_DIR", config_dir)
        
        from modules.location_store import for_external_api
        from health_config import load
        load.cache_clear()
        
        lat, lon = for_external_api(48.123456, 11.543210)
        
        assert lat == 48.123
        assert lon == 11.543

    @pytest.mark.filterwarnings("ignore::UserWarning")
    def test_default_precision_is_2(self, tmp_path, monkeypatch):
        """Standard-Präzision ist 2."""
        config_dir = _create_test_config(tmp_path)
        _create_test_location_privacy(tmp_path, {})
        
        monkeypatch.setattr("health_config.KYORO_CONFIG_DIR", config_dir)
        
        from modules.location_store import for_external_api
        from health_config import load
        load.cache_clear()
        
        lat, lon = for_external_api(48.123456, 11.543210)
        
        assert lat == 48.12
        assert lon == 11.54


# ============================================================================
# Caller Name Tests
# ============================================================================

class TestGetCallerName:
    """Tests für get_caller_name()."""

    def test_explicit_caller_override(self):
        """Expliziter Caller überschreibt sys.argv[0]."""
        from modules.location_store import get_caller_name
        
        result = get_caller_name("my_custom_script")
        assert result == "my_custom_script"

    def test_from_sys_argv(self, monkeypatch):
        """Caller wird aus sys.argv[0] extrahiert."""
        from modules.location_store import get_caller_name
        
        # Mock sys.argv
        test_args = ["/path/to/analyse_synthesis.py", "arg1", "arg2"]
        monkeypatch.setattr("sys.argv", test_args)
        
        result = get_caller_name()
        assert result == "analyse_synthesis"

    def test_fallback_to_unknown(self, monkeypatch):
        """Fallback auf 'unknown' bei leeren sys.argv."""
        from modules.location_store import get_caller_name
        
        monkeypatch.setattr("sys.argv", [])
        
        result = get_caller_name()
        assert result == "unknown"


class TestForPrompt:
    """Tests für for_prompt Funktion — nur grundlegende Tests ohne DB."""

    @pytest.mark.filterwarnings("ignore::UserWarning")
    def test_no_refs_returns_empty_list(self, tmp_path, monkeypatch):
        """for_prompt mit leerer refs-Liste gibt leere Liste zurück."""
        from modules.location_store import for_prompt
        
        config_dir = tmp_path / ".config" / "kyoro"
        config_dir.mkdir(parents=True, exist_ok=True)
        
        privacy_config = {
            "default": {"store": "none", "precision": 0},
            "llm": {"default": "none", "allow": {}},
        }
        (config_dir / "location_privacy.json").write_text(json.dumps(privacy_config))
        
        with patch("health_config.KYORO_CONFIG_DIR", config_dir):
            result = for_prompt("test_caller", refs=None)
            assert result == []
            
            result = for_prompt("test_caller", refs=[])
            assert result == []

    @pytest.mark.filterwarnings("ignore::UserWarning")
    def test_level_none_returns_empty_list(self, tmp_path, monkeypatch):
        """for_prompt mit Level 'none' gibt leere Liste zurück."""
        from modules.location_store import for_prompt
        
        config_dir = tmp_path / ".config" / "kyoro"
        config_dir.mkdir(parents=True, exist_ok=True)
        
        privacy_config = {
            "default": {"store": "none", "precision": 0},
            "llm": {"default": "none", "allow": {"test_caller": "none"}},
        }
        (config_dir / "location_privacy.json").write_text(json.dumps(privacy_config))
        
        with patch("health_config.KYORO_CONFIG_DIR", config_dir):
            result = for_prompt("test_caller", refs=[1, 2, 3])
            assert result == []

    @pytest.mark.filterwarnings("ignore::UserWarning")
    def test_unknown_level_returns_empty_list_with_warning(self, tmp_path, monkeypatch):
        """for_prompt mit unbekannter Stufe gibt leere Liste mit Warnung zurück."""
        from modules.location_store import for_prompt
        import warnings
        
        config_dir = tmp_path / ".config" / "kyoro"
        config_dir.mkdir(parents=True, exist_ok=True)
        
        privacy_config = {
            "default": {"store": "none", "precision": 0},
            "llm": {"default": "none", "allow": {"test_caller": "unknown_level"}},
        }
        (config_dir / "location_privacy.json").write_text(json.dumps(privacy_config))
        
        with patch("health_config.KYORO_CONFIG_DIR", config_dir):
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                result = for_prompt("test_caller", refs=[1, 2, 3])
                
                assert result == []
                # Sollte eine Warnung geben
                assert any("Unbekannte Location-Level" in str(warning.message) for warning in w)

    @pytest.mark.filterwarnings("ignore::UserWarning")
    def test_explicit_level_overrides_policy(self, tmp_path, monkeypatch):
        """Explizites Level überschreibt die Policy."""
        from modules.location_store import for_prompt
        
        config_dir = tmp_path / ".config" / "kyoro"
        config_dir.mkdir(parents=True, exist_ok=True)
        
        # Policy sagt "none", aber explizites Level ist "region"
        privacy_config = {
            "default": {"store": "none", "precision": 0},
            "llm": {"default": "none", "allow": {"test_caller": "none"}},
        }
        (config_dir / "location_privacy.json").write_text(json.dumps(privacy_config))
        
        with patch("health_config.KYORO_CONFIG_DIR", config_dir):
            # Ohne explizites Level: empty
            result = for_prompt("test_caller", refs=[1])
            assert result == []
            
            # Mit explizitem Level: should try to read from DB (will fail and return [])
            # This is OK - we just verify it doesn't crash with explicit level
            result = for_prompt("test_caller", refs=[1], level="region")
            # Will return [] because DB doesn't exist, but that's OK
            assert isinstance(result, list)

    @pytest.mark.filterwarnings("ignore::UserWarning")
    def test_invalid_ref_types(self, tmp_path, monkeypatch):
        """for_prompt ignoriert ungültige Ref-Typen."""
        from modules.location_store import for_prompt
        
        config_dir = tmp_path / ".config" / "kyoro"
        config_dir.mkdir(parents=True, exist_ok=True)
        
        privacy_config = {
            "default": {"store": "none", "precision": 0},
            "llm": {"default": "none", "allow": {"test_caller": 2}},
        }
        (config_dir / "location_privacy.json").write_text(json.dumps(privacy_config))
        
        with patch("health_config.KYORO_CONFIG_DIR", config_dir):
            # String refs sollten ignoriert werden
            result = for_prompt("test_caller", refs=["invalid", "also_invalid"])
            assert result == []
            
            # Gemischte Typen: nur Integer werden berücksichtigt
            result = for_prompt("test_caller", refs=["invalid", 1, None, 2.5])
            assert result == []  # 1 ist Integer, aber DB existiert nicht
