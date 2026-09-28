# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
geo_bundesland.py — Deutsche Bundesländer: Namen, ISO-Codes, Zentroid-Koordinaten

@tier        infrastructure
@purpose.de  Kanonische Liste der 16 deutschen Bundesländer (Name, ISO-3166-2-Code,
             ungefähre Zentroid-Koordinaten) plus Zuordnung von Heimatkoordinaten
             zum nächstgelegenen Bundesland — analog zu _nearest_region in
             import_pollen_dwd.py, aber für Bundesland-Ebene statt DWD-Teilregionen.
@purpose.en  Canonical list of the 16 German federal states (name, ISO 3166-2
             code, approximate centroid coordinates) plus mapping from home
             coordinates to the nearest federal state — analogous to
             _nearest_region in import_pollen_dwd.py, but at federal-state
             level instead of DWD sub-regions.
@method.de   Euklidische Distanz zu Landeshauptstadt-Koordinaten (ausreichend
             genau für eine Bundesland-Zuordnung, kein echtes Polygon-Matching).
@method.en   Euclidean distance to state-capital coordinates (accurate enough
             for federal-state assignment, not real polygon matching).
@reads       Keine Tabellen (statische Daten)
@writes      Keine Tabellen (statische Daten)
@limits.de   Grenznahe Koordinaten können dem falschen Nachbar-Bundesland
             zugeordnet werden (Zentroid-Näherung, keine Polygongrenzen).

@relevance.de  Ermöglicht geographische Funktionen, essentiell für die räumliche Analyse
@relevance.en  Enables geographical functions, essential for spatial analysis
@limits.en   Coordinates near a state border can be assigned to the wrong
             neighboring state (centroid approximation, no polygon borders).
@usage
    from modules.geo_bundesland import nearest_bundesland
    name, code = nearest_bundesland(48.14, 11.58)  # -> ("Bayern", "BY")
"""

import math

# (Name — wie in RKI-Datensätzen z.B. ARE-Konsultationsinzidenz verwendet,
#  ISO-3166-2-Code — wie in AMELAG-Einzelstandortdaten verwendet,
#  Zentroid-Breitengrad, Zentroid-Längengrad)
BUNDESLAENDER: list[tuple[str, str, float, float]] = [
    ("Baden-Wuerttemberg",      "BW", 48.78,  9.18),
    ("Bayern",                  "BY", 48.14, 11.58),
    ("Berlin",                  "BE", 52.52, 13.40),
    ("Brandenburg",             "BB", 52.40, 13.06),
    ("Bremen",                  "HB", 53.08,  8.80),
    ("Hamburg",                 "HH", 53.55, 10.00),
    ("Hessen",                  "HE", 50.08,  8.24),
    ("Mecklenburg-Vorpommern",  "MV", 53.63, 11.41),
    ("Niedersachsen",           "NI", 52.37,  9.73),
    ("Nordrhein-Westfalen",     "NW", 51.23,  6.77),
    ("Rheinland-Pfalz",         "RP", 49.99,  8.27),
    ("Saarland",                "SL", 49.24,  6.99),
    ("Sachsen",                 "SN", 51.05, 13.74),
    ("Sachsen-Anhalt",          "ST", 52.13, 11.64),
    ("Schleswig-Holstein",      "SH", 54.32, 10.14),
    ("Thueringen",              "TH", 50.98, 11.03),
]

BUNDESLAND_COORDS_BY_NAME: dict[str, tuple[float, float]] = {
    name: (lat, lon) for name, _code, lat, lon in BUNDESLAENDER
}


def nearest_bundesland(lat: float, lon: float) -> tuple[str, str]:
    """Nächstgelegenes Bundesland zu gegebenen Koordinaten.

    Returns (name, iso_code), z.B. ("Bayern", "BY").
    """
    best = min(BUNDESLAENDER, key=lambda b: math.hypot(lat - b[2], lon - b[3]))
    return best[0], best[1]
