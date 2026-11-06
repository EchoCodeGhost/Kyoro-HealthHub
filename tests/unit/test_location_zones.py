# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Tests for privacy zones in the location registry.

@tier        unit
@purpose.de  Prüft die Privatsphäre-Zonen: Punkte eines Tracks innerhalb einer
             Zone werden weggelassen (Standard) oder mit der Zonen-Genauigkeit
             gespeichert, Punkte außerhalb mit der Genauigkeit der Quelle; der
             Mittelpunkt wird fest, aber mit dem Salz verschoben, und der echte
             Punkt bleibt in der Zone; ausgeschaltete Zonen ändern nichts;
             konfigurierte Orte ohne Koordinaten bekommen keine Zone und werden
             einmal gemeldet; Mittelpunkte landen nie in location.db; das
             Skript apply_privacy_zones wendet die Zonen auf vorher
             gespeicherte Einträge an, ohne genaue Koordinaten ins Audit-Log zu
             kopieren.
@purpose.en  Checks privacy zones: track points inside a zone are dropped
             (default) or stored at the zone precision, points outside at the
             source precision; the centre is shifted by a fixed, salted offset
             and the true point stays inside the zone; disabled zones change
             nothing; configured places without coordinates get no zone and are
             reported once; centres never reach location.db; the
             apply_privacy_zones script applies zones to previously stored
             entries without copying precise coordinates into the audit log.
@method.de   Temporäre location.db, gemockte Konfiguration und gemocktes Salz,
             erfundene Koordinaten (Zentrum 48.12345, 11.54321).
@method.en   Temporary location.db, mocked configuration and salt, made-up
             coordinates (centre 48.12345, 11.54321).
@reads       (temporäre Dateien)
@writes      (temporäre Dateien)
@limits.de   Keine echten Ortsdaten.
@limits.en   No real location data.
"""

import math
import sqlite3
import sys
import warnings
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

PERSON = "PER-00000000"
CENTRE = (48.12345, 11.54321)
INSIDE_START = (48.12360, 11.54340)   # ~20 m vom Zentrum
INSIDE_END = (48.12330, 11.54300)     # ~25 m vom Zentrum
OUTSIDE = (48.15000, 11.60000)        # ~5 km vom Zentrum


def _dist_m(a, b):
    dlat = (a[0] - b[0]) * 111_320
    dlon = (a[1] - b[1]) * 111_320 * math.cos(math.radians(a[0]))
    return math.hypot(dlat, dlon)


@pytest.fixture
def env(tmp_path, monkeypatch):
    import modules.location_store as ls

    path = tmp_path / "location.db"

    def _open(p=None):
        return sqlite3.connect(path)

    state = {
        "policy": {
            "default": {"store": "none"},
            "importers": {"import_tracks": {"*": {"precision": 5}}},
            "zones": {"enabled": True, "radius_m": 500, "zone_precision": 2,
                      "centres": {"Musterort": {"lat": CENTRE[0], "lon": CENTRE[1]}}},
        },
        "places": ([], [], None),
        "salt": "",
    }
    monkeypatch.setattr(ls, "_load_location_privacy", lambda: state["policy"])
    monkeypatch.setattr(ls, "_personal_places", lambda: state["places"])
    monkeypatch.setattr(ls, "_get_pseudonym_salt", lambda: state["salt"])
    monkeypatch.setattr(ls, "open_location_db", _open)
    monkeypatch.setattr(ls, "_missing_centres_warned", False)
    monkeypatch.setattr(ls, "_no_salt_warned", True)
    return ls, path, state


def _record_track(ls, points):
    return [ls.record("import_tracks", ".gpx", lat, lon, f"2026-01-01T10:0{i}:00+00:00",
                      "2026-01-01", source_file="imports/tracks/run.gpx", person=PERSON)
            for i, (lat, lon) in enumerate(points)]


def _rows(path):
    if not path.exists():
        return []
    conn = sqlite3.connect(path)
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE name='location_registry'").fetchone():
        return []
    return conn.execute("SELECT lat, lon, precision FROM location_registry ORDER BY id").fetchall()


def test_track_starting_and_ending_in_zone_is_hidden(env):
    ls, path, _ = env
    assert _record_track(ls, [INSIDE_START, OUTSIDE, INSIDE_END]) == [False, True, False]
    assert _rows(path) == [(48.15, 11.6, 5)]


def test_coarsen_mode(env):
    ls, path, state = env
    state["policy"]["zones"]["inside"] = "coarsen"
    _record_track(ls, [INSIDE_START, OUTSIDE, INSIDE_END])
    # Start und Ende fallen vergröbert in dieselbe Zelle; ts gehört nicht zum
    # Duplikat-Schlüssel, daher bleibt ein Eintrag für die Zone.
    assert _rows(path) == [(48.12, 11.54, 2), (48.15, 11.6, 5)]


def test_unknown_inside_value_falls_back_to_hide(env):
    ls, path, state = env
    state["policy"]["zones"]["inside"] = "blur"
    with pytest.warns(UserWarning):
        _record_track(ls, [INSIDE_START])
    assert _rows(path) == []


def test_zones_disabled_keep_source_precision(env):
    ls, path, state = env
    state["policy"]["zones"]["enabled"] = False
    _record_track(ls, [INSIDE_START, OUTSIDE])
    assert _rows(path) == [(*INSIDE_START, 5), (48.15, 11.6, 5)]


def test_coarser_source_is_not_affected(env):
    ls, path, state = env
    state["policy"]["importers"]["import_tracks"] = {"*": {"precision": 2}}
    _record_track(ls, [INSIDE_START])
    assert _rows(path) == [(48.12, 11.54, 2)]


def test_home_position_is_a_zone_centre(env):
    ls, path, state = env
    state["policy"]["zones"]["centres"] = {}
    state["places"] = ([], [], CENTRE)
    _record_track(ls, [INSIDE_START])
    assert _rows(path) == []


class TestShiftedCentre:
    def test_shift_is_fixed_and_within_half_radius(self, env):
        ls, _, state = env
        state["salt"] = "aa" * 32
        first = ls.zone_centres()
        assert first == ls.zone_centres()
        assert first != [CENTRE]
        assert _dist_m(first[0], CENTRE) <= 250

    def test_shift_depends_on_salt(self, env):
        ls, _, state = env
        state["salt"] = "aa" * 32
        a = ls.zone_centres()
        state["salt"] = "bb" * 32
        assert ls.zone_centres() != a

    def test_true_centre_and_its_surroundings_stay_hidden(self, env):
        ls, path, state = env
        state["salt"] = "aa" * 32
        # Alles bis radius/2 um den echten Punkt liegt in der verschobenen Zone
        ring = [(CENTRE[0] + 240 / 111_320 * math.cos(a),
                 CENTRE[1] + 240 / (111_320 * math.cos(math.radians(CENTRE[0]))) * math.sin(a))
                for a in (k * math.pi / 4 for k in range(8))]
        assert not any(_record_track(ls, [CENTRE, *ring]))
        assert _rows(path) == []

    def test_without_salt_no_shift_and_one_warning(self, env, monkeypatch):
        ls, _, _ = env
        monkeypatch.setattr(ls, "_no_salt_warned", False)
        with pytest.warns(UserWarning):
            assert ls.zone_centres() == [CENTRE]
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            assert ls.zone_centres() == [CENTRE]


def test_place_without_coordinates_gets_no_zone_and_one_warning(env):
    ls, path, state = env
    state["policy"]["zones"]["centres"] = {}
    state["places"] = (["Beispielstadt"], ["Musterweg 1, 12345 Beispieldorf"], None)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        _record_track(ls, [INSIDE_START, INSIDE_END])
    messages = [str(w.message) for w in caught]
    assert len(messages) == 1
    assert "2" in messages[0]
    assert "Beispielstadt" not in messages[0] and "Musterweg" not in messages[0]
    assert [r[2] for r in _rows(path)] == [5, 5]


def test_address_covered_by_its_town_centre(env):
    ls, _, state = env
    state["policy"]["zones"]["centres"] = {"Beispieldorf": {"lat": CENTRE[0], "lon": CENTRE[1]}}
    state["places"] = ([], ["Musterweg 1, 12345 Beispieldorf"], None)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        assert ls._get_centre_coordinates() == [CENTRE]
    assert caught == []


def test_zone_centre_is_never_stored(env):
    ls, path, state = env
    state["policy"]["zones"]["inside"] = "coarsen"
    state["salt"] = "aa" * 32
    _record_track(ls, [INSIDE_START, OUTSIDE])
    stored = {(r[0], r[1]) for r in _rows(path)}
    shifted = ls.zone_centres()[0]
    assert CENTRE not in stored and shifted not in stored


class TestApplyPrivacyZones:
    def _seed(self, ls, path, state, points):
        state["policy"]["zones"]["enabled"] = False
        _record_track(ls, points)
        state["policy"]["zones"]["enabled"] = True
        conn = sqlite3.connect(path)
        from modules.db import _install_audit_log_triggers
        _install_audit_log_triggers(conn)
        conn.commit()
        conn.close()

    def _run(self, ls, monkeypatch, execute):
        import migrations.apply_privacy_zones as apz
        monkeypatch.setattr(apz, "open_location_db", ls.open_location_db)
        return apz.apply_zones(execute=execute)

    def _audit(self, path):
        conn = sqlite3.connect(path)
        audit = " ".join(str(r) for r in conn.execute("SELECT old_data, new_data FROM audit_log"))
        triggers = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='trigger'")}
        return audit, triggers

    def test_dry_run_changes_nothing(self, env, monkeypatch):
        ls, path, state = env
        self._seed(ls, path, state, [INSIDE_START, OUTSIDE])
        stats = self._run(ls, monkeypatch, execute=False)
        assert stats["location_registry:in_zone"] == 1 and stats["location_registry:checked"] == 2
        assert len(_rows(path)) == 2

    def test_execute_hides_without_audit_copy(self, env, monkeypatch):
        ls, path, state = env
        self._seed(ls, path, state, [INSIDE_START, OUTSIDE])
        stats = self._run(ls, monkeypatch, execute=True)
        assert stats["location_registry:deleted"] == 1
        assert _rows(path) == [(48.15, 11.6, 5)]
        audit, triggers = self._audit(path)
        assert "48.1236" not in audit and "privacy_zones" in audit
        assert {"_audit_location_registry_update", "_audit_location_registry_delete"} <= triggers

    def test_execute_coarsens_and_merges(self, env, monkeypatch):
        ls, path, state = env
        state["policy"]["zones"]["inside"] = "coarsen"
        self._seed(ls, path, state, [INSIDE_START, INSIDE_END, OUTSIDE])
        stats = self._run(ls, monkeypatch, execute=True)
        assert stats["location_registry:coarsened"] == 1 and stats["location_registry:merged"] == 1
        assert _rows(path) == [(48.12, 11.54, 2), (48.15, 11.6, 5)]
        audit, _ = self._audit(path)
        assert "48.1236" not in audit and "48.1233" not in audit
