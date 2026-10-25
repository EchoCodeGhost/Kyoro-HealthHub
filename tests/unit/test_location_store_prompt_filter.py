# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Tests for location privacy prompt filtering.

@tier        unit
@purpose.de  Testet die Location-Privacy-Filter für Prompts
@purpose.en  Tests location privacy filters for prompts
@method.de   Testet filter_prompt_text, call_llm-Integration
@method.en   Tests filter_prompt_text, call_llm integration
@reads       location_privacy.json (mocked)
@writes      (nothing)
@limits.de   Nutzt nur syntetische Koordinaten
@limits.en   Uses only synthetic coordinates
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))


def _create_test_config(tmp_path, privacy_data=None):
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
    
    config_file.write_text(json.dumps(config, indent=2))
    return config_dir


def _create_test_location_privacy(tmp_path, privacy_data=None):
    """Erstellt eine temporäre location_privacy.json für Tests."""
    config_dir = tmp_path / ".config" / "kyoro"
    config_dir.mkdir(parents=True, exist_ok=True)
    
    privacy_file = config_dir / "location_privacy.json"
    default_privacy = {
        "default": {"store": "none", "precision": 0},
        "importers": {},
        "zones": {"enabled": True, "radius_m": 500, "zone_precision": 2},
        "external_api": {"precision": 2},
        "llm": {"default": "none", "allow": {}},
        "exports": {"allow": {}}
    }
    if privacy_data:
        default_privacy.update(privacy_data)
    
    privacy_file.write_text(json.dumps(default_privacy, indent=2))
    return privacy_file


class TestFilterPromptText:
    """Tests für filter_prompt_text()."""

    @pytest.mark.filterwarnings("ignore::UserWarning")
    def test_removes_coordinates_by_default(self, tmp_path, monkeypatch):
        """Standardmäßig (default: none) werden Koordinaten entfernt."""
        config_dir = _create_test_config(tmp_path)
        _create_test_location_privacy(tmp_path, {
            "llm": {"default": "none", "allow": {}}
        })
        
        monkeypatch.setattr("health_config.KYORO_CONFIG_DIR", config_dir)
        
        from modules.location_store import filter_prompt_text
        from health_config import load
        load.cache_clear()
        
        text = "Position: 48.123456, 11.543210"
        filtered, count = filter_prompt_text(text, "test_caller")
        
        assert "48.123456" not in filtered
        assert "11.543210" not in filtered
        assert count >= 1

    @pytest.mark.filterwarnings("ignore::UserWarning")
    def test_keeps_coordinates_for_allowed_caller_with_raster(self, tmp_path, monkeypatch):
        """Erlaubter Caller mit raster-Level behält Koordinaten (gerundet)."""
        config_dir = _create_test_config(tmp_path)
        _create_test_location_privacy(tmp_path, {
            "llm": {"default": "none", "allow": {"test_caller": 2}}
        })
        
        monkeypatch.setattr("health_config.KYORO_CONFIG_DIR", config_dir)
        
        from modules.location_store import filter_prompt_text
        from health_config import load
        load.cache_clear()
        
        text = "Position: 48.123456, 11.543210"
        filtered, count = filter_prompt_text(text, "test_caller")
        
        # Sollte auf 2 Dezimalstellen gerundet sein
        assert "48.12" in filtered
        assert "11.54" in filtered
        assert count >= 1

    @pytest.mark.filterwarnings("ignore::UserWarning")
    def test_replaces_with_token_for_allowed_caller(self, tmp_path, monkeypatch):
        """Erlaubter Caller mit token-Level ersetzt Koordinaten durch Token."""
        config_dir = _create_test_config(tmp_path)
        
        # Erstelle identity.db mit Salt
        identity_db = config_dir / "identity.db"
        import sqlite3
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
        
        _create_test_location_privacy(tmp_path, {
            "llm": {"default": "none", "allow": {"test_caller": "token"}}
        })
        
        monkeypatch.setattr("health_config.KYORO_CONFIG_DIR", config_dir)
        
        from modules.location_store import filter_prompt_text
        from health_config import load
        load.cache_clear()
        
        text = "Position: 48.123456, 11.543210"
        filtered, count = filter_prompt_text(text, "test_caller")
        
        assert "48.123456" not in filtered
        assert "11.543210" not in filtered
        assert "LOC-" in filtered  # Token-Präfix
        assert count >= 1

    @pytest.mark.filterwarnings("ignore::UserWarning")
    def test_region_level_removes_coordinates(self, tmp_path, monkeypatch):
        """Region-Level entfernt Koordinaten."""
        config_dir = _create_test_config(tmp_path)
        _create_test_location_privacy(tmp_path, {
            "llm": {"default": "none", "allow": {"test_caller": "region"}}
        })
        
        monkeypatch.setattr("health_config.KYORO_CONFIG_DIR", config_dir)
        
        from modules.location_store import filter_prompt_text
        from health_config import load
        load.cache_clear()
        
        text = "Position: 48.123456, 11.543210"
        filtered, count = filter_prompt_text(text, "test_caller")
        
        assert "48.123456" not in filtered
        assert "11.543210" not in filtered
        assert count >= 1

    @pytest.mark.filterwarnings("ignore::UserWarning")
    def test_empty_prompt_returns_empty(self, tmp_path, monkeypatch):
        """Leerer Prompt bleibt leer."""
        config_dir = _create_test_config(tmp_path)
        _create_test_location_privacy(tmp_path)
        
        monkeypatch.setattr("health_config.KYORO_CONFIG_DIR", config_dir)
        
        from modules.location_store import filter_prompt_text
        from health_config import load
        load.cache_clear()
        
        text = ""
        filtered, count = filter_prompt_text(text, "test_caller")
        
        assert filtered == ""
        assert count == 0

    @pytest.mark.filterwarnings("ignore::UserWarning")
    def test_default_caller_uses_default_level(self, tmp_path, monkeypatch):
        """Unbekannter Caller verwendet den Default-Level."""
        config_dir = _create_test_config(tmp_path)
        _create_test_location_privacy(tmp_path, {
            "llm": {"default": "none"}
        })
        
        monkeypatch.setattr("health_config.KYORO_CONFIG_DIR", config_dir)
        
        from modules.location_store import filter_prompt_text
        from health_config import load
        load.cache_clear()
        
        text = "Position: 48.123456, 11.543210"
        filtered, count = filter_prompt_text(text, "unknown_caller")
        
        # Default ist "none" - Koordinaten werden entfernt
        assert "48.123456" not in filtered
        assert "11.543210" not in filtered


class TestForExternalApi:
    """Tests für for_external_api()."""

    @pytest.mark.filterwarnings("ignore::UserWarning")
    def test_uses_default_precision_2(self, tmp_path, monkeypatch):
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

    @pytest.mark.filterwarnings("ignore::UserWarning")
    def test_uses_configured_precision(self, tmp_path, monkeypatch):
        """Verwendet die konfigurierte Präzision."""
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


class TestGetCallerName:
    """Tests für get_caller_name()."""

    def test_explicit_caller(self):
        """Expliziter Caller wird zurückgegeben."""
        from modules.location_store import get_caller_name
        
        result = get_caller_name("my_script")
        assert result == "my_script"

    def test_from_sys_argv(self, monkeypatch):
        """Caller wird aus sys.argv extrahiert."""
        from modules.location_store import get_caller_name
        
        test_args = ["/path/to/my_script.py", "arg1"]
        monkeypatch.setattr("sys.argv", test_args)
        
        result = get_caller_name()
        assert result == "my_script"


class TestStripImageMetadata:
    """Tests für _strip_image_metadata(): Pixel neu kodieren, fail closed."""

    @staticmethod
    def _jpeg_with_gps() -> bytes:
        import io
        from PIL import Image
        img = Image.new("RGB", (8, 8), (120, 60, 30))
        exif = Image.Exif()
        exif[0x010F] = "ExampleCam"                      # Make
        exif[0x8825] = {1: "N", 2: (48.0, 7.0, 24.0)}   # GPS IFD, erfunden
        buf = io.BytesIO()
        img.save(buf, format="JPEG", exif=exif)
        return buf.getvalue()

    def test_removes_exif_and_gps_from_jpeg(self):
        import io
        from PIL import Image
        from modules.llm import _strip_image_metadata

        src = self._jpeg_with_gps()
        assert len(Image.open(io.BytesIO(src)).getexif())  # Vorbedingung

        out, mime = _strip_image_metadata(src, "image/jpeg")
        assert mime == "image/jpeg"
        with Image.open(io.BytesIO(out)) as img:
            assert len(img.getexif()) == 0
            assert img.size == (8, 8)

    def test_rgba_is_sent_as_png_not_failing_open(self):
        import io
        from PIL import Image
        from modules.llm import _strip_image_metadata

        buf = io.BytesIO()
        Image.new("RGBA", (4, 4), (1, 2, 3, 128)).save(buf, format="PNG")
        out, mime = _strip_image_metadata(buf.getvalue(), "image/jpeg")
        assert mime == "image/png"
        with Image.open(io.BytesIO(out)) as img:
            assert img.mode == "RGBA"

    def test_palette_is_kept(self):
        import io
        from PIL import Image
        from modules.llm import _strip_image_metadata

        img = Image.new("P", (4, 4))
        img.putpalette([0, 0, 0, 200, 10, 10] + [0] * (256 * 3 - 6))
        img.putpixel((0, 0), 1)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        out, _ = _strip_image_metadata(buf.getvalue(), "image/png")
        with Image.open(io.BytesIO(out)) as clean:
            assert clean.convert("RGB").getpixel((0, 0)) == (200, 10, 10)

    def test_invalid_image_raises_instead_of_returning_original(self):
        from modules.llm import ImageMetadataError, _strip_image_metadata

        with pytest.raises(ImageMetadataError):
            _strip_image_metadata(b"invalid image data", "image/jpeg")


class _RemoteFake:
    is_local = False
    name = "RemoteFake (stub)"

    def __init__(self):
        self.chat_calls = []
        self.vision_calls = []

    def chat(self, system, user, max_tokens=2000):
        self.chat_calls.append({"system": system, "user": user})
        return "ok"

    def vision(self, image_path, prompt, max_tokens=2000):
        self.vision_calls.append({"bytes": Path(image_path).read_bytes(), "prompt": prompt})
        return "ok"


class TestCallLlmRemote:
    """call_llm mit Cloud-Anbieter: Text gefiltert, Bild bereinigt oder nicht gesendet."""

    @pytest.mark.filterwarnings("ignore::UserWarning")
    def test_remote_text_is_filtered(self, tmp_path, monkeypatch):
        import modules.llm as llmmod
        config_dir = _create_test_config(tmp_path)
        _create_test_location_privacy(tmp_path)
        monkeypatch.setattr("health_config.KYORO_CONFIG_DIR", config_dir)
        fake = _RemoteFake()
        monkeypatch.setattr(llmmod, "_text_provider", lambda: fake)

        llmmod.call_llm("Lauf bei 48.123456, 11.543210", system="Kontext 48.12345, 11.54321",
                        require_grounding=False, label_output=False, caller="test_caller")

        assert "48.123456" not in fake.chat_calls[0]["user"]
        assert "48.12345" not in fake.chat_calls[0]["system"]

    def test_unknown_provider_counts_as_remote(self, monkeypatch):
        import modules.llm as llmmod

        class _NoFlag:
            name = "NoFlag"
            def vision(self, *a, **k):  # pragma: no cover - darf nicht aufgerufen werden
                raise AssertionError("image must not be sent")

        monkeypatch.setattr(llmmod, "_vision_provider", lambda: _NoFlag())
        b64 = __import__("base64").standard_b64encode(b"not an image").decode()
        with pytest.raises(llmmod.ImageMetadataError):
            llmmod.call_llm("Bild", image_b64=b64)

    def test_remote_image_is_sent_without_exif(self, monkeypatch):
        import base64
        import io
        from PIL import Image
        import modules.llm as llmmod

        fake = _RemoteFake()
        monkeypatch.setattr(llmmod, "_vision_provider", lambda: fake)
        src = TestStripImageMetadata._jpeg_with_gps()
        llmmod.call_llm("Bild", image_b64=base64.standard_b64encode(src).decode(),
                        caller="test_caller", label_output=False)

        sent = fake.vision_calls[0]["bytes"]
        assert len(Image.open(io.BytesIO(sent)).getexif()) == 0
