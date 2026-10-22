#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
symptom_synonyms.py — Kanonische Symptomnamen fuer den Abgleich Tagebuch <-> Syndromprofil

@tier        infrastructure
@purpose.de  Bildet Symptomnamen auf kanonische Namen ab, damit gleichbedeutende Begriffe
             beim Abgleich als dasselbe Symptom zaehlen (z.B. "Myalgie" im Syndromprofil
             und "Muskelschmerzen" im Symptomtagebuch, oder der kombinierte Tagebuch-
             eintrag "Erschoepfung/Fatigue" und "Fatigue" im Profil).
@purpose.en  Maps symptom names to canonical names so that synonymous terms count as the
             same symptom when matching (e.g. "Myalgie" in a syndrome profile and
             "Muskelschmerzen" in a symptom diary, or the combined diary entry
             "Erschoepfung/Fatigue" and "Fatigue" in a profile).
@method.de   Zwei Stufen. (1) Rohe Tagebuchnamen ueber config/symptom_map.json (bzw. die
             Nutzerkopie in ~/.config/kyoro/symptom_map.json, wie compute_symptoms.py)
             auf deren kanonischen deutschen Namen. (2) Synonymgruppen und kombinierte
             Eintraege aus scripts/analysis/syndromes/_symptom_synonyms.json auf die
             Namen der Syndromprofile; ein kombinierter Eintrag kann mehrere Profil-
             symptome treffen. Abgleich ohne Gross-/Kleinschreibung, mit normalisierten
             Leerzeichen/Bindestrichen. Unbekannte Namen bleiben unveraendert (getrimmt).
             Symptom-Tage werden pro kanonischem Namen ueber distinkte Daten gezaehlt.
@method.en   Two stages. (1) Raw diary names via config/symptom_map.json (or the user copy
             in ~/.config/kyoro/symptom_map.json, as in compute_symptoms.py) to its
             canonical German name. (2) Synonym groups and combined entries from
             scripts/analysis/syndromes/_symptom_synonyms.json to the syndrome profile
             names; a combined entry can match several profile symptoms. Case-insensitive
             with normalized whitespace/hyphens. Unknown names are kept (stripped).
             Symptom days are counted per canonical name over distinct dates.
@reads       config/symptom_map.json (oder ~/.config/kyoro/symptom_map.json),
             scripts/analysis/syndromes/_symptom_synonyms.json,
             Tabelle symptoms (nur raw_symptom_names: distinkte Symptomnamen)
@writes      Keine (reine Hilfsfunktionen)
@limits.de   Nur exakte Synonyme bzw. engere Begriffe auf den breiteren Profilbegriff; keine
             unscharfe Suche, keine Teilwort-Treffer. Mehrdeutige Begriffe sind bewusst
             nicht enthalten (s. _meta in der JSON-Datei).
@limits.en   Only true synonyms or narrower terms mapped to the broader profile term; no fuzzy
             search, no substring matches. Ambiguous terms are deliberately left out (see
             _meta in the JSON file).
@relevance.de  Ohne Synonyme gehen Treffer verloren, sobald Tagebuch und Syndromprofil
               unterschiedliche Begriffe fuer dasselbe Symptom verwenden.
@relevance.en  Without synonyms, matches are lost whenever the diary and the syndrome profile
               use different terms for the same symptom.
@usage
    from modules.symptom_synonyms import canonical_symptoms, canonicalize, count_symptom_days
    from modules.symptom_synonyms import FATIGUE_LIKE, raw_symptom_names
    canonical_symptoms("Myalgie")                          # -> {"Muskelschmerzen"}
    canonical_symptoms("Brainfog/Konzentrationsstörungen") # -> {"Brain Fog", "Konzentrationsstörungen"}
    canonicalize(["PEM", "Tachykardie"])                   # -> {"Post-Exertionelle Malaise", "Herzrasen"}
    count_symptom_days([("Myalgie", "2026-01-01"), ("Muskelschmerzen", "2026-01-01")])
                                                           # -> {"Muskelschmerzen": 1}
    raw_symptom_names(conn, FATIGUE_LIKE)   # -> ["Erschöpfung/Fatigue", "erschoepfung_fatigue", ...]
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from functools import lru_cache
from pathlib import Path
from typing import Iterable

_REPO = Path(__file__).parent.parent.parent
_SYNONYMS_FILE = _REPO / "scripts" / "analysis" / "syndromes" / "_symptom_synonyms.json"
_SYMPTOM_MAP_DEFAULT = _REPO / "config" / "symptom_map.json"

_DASHES = re.compile(r"[‐-―−]")
_SPACES = re.compile(r"\s+")


def _key(name: str) -> str:
    """Normalisierter Vergleichsschluessel: Kleinschreibung, einheitliche Bindestriche/Leerzeichen."""
    return _SPACES.sub(" ", _DASHES.sub("-", name)).strip().casefold()


def _symptom_map_path() -> Path:
    """Nutzerkopie der symptom_map.json, falls vorhanden (wie compute_symptoms.py)."""
    try:
        from health_config import KYORO_CONFIG_DIR
        user = KYORO_CONFIG_DIR / "symptom_map.json"
        if user.exists():
            return user
    except Exception:
        pass
    return _SYMPTOM_MAP_DEFAULT


@lru_cache(maxsize=None)
def _raw_map() -> dict[str, str]:
    """Stufe 1: Rohname (Schluessel) -> kanonischer DE-Name aus symptom_map.json."""
    path = _symptom_map_path()
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {_key(k): v["de"] for k, v in data.items()
            if not k.startswith("_") and isinstance(v, dict) and v.get("de")}


@lru_cache(maxsize=None)
def _synonym_map() -> dict[str, frozenset[str]]:
    """Stufe 2: Name (Schluessel) -> kanonische Profilnamen aus _symptom_synonyms.json."""
    data = json.loads(_SYNONYMS_FILE.read_text(encoding="utf-8"))
    table: dict[str, frozenset[str]] = {}
    for group in data.get("groups", []):
        target = frozenset([group["canonical"]])
        for name in [group["canonical"], *group.get("variants", [])]:
            table[_key(name)] = target
    for entry in data.get("combined", []):
        table[_key(entry["name"])] = frozenset(entry["maps_to"])
    return table


def canonical_symptoms(name: str) -> frozenset[str]:
    """Kanonische Profilnamen fuer einen Symptomnamen (meist genau einer)."""
    if not name or not name.strip():
        return frozenset()
    syn = _synonym_map()
    hit = syn.get(_key(name))
    if hit is None:
        mapped = _raw_map().get(_key(name))
        if mapped is not None:
            hit = syn.get(_key(mapped), frozenset([mapped]))
    return hit if hit is not None else frozenset([name.strip()])


def canonicalize(names: Iterable[str]) -> set[str]:
    """Menge der kanonischen Namen (Duplikate durch Synonyme fallen weg)."""
    out: set[str] = set()
    for n in names:
        out |= canonical_symptoms(n)
    return out


def count_symptom_days(rows: Iterable[tuple[str, str]]) -> dict[str, int]:
    """Anzahl distinkter Tage pro kanonischem Symptom aus (symptom, date)-Zeilen."""
    days: dict[str, set[str]] = defaultdict(set)
    for symptom, date in rows:
        for canon in canonical_symptoms(symptom or ""):
            days[canon].add(date)
    return {s: len(d) for s, d in days.items()}


# Ermuedungsartige Symptome als ein gemeinsamer Begriff (PEM-Veto in
# compute_pem.py, Fatigue-Verlaeufe in den Analysen). Kanonische Namen statt
# Teilwortsuche: '%rsch%pfung%' traf auch "Sprachliche Erschöpfung", ein
# anderes Symptom. Energie-Budget/Aktivitaetsniveau gehoeren nicht dazu —
# Ressourcen-Skala (hoch = gut), umgekehrt zur Symptomskala.
FATIGUE_LIKE: frozenset[str] = frozenset({"Fatigue", "Post-Exertionelle Malaise"})


def raw_symptom_names(conn, names: Iterable[str]) -> list[str]:
    """Rohe Namen aus der Tabelle symptoms, deren kanonische Namen einen der
    kanonischen Namen von `names` treffen — fuer `symptom IN (...)`-Abfragen,
    die so alle Schreibweisen und Synonyme erfassen."""
    targets = canonicalize(names)
    raw = conn.execute(
        "SELECT DISTINCT symptom FROM symptoms WHERE symptom IS NOT NULL").fetchall()
    return sorted(r for (r,) in raw if canonical_symptoms(r) & targets)
