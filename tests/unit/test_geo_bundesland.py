# SPDX-License-Identifier: GPL-3.0-or-later
"""Unit test for modules/geo_bundesland.py."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

from modules.geo_bundesland import BUNDESLAENDER, bundesland_of


def test_all_16_bundeslaender_present():
    assert len(BUNDESLAENDER) == 16
    names = {b[0] for b in BUNDESLAENDER}
    codes = {b[1] for b in BUNDESLAENDER}
    assert len(names) == 16  # no duplicate names
    assert len(codes) == 16  # no duplicate codes


@pytest.mark.parametrize("lat, lon, expected", [
    (48.14, 11.58, ("Bayern", "BY")),                 # München
    (51.23, 6.77, ("Nordrhein-Westfalen", "NW")),     # Düsseldorf
    (49.79, 9.95, ("Bayern", "BY")),                  # Würzburg (per Zentroid früher BW)
    (52.52, 13.40, ("Berlin", "BE")),
    (54.09, 12.13, ("Mecklenburg-Vorpommern", "MV")), # Rostock
    (50.98, 11.03, ("Thueringen", "TH")),             # Erfurt, RKI-Schreibweise
])
def test_bundesland_of(lat, lon, expected):
    assert bundesland_of(lat, lon) == expected


@pytest.mark.parametrize("lat, lon", [
    (47.80, 13.04),   # Salzburg
    (47.56, 7.59),    # Basel
    (28.12, -15.43),  # Las Palmas
    (None, None),
])
def test_outside_germany_is_none(lat, lon):
    assert bundesland_of(lat, lon) is None
