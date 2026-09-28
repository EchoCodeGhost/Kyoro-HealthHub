# SPDX-License-Identifier: GPL-3.0-or-later
"""Unit test for modules/geo_bundesland.py."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

from modules.geo_bundesland import nearest_bundesland, BUNDESLAENDER


def test_all_16_bundeslaender_present():
    assert len(BUNDESLAENDER) == 16
    names = {b[0] for b in BUNDESLAENDER}
    codes = {b[1] for b in BUNDESLAENDER}
    assert len(names) == 16  # no duplicate names
    assert len(codes) == 16  # no duplicate codes


def test_nearest_bundesland_munich_is_bayern():
    name, code = nearest_bundesland(48.14, 11.58)
    assert (name, code) == ("Bayern", "BY")


def test_nearest_bundesland_duesseldorf_is_nrw():
    name, code = nearest_bundesland(51.23, 6.77)
    assert (name, code) == ("Nordrhein-Westfalen", "NW")


def test_nearest_bundesland_returns_a_known_code():
    name, code = nearest_bundesland(50.0, 10.0)  # somewhere in central Germany
    assert code in {b[1] for b in BUNDESLAENDER}
