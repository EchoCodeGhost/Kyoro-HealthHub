# SPDX-License-Identifier: GPL-3.0-or-later
"""
Unit test for compute/compute_daily_context.py::_load_travel and
_load_infection_proximity — pure functions, no DB access.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

from compute.compute_daily_context import _load_travel, _load_infection_proximity


class FakeCfg:
    def __init__(self, travel_history=None, events=None):
        self.travel_history = travel_history or []
        self._events = events or []

    def events_of_type(self, *types):
        return [e for e in self._events if e.get("type") in types]


# ── _load_travel ────────────────────────────────────────────────────────────

def test_load_travel_marks_dates_inside_a_trip():
    spine = ["2026-07-04", "2026-07-05", "2026-07-06", "2026-07-07"]
    cfg = FakeCfg(travel_history=[{"date_from": "2026-07-05", "date_to": "2026-07-06"}])

    result = _load_travel(spine, cfg)

    assert result == {
        "2026-07-05": {"travel_active": 1},
        "2026-07-06": {"travel_active": 1},
    }


def test_load_travel_empty_history_returns_empty():
    spine = ["2026-07-04", "2026-07-05"]
    cfg = FakeCfg(travel_history=[])

    assert _load_travel(spine, cfg) == {}


def test_load_travel_ignores_incomplete_trip_entries():
    """A trip missing date_from or date_to must not crash or match anything."""
    spine = ["2026-07-05"]
    cfg = FakeCfg(travel_history=[{"date_from": "2026-07-05"}, {"date_to": "2026-07-05"}])

    assert _load_travel(spine, cfg) == {}


# ── _load_infection_proximity ───────────────────────────────────────────────

def test_infection_proximity_signed_distance_to_nearest_event():
    spine = ["2026-07-01", "2026-07-05", "2026-07-10"]
    cfg = FakeCfg(events=[{"type": "infection", "date": "2026-07-05"}])

    result = _load_infection_proximity(spine, cfg)

    assert result["2026-07-01"] == {"days_since_infection": -4}   # event still ahead
    assert result["2026-07-05"] == {"days_since_infection": 0}
    assert result["2026-07-10"] == {"days_since_infection": 5}    # event in the past


def test_infection_proximity_picks_nearest_of_multiple_events():
    spine = ["2026-07-08"]
    cfg = FakeCfg(events=[
        {"type": "infection", "date": "2026-07-01"},
        {"type": "reinfection", "date": "2026-07-09"},
    ])

    result = _load_infection_proximity(spine, cfg)

    assert result["2026-07-08"] == {"days_since_infection": -1}  # 07-09 is nearer than 07-01


def test_infection_proximity_ignores_non_infection_event_types():
    spine = ["2026-07-05"]
    cfg = FakeCfg(events=[{"type": "diagnosis", "date": "2026-07-05"}])

    assert _load_infection_proximity(spine, cfg) == {}


def test_infection_proximity_no_events_returns_empty():
    spine = ["2026-07-05"]
    cfg = FakeCfg(events=[])

    assert _load_infection_proximity(spine, cfg) == {}
