# SPDX-License-Identifier: GPL-3.0-or-later
"""
Tests for modules/symptom_synonyms.py and its use in
analysis/infectious/analyse_postinfectious_diagnose.py.

Before this, symptom matching between diary entries and syndrome profiles was
exact on the name: "Myalgie" in a profile never matched "Muskelschmerzen" in
the diary, and a profile listing both "PEM" and "Post-Exertionelle Malaise"
counted the same symptom twice.
"""

import json
import sqlite3

import pytest

from modules import symptom_synonyms as syn
from modules.symptom_synonyms import canonical_symptoms, canonicalize, count_symptom_days


def canonical_symptom(name):
    """Single canonical name (helper for the 1:1 cases)."""
    (only,) = canonical_symptoms(name)
    return only


def _data():
    return json.loads(syn._SYNONYMS_FILE.read_text(encoding="utf-8"))


def _groups():
    return _data()["groups"]


def test_every_name_belongs_to_exactly_one_group():
    seen: dict[str, str] = {}
    for group in _groups():
        for name in [group["canonical"], *group["variants"]]:
            key = syn._key(name)
            assert key not in seen, f"{name!r} in {group['canonical']!r} and {seen[key]!r}"
            seen[key] = group["canonical"]
    for entry in _data()["combined"]:
        key = syn._key(entry["name"])
        assert key not in seen, f"combined {entry['name']!r} also in group {seen[key]!r}"
        seen[key] = entry["name"]


def test_combined_targets_are_stable_canonical_names():
    for entry in _data()["combined"]:
        assert len(entry["maps_to"]) >= 2
        for target in entry["maps_to"]:
            assert canonical_symptoms(target) == {target}, target


def test_canonical_names_map_to_themselves():
    for group in _groups():
        assert canonical_symptom(group["canonical"]) == group["canonical"]


@pytest.mark.parametrize("variant, canonical", [
    ("Myalgie", "Muskelschmerzen"),
    ("Arthralgie", "Gelenkschmerzen"),
    ("PEM", "Post-Exertionelle Malaise"),
    ("Tachykardie", "Herzrasen"),
    ("Erschöpfung", "Fatigue"),
    ("Atemnot", "Kurzatmigkeit"),
    ("headache", "Kopfschmerzen"),
    # combined/odd spellings from config/symptom_map.json (diary vocabulary)
    ("Erschöpfung/Fatigue", "Fatigue"),
    ("PEM-Crashes", "Post-Exertionelle Malaise"),
    ("POTS-Symptomatik", "Orthostatische Intoleranz"),
    ("Atemnot (physiologisch)", "Kurzatmigkeit"),
    ("Trockenes Auge", "Trockene Augen"),
])
def test_known_variants(variant, canonical):
    assert canonical_symptom(variant) == canonical


def test_matching_ignores_case_whitespace_and_dash_variants():
    assert canonical_symptom("  myalgie ") == "Muskelschmerzen"
    assert canonical_symptom("Post–Exertionelle   Malaise") == "Post-Exertionelle Malaise"


def test_related_but_different_symptoms_stay_separate():
    assert canonical_symptom("Herzklopfen") != canonical_symptom("Herzrasen")
    assert canonical_symptom("Herzstolpern") == "Herzstolpern"


def test_unknown_names_pass_through_stripped():
    assert canonical_symptom(" Eigenes Symptom ") == "Eigenes Symptom"
    assert canonical_symptoms("") == frozenset()


def test_combined_diary_entries_match_several_profile_symptoms():
    assert canonical_symptoms("Brainfog/Konzentrationsstörungen") == {"Brain Fog", "Konzentrationsstörungen"}
    assert canonical_symptoms("Kribbeln/Taubheit") == {"Parästhesien", "Taubheitsgefühl"}


def test_ambiguous_diary_entry_maps_only_to_milder_symptom():
    # "Ohnmacht/Benommenheit" does not say whether a real syncope happened.
    assert canonical_symptoms("Ohnmacht/Benommenheit") == {"Schwindel"}


def test_raw_diary_names_go_through_symptom_map(monkeypatch):
    # raw app label -> symptom_map canonical -> synonym group
    monkeypatch.setattr(syn, "_raw_map", lambda: {"tired all the time": "Erschöpfung/Fatigue",
                                                   "eigene app-bezeichnung": "Eigenes Symptom"})
    assert canonical_symptom("Tired all the time") == "Fatigue"
    assert canonical_symptom("eigene App-Bezeichnung") == "Eigenes Symptom"


def test_canonicalize_removes_synonym_duplicates():
    assert canonicalize(["PEM", "Post-Exertionelle Malaise", "Tachykardie", "Herzrasen"]) == {
        "Post-Exertionelle Malaise", "Herzrasen"}


def test_count_symptom_days_counts_distinct_dates_per_canonical_name():
    rows = [
        ("Myalgie", "2026-01-01"),
        ("Muskelschmerzen", "2026-01-01"),  # same day, synonym -> counts once
        ("Muskelschmerzen", "2026-01-02"),
        ("Erschöpfung", "2026-01-01"),
        ("Erschöpfung/Fatigue", "2026-01-02"),
        ("Brainfog/Konzentrationsstörungen", "2026-01-02"),
        ("", "2026-01-03"),
    ]
    assert count_symptom_days(rows) == {"Muskelschmerzen": 2, "Fatigue": 2,
                                        "Brain Fog": 1, "Konzentrationsstörungen": 1}


# ── Integration with the post-infectious differential ────────────────────────

@pytest.fixture
def diag(monkeypatch):
    import analysis.infectious.analyse_postinfectious_diagnose as m
    med = sqlite3.connect(":memory:")
    med.execute("CREATE TABLE lab_manual (parameter, wert, wert_num, ref_max, status, date)")
    monkeypatch.setattr(m, "open_medicine_db", lambda *a, **k: med)
    return m


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.execute("CREATE TABLE symptoms (date TEXT, symptom TEXT)")
    for day in ("2026-01-01", "2026-01-02"):
        c.execute("INSERT INTO symptoms VALUES (?, ?)", (day, "Myalgie"))
        c.execute("INSERT INTO symptoms VALUES (?, ?)", (day, "Muskelschmerzen"))
    c.execute("INSERT INTO symptoms VALUES (?, ?)", ("2026-01-01", "Erschöpfung"))
    c.execute("INSERT INTO symptoms VALUES (?, ?)", ("2026-01-02", "Brainfog/Konzentrationsstörungen"))
    return c


def test_load_symptoms_syndrom_matches_synonyms(diag, conn):
    res = diag.load_symptoms_syndrom(conn, "2025-12-01", "2026-02-01")
    assert dict(res["treffer"]) == {"Muskelschmerzen": 2, "Fatigue": 1,
                                    "Brain Fog": 1, "Konzentrationsstörungen": 1}
    # post_covid lists both spellings of PEM and of tachycardia; each counts once
    assert "PEM" not in res["syndrom_symptome"]
    assert "Tachykardie" not in res["syndrom_symptome"]
    # every match is a profile symptom, so the report's "not documented" list stays consistent
    assert {s for s, _ in res["treffer"]} <= set(res["syndrom_symptome"])


def test_vermute_syndrome_matches_diary_synonyms_against_profiles(diag, conn):
    ranking = diag.vermute_syndrome(conn, "2025-12-01", "2026-02-01")
    by_slug = {r["slug"]: r for r in ranking}
    # anaplasmose lists "Muskelschmerzen" and "Myalgie": one symptom, matched once with 2 days
    matched = dict(by_slug["anaplasmose"]["matched"])
    assert matched == {"Muskelschmerzen": 2, "Fatigue": 1, "Konzentrationsstörungen": 1}


# ── Shared mapping for the other analyses (raw_symptom_names, FATIGUE_LIKE) ──

def test_raw_symptom_names_finds_all_spellings_in_the_table():
    c = sqlite3.connect(":memory:")
    c.execute("CREATE TABLE symptoms (date TEXT, symptom TEXT)")
    c.executemany("INSERT INTO symptoms VALUES ('2026-01-01', ?)", [
        ("erschoepfung_fatigue",), ("Erschöpfung/Fatigue",), ("Fatigue",), ("PEM",),
        ("Sprachliche Erschöpfung",), ("Energie-Budget Morgens",), (None,),
    ])
    assert syn.raw_symptom_names(c, syn.FATIGUE_LIKE) == [
        "Erschöpfung/Fatigue", "Fatigue", "PEM", "erschoepfung_fatigue"]
    assert syn.raw_symptom_names(c, ["Kopfschmerzen"]) == []


def test_fatigue_like_excludes_other_exhaustion_and_resource_scales():
    # Substring matching ('%rsch%pfung%', "Energie") caught both before.
    for name in ("Sprachliche Erschöpfung", "sprachliche_erschoepfung",
                 "Energie-Budget Morgens", "energie_abends", "aktivitaetsniveau"):
        assert not canonical_symptoms(name) & syn.FATIGUE_LIKE, name
    for name in ("Erschöpfung", "erschoepfung_fatigue", "fatigue", "PEM", "pem_erschoepfung"):
        assert canonical_symptoms(name) & syn.FATIGUE_LIKE, name


@pytest.mark.parametrize("raw, canonical", [
    ("nachtschweis", "Nachtschweiß"),
    ("fibro_fog", "Brain Fog"),
    ("trockener_mund", "Mundtrockenheit"),
    ("sicca_mundtrockenheit", "Mundtrockenheit"),
    ("sicca_augentrockenheit", "Trockene Augen"),
    ("koerperschmerz", "Körperschmerzen"),
    ("einschlafschwierigkeiten", "Schlafstörungen"),
])
def test_tracker_raw_keys_map_like_their_readable_spelling(raw, canonical):
    assert canonical_symptoms(raw) == {canonical}


def test_breast_pain_is_not_chest_pain():
    # symptom_map.json mapped "breast pain" to "Brustschmerzen", the profiles'
    # name for chest pain, so a cycle symptom matched cardiac profiles.
    assert canonical_symptoms("breast pain") == {"Brustdrüsenschmerzen"}
    assert not canonical_symptoms("breast pain") & canonical_symptoms("Brustschmerzen")
