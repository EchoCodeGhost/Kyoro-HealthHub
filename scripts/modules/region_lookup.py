# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
region_lookup.py — Offline ISO 3166 region for coordinates, worldwide

@tier        infrastructure
@purpose.de  Ordnet Koordinaten offline der ersten Verwaltungsebene zu
             (ISO 3166-2, z.B. DE-BY, ES-GC, US-HI) und liefert deren Namen
             und Fläche. Grundlage für location_store.region_of.
@purpose.en  Maps coordinates offline to the first administrative level
             (ISO 3166-2, e.g. DE-BY, ES-GC, US-HI) and returns its names and
             area. Basis for location_store.region_of.
@method.de   Lädt die mitgelieferte Datei geodata/admin1.json.gz (Natural Earth,
             vereinfacht, erzeugt von tools/build_region_data.py) beim ersten
             Aufruf und sucht über einen STRtree (shapely) die Einheit, die den
             Punkt enthält. Liegt der Punkt in keiner Einheit, gilt die
             nächste Einheit bis 5 km Entfernung (Küsten, kleine Inseln).
@method.en   Loads the bundled file geodata/admin1.json.gz (Natural Earth,
             simplified, built by tools/build_region_data.py) on first use and
             finds the unit containing the point via an STRtree (shapely). If
             the point lies in no unit, the nearest unit within 5 km counts
             (coasts, small islands).
@reads       scripts/modules/geodata/admin1.json.gz
@writes      (nichts)
@limits.de   Umrisse auf ~2 km vereinfacht: an Grenzen kann ein Punkt bis zu
             dieser Strecke der Nachbareinheit zugeordnet werden. De-facto-Grenzen
             nach Natural Earth; umstrittene Gebiete folgen dieser Darstellung.
             In manchen Ländern ist die erste Ebene klein (Basel-Stadt, Paris),
             dort entspricht die Region fast dem Ort.
@limits.en   Outlines simplified to ~2 km: near borders a point can be assigned
             to the neighbouring unit within that distance. De-facto boundaries
             as in Natural Earth; disputed areas follow that depiction. In some
             countries the first level is small (Basel-Stadt, Paris); there the
             region nearly equals the town.

@relevance.de  Liefert die Stufe "region" der Ortsdaten-Policy weltweit statt nur für Deutschland
@relevance.en  Provides the "region" level of the location policy worldwide, not only for Germany
@usage
    from modules.region_lookup import lookup, unit_info
    code = lookup(49.79, 9.95)          # -> "DE-BY"
    info = unit_info("DE-BY")           # -> {"name_de": "Bayern", ...}
"""

import gzip
import json
import math
import threading
from pathlib import Path

DATA_FILE = Path(__file__).resolve().parent / "geodata" / "admin1.json.gz"
UNKNOWN = "XX"
COAST_TOLERANCE_KM = 5.0
_EARTH_RADIUS_KM = 6371.0088
_KM_PER_DEG_LAT = 111.32

_lock = threading.Lock()
_index = None


class _Index:
    def __init__(self, path: Path):
        from shapely import STRtree
        from shapely.geometry import shape

        with gzip.open(path, "rt", encoding="utf-8") as fh:
            payload = json.load(fh)
        self.units = payload["units"]
        self.geoms = [shape(u["geometry"]) for u in self.units]
        self.tree = STRtree(self.geoms)
        self.info = {}
        for unit in self.units:
            # Ländercodes und XX stehen für Einheiten ohne gültigen Code und
            # fassen Unverwandtes zusammen: kein Name, keine Fläche dafür.
            if "-" not in unit["code"]:
                continue
            # Mehrere Polygone können sich einen Code teilen (D3);
            # Flächen werden addiert, Namen vom ersten Eintrag.
            entry = self.info.setdefault(unit["code"], {
                "code": unit["code"],
                "country": unit["country"],
                "name_de": unit["name_de"],
                "name_en": unit["name_en"],
                "area_km2": 0.0,
            })
            entry["area_km2"] += unit["area_km2"]


def _get_index() -> _Index:
    global _index
    if _index is None:
        with _lock:
            if _index is None:
                _index = _Index(DATA_FILE)
    return _index


def _haversine_km(lat1, lon1, lat2, lon2) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * _EARTH_RADIUS_KM * math.asin(math.sqrt(min(1.0, a)))


def _valid_point(lat, lon) -> tuple[float, float] | None:
    try:
        lat_f, lon_f = float(lat), float(lon)
    except (TypeError, ValueError):
        return None
    if not (math.isfinite(lat_f) and math.isfinite(lon_f)):
        return None
    if not (-90.0 <= lat_f <= 90.0 and -180.0 <= lon_f <= 180.0):
        return None
    return lat_f, lon_f


def lookup(lat, lon) -> str:
    """ISO-3166-2-Code der Einheit am Punkt, Ländercode als Ersatz, sonst XX."""
    point_ll = _valid_point(lat, lon)
    if point_ll is None:
        return UNKNOWN
    lat_f, lon_f = point_ll
    from shapely import Point
    from shapely.ops import nearest_points

    idx = _get_index()
    point = Point(lon_f, lat_f)
    hits = idx.tree.query(point, predicate="intersects")
    if len(hits):
        # Bei Überlappung (Vereinfachung) die kleinste Einheit nehmen
        best = min(hits, key=lambda i: idx.units[i]["area_km2"])
        return idx.units[best]["code"]

    # Küstenregel: Suchradius in Grad großzügig aus 5 km ableiten,
    # die echte Entfernung danach auf der Kugel prüfen.
    cos_lat = max(math.cos(math.radians(lat_f)), 0.01)
    radius_deg = COAST_TOLERANCE_KM / (_KM_PER_DEG_LAT * cos_lat)
    candidates = idx.tree.query(point.buffer(radius_deg))
    best_code, best_km = UNKNOWN, COAST_TOLERANCE_KM
    for i in candidates:
        nearest = nearest_points(idx.geoms[i], point)[0]
        dist = _haversine_km(lat_f, lon_f, nearest.y, nearest.x)
        if dist <= best_km:
            best_code, best_km = idx.units[i]["code"], dist
    return best_code


def unit_info(code: str) -> dict | None:
    """Name (de/en), Ländercode und Fläche für einen Code; None wenn unbekannt.

    Reine Ländercodes (z.B. "FR") und "XX" haben keinen Eintrag.
    """
    if not code:
        return None
    return _get_index().info.get(code)
