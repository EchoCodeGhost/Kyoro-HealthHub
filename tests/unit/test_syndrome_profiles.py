# SPDX-License-Identifier: GPL-3.0-or-later
"""
Cross-reference fields in the syndrome profiles.

Background: the field "coinfection_with" suggested a co-infection in the
narrow sense, but in 18 profiles it only recorded that the DBG guideline
2026 lists the pathogen in connection with Lyme borreliosis (the DBG uses
"Co-Infektion" broadly, incl. non-tick-borne viruses such as SARS-CoV-2
for phenotypic overlap). It is now dbg_2026_lyme_associated; in
neuroborreliose.json, which listed pathogens of the same tick vector,
same_tick_vector.
"""
import json
from pathlib import Path

SYNDROMES_DIR = Path(__file__).parent.parent.parent / "scripts" / "analysis" / "syndromes"


def _profiles():
    for f in sorted(SYNDROMES_DIR.glob("*.json")):
        if not f.name.startswith("_"):
            yield f.stem, json.loads(f.read_text(encoding="utf-8"))


def test_misleading_coinfection_field_is_gone():
    assert [slug for slug, d in _profiles() if "coinfection_with" in d] == []


def test_cross_references_point_to_existing_profiles():
    slugs = {slug for slug, _ in _profiles()}
    for slug, d in _profiles():
        for field in ("dbg_2026_lyme_associated", "same_tick_vector"):
            for target in d.get(field, []):
                assert target in slugs, f"{slug}.{field} -> {target}"
                assert target != slug, f"{slug}.{field} references itself"
