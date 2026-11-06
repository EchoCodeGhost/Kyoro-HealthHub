#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Build the bundled region boundaries from Natural Earth admin-1.

@tier        infrastructure
@purpose.de  Erzeugt die mitgelieferte Grenzdatei für location_store.region_of
             aus Natural Earth admin-1 (gemeinfrei): ISO-3166-2-Code,
             Ländercode, Namen auf Deutsch und Englisch, Fläche und
             vereinfachte Umrisse, als eine gzip-Datei im Repository.
@purpose.en  Builds the bundled boundary file for location_store.region_of
             from Natural Earth admin-1 (public domain): ISO 3166-2 code,
             country code, German and English names, area and simplified
             outlines, written as one gzip file into the repository.
@method.de   Lädt die festgelegte Natural-Earth-Version, prüft die SHA-256-
             Prüfsumme, ersetzt Platzhalter-Codes (mit "~" oder "-99") durch den
             Ländercode bzw. "XX", berechnet die Fläche auf der Kugel aus den
             unvereinfachten Umrissen, vereinfacht auf 0.02° und rundet die
             Koordinaten auf 3 Stellen.
@method.en   Downloads the pinned Natural Earth release, verifies its SHA-256
             checksum, replaces placeholder codes (containing "~" or "-99") by
             the country code or "XX", computes the area on the sphere from the
             unsimplified outlines, simplifies to 0.02° and rounds coordinates
             to 3 decimals.
@reads       Natural Earth ne_10m_admin_1_states_provinces.geojson (Download oder --source)
@writes      scripts/modules/geodata/admin1.json.gz
@limits.de   Natural Earth zeigt De-facto-Grenzen; umstrittene Gebiete folgen
             dieser Darstellung. Vereinfachung auf ~2 km verschiebt Küsten und
             Grenzen um bis zu diese Strecke. Das Feld area_sqkm der Quelle ist
             leer, daher wird die Fläche selbst berechnet.
@limits.en   Natural Earth shows de-facto boundaries; disputed areas follow that
             depiction. Simplifying to ~2 km moves coasts and borders by up to
             that distance. The source's area_sqkm field is empty, so the area
             is computed here.

@relevance.de  Nur bei Grenzänderungen oder neuer Natural-Earth-Version erneut ausführen
@relevance.en  Re-run only when borders change or Natural Earth publishes a new release
@usage
    python3 tools/build_region_data.py
    python3 tools/build_region_data.py --source /path/to/ne_10m_admin_1_states_provinces.geojson
"""

import argparse
import gzip
import hashlib
import json
import math
import sys
import tempfile
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUTPUT = REPO / "scripts" / "modules" / "geodata" / "admin1.json.gz"

# Festgelegte Quelle: wie eine Version in requirements.txt, kein Changelog.
NE_RELEASE = "v5.1.2"
NE_URL = ("https://raw.githubusercontent.com/nvkelso/natural-earth-vector/"
          f"{NE_RELEASE}/geojson/ne_10m_admin_1_states_provinces.geojson")
NE_SHA256 = "22d0e3ad85eb3e27f17cabf8ba2d50e554fbc27a87796ff891d958185da62fb5"

SIMPLIFY_DEG = 0.02
COORD_DECIMALS = 3
UNKNOWN = "XX"
EARTH_RADIUS_KM = 6371.0088


def clean_code(iso_3166_2: str | None, iso_a2: str | None) -> str:
    """ISO-3166-2-Code oder, bei Platzhaltern, Ländercode bzw. XX (D3)."""
    country = (iso_a2 or "").strip().upper()
    if len(country) != 2 or not country.isalpha():
        country = UNKNOWN
    code = (iso_3166_2 or "").strip()
    if not code or "~" in code or code.startswith("-"):
        return country
    prefix, _, sub = code.partition("-")
    if len(prefix) != 2 or not prefix.isalpha() or not sub:
        return country
    return code


def _ring_area_km2(ring) -> float:
    """Fläche eines Rings auf der Kugel (Lon/Lat in Grad), ohne Vorzeichen."""
    n = len(ring)
    if n < 3:
        return 0.0
    total = 0.0
    for i in range(n):
        lon1, lat1 = ring[i][:2]
        lon2, lat2 = ring[(i + 1) % n][:2]
        total += math.radians(lon2 - lon1) * (
            2 + math.sin(math.radians(lat1)) + math.sin(math.radians(lat2)))
    return abs(total) * EARTH_RADIUS_KM ** 2 / 2


def geometry_area_km2(geometry: dict) -> float:
    """Fläche einer GeoJSON-Polygon/MultiPolygon-Geometrie in km² (Löcher abgezogen)."""
    if geometry["type"] == "Polygon":
        polygons = [geometry["coordinates"]]
    elif geometry["type"] == "MultiPolygon":
        polygons = geometry["coordinates"]
    else:
        return 0.0
    area = 0.0
    for rings in polygons:
        if not rings:
            continue
        area += _ring_area_km2(rings[0])
        area -= sum(_ring_area_km2(hole) for hole in rings[1:])
    return max(area, 0.0)


def _round_coords(obj, decimals: int):
    if isinstance(obj, (list, tuple)):
        if obj and isinstance(obj[0], (int, float)):
            return [round(float(v), decimals) for v in obj[:2]]
        return [_round_coords(v, decimals) for v in obj]
    return obj


def simplify_geometry(geometry: dict) -> dict | None:
    """Vereinfacht und rundet eine Geometrie; None, wenn nichts übrig bleibt."""
    from shapely import make_valid
    from shapely.geometry import mapping, shape

    geom = shape(geometry).simplify(SIMPLIFY_DEG, preserve_topology=True)
    rounded = shape({"type": geom.geom_type,
                     "coordinates": _round_coords(mapping(geom)["coordinates"], COORD_DECIMALS)})
    if not rounded.is_valid:
        rounded = make_valid(rounded)
    # make_valid kann eine GeometryCollection liefern; nur Flächen behalten
    if rounded.geom_type == "GeometryCollection":
        from shapely.geometry import MultiPolygon
        parts = []
        for part in rounded.geoms:
            if part.geom_type == "Polygon":
                parts.append(part)
            elif part.geom_type == "MultiPolygon":
                parts.extend(part.geoms)
        rounded = MultiPolygon(parts) if parts else None
    if rounded is None or rounded.is_empty or rounded.geom_type not in ("Polygon", "MultiPolygon"):
        return None
    return {"type": rounded.geom_type,
            "coordinates": _round_coords(mapping(rounded)["coordinates"], COORD_DECIMALS)}


def build_units(features: list[dict]) -> list[dict]:
    """Wandelt Natural-Earth-Features in die gebündelte Einheiten-Liste um."""
    units = []
    for feature in features:
        props = feature.get("properties") or {}
        geometry = feature.get("geometry")
        if not geometry:
            continue
        code = clean_code(props.get("iso_3166_2"), props.get("iso_a2"))
        country = code.split("-", 1)[0]
        simplified = simplify_geometry(geometry)
        if simplified is None:
            continue
        name = props.get("name") or code
        units.append({
            "code": code,
            "country": country,
            "name_de": props.get("name_de") or name,
            "name_en": props.get("name_en") or name,
            "area_km2": round(geometry_area_km2(geometry), 1),
            "geometry": simplified,
        })
    return units


def write_output(units: list[dict], path: Path, source_label: str) -> None:
    payload = {
        "source": source_label,
        "licence": "Public domain (Natural Earth)",
        "simplify_deg": SIMPLIFY_DEG,
        "units": units,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    # mtime=0: gleiche Eingabe ergibt byte-gleiche Datei
    with open(path, "wb") as fh, gzip.GzipFile(fileobj=fh, mode="wb", mtime=0,
                                                compresslevel=9) as gz:
        gz.write(raw)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("--source", type=Path,
                        help="local copy of the Natural Earth GeoJSON instead of downloading")
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args(argv)

    with tempfile.TemporaryDirectory() as tmp:
        source = args.source
        if source is None:
            source = Path(tmp) / "admin1.geojson"
            print(f"Download {NE_URL}")
            urllib.request.urlretrieve(NE_URL, source)
        checksum = _sha256(source)
        if checksum != NE_SHA256:
            print(f"Checksum mismatch: {checksum} != {NE_SHA256}", file=sys.stderr)
            return 1
        with open(source, encoding="utf-8") as fh:
            features = json.load(fh)["features"]

    units = build_units(features)
    write_output(units, args.output, f"Natural Earth {NE_RELEASE} ne_10m_admin_1_states_provinces")
    size_mb = args.output.stat().st_size / 1e6
    print(f"{len(units)} units -> {args.output} ({size_mb:.2f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
