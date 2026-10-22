# SPDX-License-Identifier: GPL-3.0-or-later
"""
Scoring of the post-infectious differential (vermute_syndrome()) and the
extended symptom catalog (symptoms_extended) in the syndrome profiles.

Background: the symptom score used a linear IDF (n_syndromes / symptom_in_n),
so a profile symptom found in only one profile counted ~100x as much as a
common one. With synonym matching, a single diary entry that reached such a
name ("Schnupfen" -> "Nasenlaufen", only in rsv.json) moved that syndrome to
the top of the ranking. The score now uses log-IDF divided by sqrt(profile
size), scaled by _SYMPTOM_SCORE_SCALE so the other boosts keep their weight.
symptoms_extended (post_covid: Davis 2021) is context only and must not
change the ranking.
"""
import json
import math
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

from modules.symptom_synonyms import canonicalize  # noqa: E402

SYNDROMES_DIR = Path(__file__).parent.parent.parent / "scripts" / "analysis" / "syndromes"


@pytest.fixture
def diag(monkeypatch):
    import analysis.infectious.analyse_postinfectious_diagnose as m
    def open_med(*a, **k):
        # vermute_syndrome() closes the connection, so a fresh one per call
        med = sqlite3.connect(":memory:")
        med.execute("CREATE TABLE lab_manual (parameter, wert, wert_num, ref_max, status, date)")
        return med
    monkeypatch.setattr(m, "open_medicine_db", open_med)
    # No personal exposure events or lifestyle data in the unit test
    monkeypatch.setattr(m, "_EXPOSURE_BOOSTS", {})
    monkeypatch.setattr(m, "_lifestyle_boost_for_slug", lambda slug: 0.0)
    return m


def _conn(*entries):
    c = sqlite3.connect(":memory:")
    c.execute("CREATE TABLE symptoms (date TEXT, symptom TEXT)")
    c.executemany("INSERT INTO symptoms VALUES (?, ?)", entries)
    return c


def _ranking(diag, conn):
    return {r["slug"]: r for r in diag.vermute_syndrome(conn, "2025-12-01", "2026-02-01")}


def _n_syndromes(diag):
    return sum(1 for s in diag.SYNDROME_CODES if s != "generic")


def test_symptom_found_in_one_profile_is_damped(diag):
    profil = canonicalize(diag.SYNDROME_CODES["rsv"]["symptoms"])
    assert "Nasenlaufen" in profil
    r = _ranking(diag, _conn(("2026-01-01", "Schnupfen")))["rsv"]
    assert dict(r["matched"]) == {"Nasenlaufen": 1}
    n = _n_syndromes(diag)
    expected = (diag._SYMPTOM_SCORE_SCALE * (1 + math.log(n)) * (1 + 0.1)
                / math.sqrt(len(profil)))
    assert r["score"] == pytest.approx(expected, abs=3.0)  # small fixed boosts allowed
    # Linear IDF gave this single entry a weight of n (> 100)
    assert r["score"] < n


def test_long_profiles_get_no_advantage_from_size_alone(diag):
    # Same matched symptom, same days: one match covers less of a longer
    # profile, so the longer profile scores lower (linear IDF: equal).
    conn = _conn(("2026-01-01", "Fatigue"))
    ranking = _ranking(diag, conn)
    with_fatigue = {slug: r for slug, r in ranking.items()
                    if dict(r["matched"]) == {"Fatigue": 1}}
    sizes = {slug: len(canonicalize(diag.SYNDROME_CODES[slug]["symptoms"]))
             for slug in with_fatigue}
    longest, shortest = max(sizes, key=sizes.get), min(sizes, key=sizes.get)
    assert sizes[longest] > sizes[shortest]
    assert with_fatigue[longest]["score"] < with_fatigue[shortest]["score"]


def test_extended_catalog_does_not_change_ranking(diag, monkeypatch):
    conn = _conn(("2026-01-01", "Fatigue"), ("2026-01-01", "Nachtschweiß"),
                 ("2026-01-02", "Geruchsverlust"))
    before = {s: r["score"] for s, r in _ranking(diag, conn).items()}
    codes = {k: dict(v) for k, v in diag.SYNDROME_CODES.items()}
    for v in codes.values():
        v["symptoms_extended"] = []
    monkeypatch.setattr(diag, "SYNDROME_CODES", codes)
    after = {s: r["score"] for s, r in _ranking(diag, conn).items()}
    assert before == after


def test_extended_catalog_matches_are_listed_separately(diag):
    conn = _conn(("2026-01-01", "Nachtschweiß"), ("2026-01-02", "Nachtschweiß"),
                 ("2026-01-01", "Fatigue"))
    res = diag.load_symptoms_syndrom(conn, "2025-12-01", "2026-02-01")
    assert dict(res["treffer"]) == {"Fatigue": 1}
    erweitert = {s: (n, e["system"]) for s, n, e in res["treffer_erweitert"]}
    assert erweitert == {"Nachtschweiß": (2, "Systemisch")}


def test_post_covid_extended_catalog_is_well_formed():
    rec = json.loads((SYNDROMES_DIR / "post_covid.json").read_text(encoding="utf-8"))
    ext = rec["symptoms_extended"]
    assert "10.1016/j.eclinm.2021.101019" in rec["symptoms_extended_source"]
    names = [e["name"] for e in ext]
    assert len(names) == len(set(names))
    for e in ext:
        assert set(e) == {"name", "en", "system", "prevalence_pct"}
        assert e["prevalence_pct"] is None or 0 <= e["prevalence_pct"] <= 100
    # The core profile stays short; the catalog is the long list
    assert len(rec["symptoms"]) < 25 < len(ext)


def test_post_covid_core_profile_matches_its_derivation():
    """The core profile is derived from Davis 2021 Table S24 (month 7 >= 30 %,
    plus orthostatic intolerance); symptoms_core_derivation documents it.
    Adding or removing a core symptom without updating the derivation fails."""
    rec = json.loads((SYNDROMES_DIR / "post_covid.json").read_text(encoding="utf-8"))
    deriv = rec["symptoms_core_derivation"]
    derived = {e["name"] for e in deriv["core"]} | set(deriv["aliases_in_core"])
    assert set(rec["symptoms"]) == derived
    for e in deriv["core"]:
        if e["month7_pct"] is not None and e["month7_pct"] < 30:
            assert e.get("note"), f"{e['name']} below 30 % needs a reason"
    removed = {e["name"] for e in deriv["removed_from_previous_core"]}
    assert not removed & set(rec["symptoms"])
