# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Tests that import_fundus and import_fibricheck store no location.

@tier        unit
@purpose.de  Prüft, dass ein Fundusfoto mit GPS-EXIF und ein FibriCheck-PDF mit
             GPS-Fund keinen Eintrag in location.db oder photo_locations
             erzeugen und das abgelegte Fundusbild kein GPS mehr enthält.
@purpose.en  Checks that a fundus photo with GPS EXIF and a FibriCheck PDF with
             a GPS finding create no entry in location.db or photo_locations,
             and that the stored fundus image no longer carries GPS.
@method.de   Ablageordner und Datenbanken werden auf tmp_path umgelenkt; der
             Import muss erfolgreich laufen (kein Abfangen von Fehlern).
@method.en   Storage folders and databases are redirected to tmp_path; the
             import has to succeed (no swallowing of errors).
@reads       (temporäre Dateien)
@writes      (temporäre Dateien)
@limits.de   Nur erfundene Koordinaten (48.12345, 11.54321). Für FibriCheck
             wird die PDF-Bereinigung durch einen Stub ersetzt, der einen
             GPS-Fund meldet, wie ihn ein eingebettetes Foto liefern würde.
@limits.en   Made-up coordinates only (48.12345, 11.54321). For FibriCheck the
             PDF scrubber is replaced by a stub that reports a GPS finding, as
             an embedded photo would.
"""

import sqlite3
import sys
from pathlib import Path

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

_GPS_IFD = 0x8825
_FAKE_GPS = {1: "N", 2: (48.0, 7.0, 24.42), 3: "E", 4: (11.0, 32.0, 35.56)}


@pytest.fixture
def location_db(tmp_path, monkeypatch):
    """Lenkt location.db auf tmp_path um und zählt record()-Aufrufe."""
    import modules.location_store as ls

    path = tmp_path / "location.db"
    monkeypatch.setattr(ls, "open_location_db", lambda *a, **k: sqlite3.connect(path))
    calls = []
    real_record = ls.record

    def _spy(*args, **kwargs):
        calls.append((args, kwargs))
        return real_record(*args, **kwargs)

    monkeypatch.setattr(ls, "record", _spy)
    return path, calls


def _gps_jpeg(path: Path) -> Path:
    exif = Image.Exif()
    exif[_GPS_IFD] = _FAKE_GPS
    Image.new("RGB", (64, 64), (120, 60, 30)).save(path, "JPEG", exif=exif)
    assert Image.open(path).getexif().get_ifd(_GPS_IFD), "test input must carry GPS"
    return path


class TestFundus:
    def test_geotagged_jpeg_stores_no_location(self, tmp_path, monkeypatch, location_db):
        import importers.import_fundus as fundus
        from utils.create_medicine_imaging_schema import SCHEMA, _migrate

        imaging_db = tmp_path / "medicine_imaging.db"
        conn = sqlite3.connect(imaging_db)
        conn.executescript(SCHEMA)
        _migrate(conn)
        conn.commit()
        conn.close()

        monkeypatch.setattr(fundus, "FUNDUS_DIR", tmp_path / "fundus")
        monkeypatch.setattr(fundus, "ANALYSES_DIR", tmp_path / "analyses")
        monkeypatch.setattr(fundus, "open_medicine_imaging_db",
                            lambda *a, **k: sqlite3.connect(imaging_db))
        monkeypatch.setattr(fundus, "ensure_imaging_schema", lambda *a, **k: None)

        src = _gps_jpeg(tmp_path / "input.jpg")
        assert fundus.run([str(src)], person="PER-00000000") == 1

        stored = list((tmp_path / "fundus").glob("*.jpg"))
        assert len(stored) == 1
        assert not Image.open(stored[0]).getexif().get_ifd(_GPS_IFD)

        loc_path, calls = location_db
        assert calls == []
        assert not loc_path.exists()


class TestFibriCheck:
    _REPORT = (
        "Herzrhythmusmessung durchgeführt am: 2026-01-01 10:00\n"
        "Ihr Herzrhythmus war regelmäßig. Sie meldeten KEINE SYMPTOME.\n"
        "Der Durchschnitt beträgt 70 Schläge pro Minute.\n"
    )

    def test_gps_finding_in_pdf_stores_no_location(self, tmp_path, monkeypatch, location_db):
        import importers.import_fibricheck as fc
        from utils.create_schema import SCHEMA

        pdf = tmp_path / "report.pdf"
        pdf.write_bytes(b"%PDF-1.4 synthetic")

        def _scrub_stub(src, dst, **kwargs):
            Path(dst).write_bytes(Path(src).read_bytes())
            return 1, [{"date": "2026-01-01", "gps": (48.12345, 11.54321)}]

        monkeypatch.setattr(fc, "PDF_DIR", tmp_path / "fibricheck")
        monkeypatch.setattr(fc, "ORIGINALE_DIR", tmp_path / "fibricheck" / "originals")
        monkeypatch.setattr(fc, "_extract_text", lambda p: self._REPORT)
        monkeypatch.setattr(fc, "_scrub_pdf_metadata", _scrub_stub)

        conn = sqlite3.connect(tmp_path / "health.db")
        conn.executescript(SCHEMA)
        result = fc.run(conn, pdf, person="PER-00000000")

        assert result.rows_inserted == 1
        assert (tmp_path / "fibricheck" / "originals" / "report.pdf").exists()
        assert conn.execute("SELECT COUNT(*) FROM photo_locations").fetchone()[0] == 0
        conn.close()

        loc_path, calls = location_db
        assert calls == []
        assert not loc_path.exists()
