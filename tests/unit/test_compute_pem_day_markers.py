# SPDX-License-Identifier: GPL-3.0-or-later
"""
Day markers "Ruhetag", "PEM" and "Crashtag" in compute/compute_pem.py.

Background: the activity-drop block scored any drop in steps after an
exertion day as a reaction, so a deliberate rest day (pacing, weather,
plans) counted like a forced reduction. The person can now mark the day:
"Ruhetag" sets the activity-drop points to 0, "PEM" counts as a symptom
signal (+12), "Crashtag" as a strong one (+20) and wins over "Ruhetag".
Only these exact words, only as a whole entry.

Unit tests for the helpers plus an end-to-end run of main() against an
in-memory DB, like test_compute_pem_oura_bias.py.
"""

import itertools
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

from utils.create_schema import SCHEMA  # noqa: E402
from utils import compat_views  # noqa: E402
import compute.compute_pem as pem  # noqa: E402


# ── _collect_day_markers ─────────────────────────────────────────────────────

def test_markers_only_as_whole_entry_from_all_sources():
    markers, rest_notes = pem._collect_day_markers(
        symptom_rows=[
            ("2026-07-01", "Crashtag", 1, None, None, None, "kyoro_st"),
            ("2026-07-02", "Fatigue", 5, None, "PEM", None, "symptomtagebuch"),
            ("2026-07-03", "Fatigue", 5, None, "kein Ruhetag möglich", None, "symptomtagebuch"),
            ("2026-07-04", "Fatigue", 5, None, "PEM-Score heute hoch", None, "symptomtagebuch"),
        ],
        context_rows=[
            ("2026-07-05", "Ruhetag", None, "oura_api"),
            ("2026-07-05", "Light Exercise", None, "garmin_gdpr"),
            ("2026-07-06", "ruhetag", None, "oura_api"),  # no variants
        ],
        oura_rows=[
            ("2026-07-05", "Ruhetag", None),
            ("2026-07-07", "Pacing", None),
        ],
    )
    assert dict(markers["2026-07-01"]) == {"Crashtag": ["kyoro_st:entry"]}
    assert dict(markers["2026-07-02"]) == {"PEM": ["symptomtagebuch:note"]}
    assert dict(markers["2026-07-05"]) == {"Ruhetag": ["oura_api:tag", "oura_tags:tag"]}
    for date in ("2026-07-03", "2026-07-04", "2026-07-06", "2026-07-07"):
        assert date not in markers, date
    # Free text and non-marker tags only become a hint
    assert {"2026-07-03", "2026-07-06", "2026-07-07"} <= rest_notes
    assert "2026-07-04" not in rest_notes  # "PEM-Score" is no rest/pacing keyword


def test_boolean_marker_set_to_false_does_not_count():
    markers, _ = pem._collect_day_markers(
        [("2026-07-01", "Crashtag", None, "false", None, None, "kyoro_st"),
         ("2026-07-02", "Crashtag", 0, None, None, None, "kyoro_st")], [], [])
    assert not markers


def test_symptomtrack_crash_field_counts_only_when_true():
    # pem_crash_tag is SymptomTrack's binary "Crash-Tag" field; the companion
    # user_context entry with the same name only carries the note.
    markers, rest_notes = pem._collect_day_markers(
        [("2026-07-01", "pem_crash_tag", None, "true", None, None, "kyoro_st"),
         ("2026-07-02", "pem_crash_tag", None, "false", None, None, "kyoro_st")],
        [("2026-07-02", "pem_crash_tag", "Ich glaube nicht", "kyoro_st")], [])
    assert dict(markers["2026-07-01"]) == {"Crashtag": ["kyoro_st:pem_crash_tag"]}
    assert "2026-07-02" not in markers and "2026-07-02" not in rest_notes


def test_rest_note_pattern_respects_word_boundaries():
    assert pem.REST_NOTE_PATTERN.search("heute Regen, drinnen geblieben")
    assert not pem.REST_NOTE_PATTERN.search("sport_regeneration")
    assert not pem.REST_NOTE_PATTERN.search("anregend")


# ── _apply_marker_symptoms / _activity_drop_points ───────────────────────────

def test_marker_symptom_value_takes_the_higher_not_the_sum():
    symptom_d = {"2026-07-01": 8.0, "2026-07-02": 2.0}
    markers = {"2026-07-01": {"PEM": ["x"]}, "2026-07-02": {"Crashtag": ["x"]},
               "2026-07-03": {"PEM": ["x"]}, "2026-07-04": {"Ruhetag": ["x"]}}
    pem._apply_marker_symptoms(symptom_d, markers)
    assert symptom_d == {"2026-07-01": 8.0, "2026-07-02": 6.0, "2026-07-03": 4.0}


@pytest.mark.parametrize("markers, expected", [
    ({}, (15, 0)),
    ({"Ruhetag": ["x"]}, (0, 1)),
    ({"Ruhetag": ["x"], "PEM": ["x"]}, (0, 1)),
    ({"Ruhetag": ["x"], "Crashtag": ["x"]}, (15, 0)),
])
def test_activity_drop_points(markers, expected):
    assert pem._activity_drop_points(75.0, markers) == expected


def test_rest_day_without_scoring_drop_is_not_marked_suppressed():
    assert pem._activity_drop_points(10.0, {"Ruhetag": ["x"]}) == (0, 0)


# ── End to end: main() on an in-memory DB ────────────────────────────────────

_db_counter = itertools.count()
PERSON = "PER-test"
TRIGGER_DAY = "2026-07-08"
NEXT_DAY = "2026-07-09"


def _fresh_conn():
    uri = f"file:compute_pem_markers_test_{next(_db_counter)}?mode=memory&cache=shared"
    conn = sqlite3.connect(uri, uri=True)
    conn.executescript(SCHEMA)
    compat_views.apply(conn)
    conn.executescript("""
        CREATE TABLE daily_stress (
            date TEXT NOT NULL, person TEXT NOT NULL DEFAULT 'unknown',
            resting_hr REAL, rmssd_ms REAL, hrv_sdnn_ms REAL,
            sleep_quality REAL, sleep_hours REAL, steps INTEGER,
            training_load REAL, stress_score REAL, source TEXT,
            PRIMARY KEY (date, person)
        );
    """)
    # 7 days at 8000 steps, the trigger day, then 2000 steps (-75 %)
    for day in range(1, 9):
        conn.execute("INSERT INTO daily_stress (date, person, steps) VALUES (?, ?, 8000)",
                     (f"2026-07-{day:02d}", PERSON))
    conn.execute("INSERT INTO daily_stress (date, person, steps) VALUES (?, ?, 2000)",
                 (NEXT_DAY, PERSON))
    conn.commit()
    return conn, uri


def _run(conn, uri, monkeypatch, markers=()):
    for m in markers:
        conn.execute("INSERT INTO user_context (id, date, person, source, tag) "
                     "VALUES (?, ?, ?, 'oura_api', ?)",
                     (f"test_{NEXT_DAY}_{m}", NEXT_DAY, PERSON, m))
    conn.commit()
    monkeypatch.setattr(pem, "open_db", lambda: sqlite3.connect(uri, uri=True))
    monkeypatch.setattr(sys, "argv", ["compute_pem.py", "--person", PERSON,
                                      "--date-from", "2026-07-01", "--date-to", TRIGGER_DAY])
    pem.main()
    return conn.execute("""
        SELECT react_score, react_activity_drop, react_activity_suppressed
        FROM pem_evidence_scores WHERE person=? AND date=?
    """, (PERSON, TRIGGER_DAY)).fetchone()


def test_end_to_end_without_marker_counts_the_drop(monkeypatch):
    conn, uri = _fresh_conn()
    react, drop, suppressed = _run(conn, uri, monkeypatch)
    assert drop == pytest.approx(75.0)
    assert react == 15 and suppressed == 0


def test_end_to_end_ruhetag_suppresses_only_the_drop(monkeypatch):
    conn, uri = _fresh_conn()
    react, drop, suppressed = _run(conn, uri, monkeypatch, ["Ruhetag"])
    assert drop == pytest.approx(75.0)  # value kept, points not
    assert react == 0 and suppressed == 1


def test_end_to_end_ruhetag_and_pem_keeps_the_symptom_signal(monkeypatch):
    conn, uri = _fresh_conn()
    react, _, suppressed = _run(conn, uri, monkeypatch, ["Ruhetag", "PEM"])
    assert react == 12 and suppressed == 1


def test_end_to_end_crashtag_wins_over_ruhetag(monkeypatch):
    conn, uri = _fresh_conn()
    react, _, suppressed = _run(conn, uri, monkeypatch, ["Ruhetag", "Crashtag"])
    assert react == 15 + 20 and suppressed == 0
    marker, source = conn.execute(
        "SELECT day_marker, day_marker_source FROM pem_evidence_scores WHERE person=? AND date=?",
        (PERSON, NEXT_DAY)).fetchone() or (None, None)
    # NEXT_DAY is outside --date-to, so it has no row of its own; the marker
    # still reached the trigger day's reaction window (d1_extended).
    assert marker is None and source is None
