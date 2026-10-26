# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Tests for location_store safety properties and the photo_locations migration.

@tier        unit
@purpose.de  Prüft Salt-Pflicht der Ort-Tokens, Regionsbestimmung, Anlage
             des Schemas, Duplikat-Schutz bei NULL-Feldern und die Migration
             aus photo_locations.
@purpose.en  Checks the salt requirement for location tokens, region lookup,
             schema creation, duplicate protection with NULL fields and the
             migration from photo_locations.
@method.de   Temporäre identity.db/location.db/health.db, erfundene Koordinaten.
@method.en   Temporary identity.db/location.db/health.db, made-up coordinates.
@reads       (temporäre Dateien)
@writes      (temporäre Dateien)
@limits.de   Nur synthetische Koordinaten (48.12345, 11.54321 …)
@limits.en   Synthetic coordinates only (48.12345, 11.54321 …)
"""

import json
import sqlite3
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))


def _setup(tmp_path, monkeypatch, privacy=None, salt="test_salt_hex"):
    config_dir = tmp_path / "cfg"
    config_dir.mkdir()
    policy = {
        "default": {"store": "none"},
        "importers": {"import_skin": {"*": {"precision": 2}}},
        "zones": {"enabled": False},
        "external_api": {"precision": 2},
        "llm": {"default": "none", "allow": {"tok_caller": "token"}},
    }
    if privacy:
        policy.update(privacy)
    (config_dir / "location_privacy.json").write_text(json.dumps(policy))
    if salt is not None:
        conn = sqlite3.connect(config_dir / "identity.db")
        conn.execute("CREATE TABLE pseudonym_salt (id INTEGER PRIMARY KEY CHECK (id = 1), "
                     "salt_hex TEXT NOT NULL)")
        conn.execute("INSERT INTO pseudonym_salt VALUES (1, ?)", (salt,))
        conn.commit()
        conn.close()
    monkeypatch.setattr("health_config.KYORO_CONFIG_DIR", config_dir)
    return config_dir


def _loc_db(tmp_path):
    path = tmp_path / "data" / "location.db"

    def _open(p=None):
        path.parent.mkdir(parents=True, exist_ok=True)
        return sqlite3.connect(path)
    return path, _open


class TestTokenSalt:
    def test_token_uses_identity_db_salt(self, tmp_path, monkeypatch):
        _setup(tmp_path, monkeypatch, salt="aa" * 32)
        from modules.location_store import location_token
        t1 = location_token(48.12345, 11.54321, 2)
        assert t1.startswith("LOC-") and len(t1) == 12

        other = tmp_path / "other"
        other.mkdir()
        _setup(other, monkeypatch, salt="bb" * 32)
        t2 = location_token(48.12345, 11.54321, 2)
        assert t1 != t2  # anderer Salt → anderes Token

    def test_no_salt_no_token(self, tmp_path, monkeypatch):
        _setup(tmp_path, monkeypatch, salt=None)
        from modules.location_store import location_token
        assert location_token(48.12345, 11.54321, 2) is None

    def test_token_level_without_salt_removes_coordinates(self, tmp_path, monkeypatch):
        _setup(tmp_path, monkeypatch, salt=None)
        from modules.location_store import COORDINATE_PLACEHOLDER, filter_prompt_text
        out, n = filter_prompt_text("Start 48.123456, 11.543210", "tok_caller")
        assert "48.12" not in out and "LOC-" not in out
        assert COORDINATE_PLACEHOLDER in out and n >= 1


class TestRegion:
    def test_inside_germany(self):
        from modules.location_store import region_of
        assert region_of(48.12345, 11.54321) == "Bayern"

    def test_outside_germany(self):
        from modules.location_store import region_of
        assert region_of(28.12345, -14.12345) in ("Ausland", "Abroad")

    def test_invalid(self):
        from modules.location_store import region_of
        assert region_of(None, None) in ("Unbekannt", "Unknown")


class TestRecordSchemaAndDuplicates:
    def test_record_creates_schema_on_fresh_db(self, tmp_path, monkeypatch):
        _setup(tmp_path, monkeypatch)
        path, opener = _loc_db(tmp_path)
        from modules.location_store import record
        with patch("modules.location_store.open_location_db", opener):
            assert record("import_skin", ".jpg", 48.123456, 11.543210, None,
                          "2026-01-01", person="PER-00000000")
        rows = sqlite3.connect(path).execute(
            "SELECT lat, lon, precision FROM location_registry").fetchall()
        assert rows == [(48.12, 11.54, 2)]

    def test_reimport_with_null_fields_is_deduplicated(self, tmp_path, monkeypatch):
        _setup(tmp_path, monkeypatch)
        path, opener = _loc_db(tmp_path)
        from modules.location_store import record
        with patch("modules.location_store.open_location_db", opener):
            for ts in ("2026-01-01T10:00:00+00:00", "2026-02-01T10:00:00+00:00"):
                record("import_skin", ".jpg", 48.123456, 11.543210, ts,
                       "2026-01-01", person="PER-00000000")
        n = sqlite3.connect(path).execute("SELECT COUNT(*) FROM location_registry").fetchone()[0]
        assert n == 1

    def test_policy_none_writes_nothing(self, tmp_path, monkeypatch):
        _setup(tmp_path, monkeypatch)
        path, opener = _loc_db(tmp_path)
        from modules.location_store import record
        with patch("modules.location_store.open_location_db", opener):
            assert not record("import_lab_results", ".pdf", 48.1, 11.5, None,
                              "2026-01-01", person="PER-00000000")
        assert not path.exists()


class TestPhotoLocationsMigration:
    def _health_db(self, tmp_path):
        path = tmp_path / "health.db"
        conn = sqlite3.connect(path)
        conn.execute("""CREATE TABLE photo_locations (
            date TEXT NOT NULL, lat REAL NOT NULL, lon REAL NOT NULL,
            source TEXT NOT NULL, person TEXT NOT NULL DEFAULT 'unknown',
            PRIMARY KEY (date, lat, lon, source))""")
        # Audit-Trigger wie in modules.db, damit der Test die Umgehung prüft
        conn.execute("""CREATE TABLE audit_log (id INTEGER PRIMARY KEY, ts TEXT,
            table_name TEXT, operation TEXT, old_data TEXT, new_data TEXT)""")
        conn.execute("""CREATE TRIGGER _audit_photo_locations_delete
            AFTER DELETE ON photo_locations BEGIN
            INSERT INTO audit_log (ts, table_name, operation, old_data, new_data)
            VALUES ('t', 'photo_locations', 'DELETE',
                    json_object('lat', OLD.lat, 'lon', OLD.lon), NULL); END""")
        conn.executemany("INSERT INTO photo_locations VALUES (?, ?, ?, ?, ?)", [
            ("2026-01-01", 48.12, 11.54, "import_skin", "PER-00000000"),
            ("2026-01-02", 48.13, 11.55, "import_lab_results", "PER-00000000"),
        ])
        conn.commit()
        conn.close()
        return path

    def _run(self, tmp_path, monkeypatch, execute):
        _setup(tmp_path, monkeypatch)
        health = self._health_db(tmp_path) if not (tmp_path / "health.db").exists() \
            else tmp_path / "health.db"
        loc_path, opener = _loc_db(tmp_path)
        import migrations.migrate_photo_locations_to_registry as mig
        with patch.object(mig, "open_db", lambda: sqlite3.connect(health)), \
             patch("modules.location_store.open_location_db", opener):
            stats = mig.migrate(execute=execute)
        return stats, health, loc_path

    def test_dry_run_writes_nothing(self, tmp_path, monkeypatch):
        stats, health, loc_path = self._run(tmp_path, monkeypatch, execute=False)
        assert stats["total"] == 2 and stats["migrated"] == 1 and stats["discarded"] == 1
        assert not loc_path.exists()
        assert sqlite3.connect(health).execute(
            "SELECT COUNT(*) FROM photo_locations").fetchone()[0] == 2

    def test_execute_moves_and_clears_health_db(self, tmp_path, monkeypatch):
        stats, health, loc_path = self._run(tmp_path, monkeypatch, execute=True)
        assert stats["migrated"] == 1 and stats["discarded"] == 1 and stats["failed"] == 0
        assert sqlite3.connect(health).execute(
            "SELECT COUNT(*) FROM photo_locations").fetchone()[0] == 0
        rows = sqlite3.connect(loc_path).execute(
            "SELECT importer, migrated_from, source_file, ts FROM location_registry").fetchall()
        assert rows == [("import_skin", "photo_locations", None, None)]
        audit = sqlite3.connect(health).execute("SELECT old_data FROM audit_log").fetchall()
        assert len(audit) == 1
        assert "lat" not in audit[0][0] and "48." not in audit[0][0]

    def test_dry_run_output_has_no_coordinates(self, tmp_path, monkeypatch, capsys):
        _setup(tmp_path, monkeypatch)
        health = self._health_db(tmp_path)
        import migrations.migrate_photo_locations_to_registry as mig
        with patch.object(mig, "open_db", lambda: sqlite3.connect(health)), \
             patch.object(sys, "argv", ["migrate_photo_locations_to_registry.py"]):
            mig.main()
        out = capsys.readouterr().out
        assert "48.1" not in out and "11.5" not in out
