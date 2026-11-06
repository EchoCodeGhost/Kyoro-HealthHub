# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Tests for the worldwide ISO 3166 region lookup.

@tier        unit
@purpose.de  Prüft region_of und region_name gegen die mitgelieferten
             Natural-Earth-Grenzen: Städte in verschiedenen Ländern, Inseln
             getrennt vom Festland, Küstenregel, offenes Meer, ungültige Eingaben.
@purpose.en  Checks region_of and region_name against the bundled Natural
             Earth boundaries: towns in several countries, islands separate
             from the mainland, coastal rule, open sea, invalid input.
@method.de   Öffentlich bekannte Stadtkoordinaten (Stadtzentren), keine
             personenbezogenen Orte.
@method.en   Publicly known town coordinates (town centres), no personal places.
@reads       scripts/modules/geodata/admin1.json.gz
@writes      (nichts)
@limits.de   Stichproben, keine vollständige Prüfung aller Grenzen.
@limits.en   Samples, not a full check of all boundaries.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))


@pytest.mark.parametrize("lat, lon, expected", [
    (49.79, 9.95, "DE-BY"),      # Würzburg (früher fälschlich Baden-Württemberg)
    (49.97, 9.15, "DE-BY"),      # Aschaffenburg
    (52.52, 13.40, "DE-BE"),     # Berlin
    (47.56, 7.59, "CH-BS"),      # Basel
    (28.12, -15.43, "ES-GC"),    # Las Palmas de Gran Canaria
    (39.57, 2.65, "ES-PM"),      # Palma
    (21.31, -157.86, "US-HI"),   # Honolulu
    (32.65, -16.91, "PT-30"),    # Funchal
])
def test_towns(lat, lon, expected):
    from modules.location_store import region_of
    assert region_of(lat, lon) == expected


def test_salzburg_is_austrian():
    from modules.location_store import region_of
    assert region_of(47.80, 13.04).startswith("AT-")


def test_islands_are_not_the_mainland():
    from modules.location_store import region_of
    assert region_of(28.12, -15.43) != region_of(40.42, -3.70)  # Las Palmas vs. Madrid
    assert region_of(39.57, 2.65) != region_of(40.42, -3.70)


def test_point_just_off_the_coast():
    from modules.region_lookup import _get_index, lookup
    from shapely import Point
    # Helgoland liegt in der vereinfachten Küstenlinie knapp außerhalb jedes Polygons
    point = Point(7.89, 54.18)
    assert not len(_get_index().tree.query(point, predicate="intersects"))
    assert lookup(54.18, 7.89) == "DE-SH"


def test_open_sea():
    from modules.location_store import region_of
    assert region_of(28.12345, -14.12345) == "XX"
    assert region_of(54.5, 6.5) == "XX"


@pytest.mark.parametrize("lat, lon", [
    (None, None), ("abc", 1), (95.0, 0.0), (0.0, 181.0), (float("nan"), 1.0),
])
def test_invalid_input(lat, lon):
    from modules.location_store import region_of
    assert region_of(lat, lon) == "XX"


def test_no_placeholder_codes_in_data():
    from modules.region_lookup import _get_index
    for unit in _get_index().units:
        code = unit["code"]
        assert "~" not in code and not code.startswith("-"), code
        assert code == "XX" or code[:2].isalpha()


def test_region_name_languages():
    from modules.i18n import get_lang, set_lang
    from modules.location_store import region_name
    previous = get_lang()
    try:
        set_lang("de")
        assert region_name("DE-BY") == "Bayern"
        set_lang("en")
        assert region_name("DE-BY") == "Bavaria"
    finally:
        set_lang(previous)
    assert region_name("ZZ-QQ") == "ZZ-QQ"
    assert region_name("XX") == "XX"
