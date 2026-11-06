# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Tests for tools/build_region_data.py on a tiny synthetic input.

@tier        unit
@purpose.de  Prüft Code-Bereinigung, Flächenberechnung, Ausgabeformat und
             Prüfsummen-Abbruch des Bauwerkzeugs für die Grenzdatei.
@purpose.en  Checks code cleanup, area computation, output format and the
             checksum abort of the boundary-file build tool.
@method.de   Zwei erfundene Quadrate als GeoJSON; keine Netzwerkzugriffe.
@method.en   Two made-up squares as GeoJSON; no network access.
@reads       (temporäre Dateien)
@writes      (temporäre Dateien)
@limits.de   Prüft nicht die echte Natural-Earth-Datei.
@limits.en   Does not check the real Natural Earth file.
"""

import gzip
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "tools"))

import build_region_data as brd


@pytest.mark.parametrize("iso, a2, expected", [
    ("DE-BY", "DE", "DE-BY"),
    ("XK-X02~", "XK", "XK"),
    ("-99-X11~", "-1", "XX"),
    ("", "FR", "FR"),
    (None, None, "XX"),
    ("SY-X01~", "SY", "SY"),
])
def test_clean_code(iso, a2, expected):
    assert brd.clean_code(iso, a2) == expected


def _square(lon, lat, size):
    return {"type": "Polygon", "coordinates": [[
        [lon, lat], [lon + size, lat], [lon + size, lat + size], [lon, lat + size], [lon, lat]]]}


def test_area_of_one_degree_square_at_equator():
    # 1° × 1° am Äquator ≈ 111.2 km × 110.6 km
    area = brd.geometry_area_km2(_square(0.0, 0.0, 1.0))
    assert 12_200 < area < 12_400


def test_hole_is_subtracted():
    outer = _square(0.0, 0.0, 1.0)["coordinates"][0]
    hole = _square(0.25, 0.25, 0.5)["coordinates"][0]
    full = brd.geometry_area_km2({"type": "Polygon", "coordinates": [outer]})
    holed = brd.geometry_area_km2({"type": "Polygon", "coordinates": [outer, hole]})
    assert holed == pytest.approx(full * 0.75, rel=0.01)


def _features():
    return [
        {"type": "Feature",
         "properties": {"iso_3166_2": "QQ-AA", "iso_a2": "QQ", "name": "Alpha",
                        "name_de": "Alpha-DE", "name_en": "Alpha-EN"},
         "geometry": _square(10.0, 10.0, 1.0)},
        {"type": "Feature",
         "properties": {"iso_3166_2": "QQ-X01~", "iso_a2": "QQ", "name": "Beta",
                        "name_de": None, "name_en": None},
         "geometry": _square(12.0, 10.0, 1.0)},
    ]


def test_build_units_shape():
    units = brd.build_units(_features())
    assert [u["code"] for u in units] == ["QQ-AA", "QQ"]
    assert units[0]["name_de"] == "Alpha-DE" and units[0]["name_en"] == "Alpha-EN"
    assert units[1]["name_de"] == "Beta" and units[1]["name_en"] == "Beta"
    assert all(u["country"] == "QQ" for u in units)
    assert units[0]["area_km2"] > 10_000
    assert units[0]["geometry"]["type"] == "Polygon"


def test_main_checks_checksum_and_writes_gzip(tmp_path, monkeypatch):
    source = tmp_path / "src.geojson"
    source.write_text(json.dumps({"type": "FeatureCollection", "features": _features()}))
    out = tmp_path / "out.json.gz"

    assert brd.main(["--source", str(source), "--output", str(out)]) == 1
    assert not out.exists()

    monkeypatch.setattr(brd, "NE_SHA256", brd._sha256(source))
    assert brd.main(["--source", str(source), "--output", str(out)]) == 0
    payload = json.loads(gzip.decompress(out.read_bytes()))
    assert len(payload["units"]) == 2
    first = out.read_bytes()
    brd.main(["--source", str(source), "--output", str(out)])
    assert out.read_bytes() == first  # byte-gleich bei gleicher Eingabe
