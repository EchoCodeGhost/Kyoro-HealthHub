# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Tests that import_skin stores a photo location only with a real capture date.

@tier        unit
@purpose.de  Prüft, dass import_skin.import_photo() den GPS-Fund nur dann an
             location_store.record() übergibt, wenn ein Aufnahmedatum bekannt
             ist (EXIF-Datum oder --date), und dass ein EXIF-Datum nur ohne
             --date übernommen wird.
@purpose.en  Checks that import_skin.import_photo() passes the GPS finding to
             location_store.record() only when a capture date is known (EXIF
             date or --date), and that an EXIF date is used only without
             --date.
@method.de   In-Memory-Tabellen, gemockte Bildverarbeitung und gemocktes
             record(), erfundene Koordinaten.
@method.en   In-memory tables, mocked image processing and mocked record(),
             made-up coordinates.
@reads       (nichts)
@writes      (temporäre Dateien)
@limits.de   Prüft nicht die Metadaten-Bereinigung selbst.
@limits.en   Does not check metadata stripping itself.
"""

import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

GPS = (48.12345, 11.54321)


@pytest.fixture
def skin(tmp_path, monkeypatch):
    import importers.import_skin as skin
    import modules.location_store as location_store

    monkeypatch.setattr(skin, "SKIN_DIR", tmp_path / "skin")
    (tmp_path / "skin").mkdir()
    calls = []
    monkeypatch.setattr(location_store, "record", lambda **kw: calls.append(kw) or True)
    return skin, calls


def _run(skin, tmp_path, monkeypatch, exif_dt, photo_date, date_given):
    src = tmp_path / "in.jpg"
    src.write_bytes(b"jpeg")

    def _fake_normalize(path, tmp_dir):
        out = Path(tmp_dir) / "norm.jpg"
        out.write_bytes(b"jpeg")
        return out, exif_dt, GPS

    monkeypatch.setattr(skin, "normalize_to_jpeg", _fake_normalize)
    conn = sqlite3.connect(":memory:")
    conn.execute("""CREATE TABLE imaging_files (id INTEGER PRIMARY KEY, person, file_path,
        original_format, acquisition_date, modality, body_part, source_type, lesion_id,
        raw_file_path, image_type, ts_import)""")
    conn.execute("CREATE TABLE skin_lesions (id INTEGER PRIMARY KEY, last_checked)")
    conn.execute("INSERT INTO skin_lesions (id) VALUES (1)")
    skin.import_photo(conn, src, 1, photo_date, "camera", date_given=date_given)
    return conn


def test_no_capture_date_stores_no_location(skin, tmp_path, monkeypatch):
    mod, calls = skin
    _run(mod, tmp_path, monkeypatch, exif_dt=None, photo_date="2026-01-05", date_given=False)
    assert calls == []


def test_exif_date_is_used_without_explicit_date(skin, tmp_path, monkeypatch):
    mod, calls = skin
    conn = _run(mod, tmp_path, monkeypatch, exif_dt="2026-01-01",
                photo_date="2026-01-05", date_given=False)
    assert [c["date"] for c in calls] == ["2026-01-01"]
    assert conn.execute("SELECT acquisition_date FROM imaging_files").fetchone()[0] == "2026-01-01"


def test_explicit_date_wins_over_exif(skin, tmp_path, monkeypatch):
    mod, calls = skin
    _run(mod, tmp_path, monkeypatch, exif_dt="2026-01-01", photo_date="2026-01-05", date_given=True)
    assert [c["date"] for c in calls] == ["2026-01-05"]
    assert calls[0]["ref_table"] == "imaging_files"


def test_explicit_date_without_exif_stores_location(skin, tmp_path, monkeypatch):
    mod, calls = skin
    _run(mod, tmp_path, monkeypatch, exif_dt=None, photo_date="2026-01-05", date_given=True)
    assert len(calls) == 1
