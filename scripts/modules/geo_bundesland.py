# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
geo_bundesland.py — Deutsche Bundesländer: Namen, ISO-Codes, Zuordnung von Koordinaten

@tier        infrastructure
@purpose.de  Kanonische Liste der 16 deutschen Bundesländer (Name in der
             Schreibweise der RKI-Datensätze, ISO-3166-2-Code) und Zuordnung
             von Koordinaten zum Bundesland, für RKI- und AMELAG-Serien.
@purpose.en  Canonical list of the 16 German federal states (name as spelled
             in RKI datasets, ISO 3166-2 code) and assignment of coordinates
             to a federal state, for RKI and AMELAG series.
@method.de   Die Zuordnung nutzt die weltweite Regionssuche
             (modules/region_lookup.py, Natural-Earth-Grenzen). Punkte außerhalb
             Deutschlands ergeben None statt eines benachbarten Bundeslands.
@method.en   Assignment uses the worldwide region lookup
             (modules/region_lookup.py, Natural Earth boundaries). Points
             outside Germany give None instead of a neighbouring state.
@reads       scripts/modules/geodata/admin1.json.gz (über region_lookup)
@writes      Keine Tabellen (statische Daten)
@limits.de   Grenzen auf ~2 km vereinfacht, die Quelle selbst ist an Grenzen
             auf etwa 1–2 km genau: Orte direkt an einer Landes- oder
             Staatsgrenze können der Nachbareinheit zugeordnet werden.
@limits.en   Borders simplified to ~2 km and the source itself is accurate to
             about 1–2 km at borders: places right at a state or national
             border can be assigned to the neighbouring unit.

@relevance.de  Ermöglicht geographische Funktionen, essentiell für die räumliche Analyse
@relevance.en  Enables geographical functions, essential for spatial analysis
@usage
    from modules.geo_bundesland import bundesland_of
    bundesland_of(48.14, 11.58)  # -> ("Bayern", "BY")
    bundesland_of(47.80, 13.04)  # -> None (Österreich)
"""

# (Name — wie in RKI-Datensätzen z.B. ARE-Konsultationsinzidenz verwendet,
#  ISO-3166-2-Code ohne "DE-" — wie in AMELAG-Einzelstandortdaten verwendet)
BUNDESLAENDER: list[tuple[str, str]] = [
    ("Baden-Wuerttemberg",      "BW"),
    ("Bayern",                  "BY"),
    ("Berlin",                  "BE"),
    ("Brandenburg",             "BB"),
    ("Bremen",                  "HB"),
    ("Hamburg",                 "HH"),
    ("Hessen",                  "HE"),
    ("Mecklenburg-Vorpommern",  "MV"),
    ("Niedersachsen",           "NI"),
    ("Nordrhein-Westfalen",     "NW"),
    ("Rheinland-Pfalz",         "RP"),
    ("Saarland",                "SL"),
    ("Sachsen",                 "SN"),
    ("Sachsen-Anhalt",          "ST"),
    ("Schleswig-Holstein",      "SH"),
    ("Thueringen",              "TH"),
]

_NAME_BY_CODE = {code: name for name, code in BUNDESLAENDER}


def bundesland_of(lat, lon) -> tuple[str, str] | None:
    """Bundesland an den Koordinaten als (Name, Code), z.B. ("Bayern", "BY").

    None, wenn der Punkt nicht in Deutschland liegt oder ungültig ist.
    """
    from modules.region_lookup import lookup
    region = lookup(lat, lon)
    if not region.startswith("DE-"):
        return None
    code = region[3:]
    name = _NAME_BY_CODE.get(code)
    return (name, code) if name else None
