#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Unit tests for provider_scrubbing module.
"""

import sys
import shutil
import tempfile
from pathlib import Path

import pytest

# provider_scrubbing.py imports identity_resolver via "scripts/" on sys.path
# as "modules.identity_resolver" (the repo-wide convention for scripts/
# importers) -- the test must use the exact same path/module name, otherwise
# it patches a different module object than the one provider_scrubbing.py
# actually calls into, and the monkeypatch below silently has no effect.
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from modules import identity_resolver  # noqa: E402
from modules.provider_scrubbing import scrub_provider_text  # noqa: E402

TEST_REGISTRY = [
    {
        "match": ["dr_mustermann_ingolstadt", "Dr. Max Mustermann", "Praxis Mustermann"],
        "category": "Hausarzt",
        "city": "Musterstadt",
        "country": "DE",
        "region": None,
    },
]


@pytest.fixture(autouse=True)
def isolated_identity_db():
    """Point identity_resolver at a throwaway DB for every test in this file."""
    test_dir = Path(tempfile.mkdtemp())
    identity_resolver.IDENTITY_DB_PATH = test_dir / "identity.db"
    identity_resolver.REGISTRY_PATH = test_dir / "registry.json"
    identity_resolver.default_resolver = identity_resolver.IdentityResolver()
    yield
    shutil.rmtree(test_dir)


def test_registry_exact_match_strips_and_pseudonymizes():
    result = scrub_provider_text("Termin bei Dr. Max Mustermann besprochen", registry=TEST_REGISTRY)
    assert "Mustermann" not in result.clean_text
    assert result.provider_category == "Hausarzt"
    assert result.provider_city == "Musterstadt"
    assert result.provider_country == "DE"
    assert result.provider_pseudonym is not None
    assert result.provider_pseudonym.startswith("PRV-")
    assert result.needs_review is False


def test_registry_match_is_deterministic():
    r1 = scrub_provider_text("Praxis Mustermann", registry=TEST_REGISTRY)
    r2 = scrub_provider_text("Praxis Mustermann", registry=TEST_REGISTRY)
    assert r1.provider_pseudonym == r2.provider_pseudonym


@pytest.mark.parametrize("prefix", [
    "Dr. rer. soc.", "Dr.med.", "Dr.rer.", "Dr. med", "Dr.", "Prof. Dr.",
    "Dipl.Psych.", "Dipl. Psych.", "Dipl.-Psych.",
    "Priv. Doz.", "Priv.Doz.", "Priv.-Doz. Dr.", "Priv. Doz. Dr. med.",
])
def test_academic_title_variants_are_stripped(prefix):
    """German doctoral/academic-title variants (interposed qualifiers like
    rer./med./jur./phil., optionally nat./soc./pol./dent.; Dipl.-Psych.;
    Priv.-Doz., standalone or combined with Dr.) must be recognized, not
    just the bare 'Dr.'/'Prof. Dr.' forms."""
    text = f"Termin bei {prefix} Mustermann besprochen"
    result = scrub_provider_text(text, registry=[])
    assert "Mustermann" not in result.clean_text


def test_longest_match_wins_over_shorter_generic_entry():
    """A specific, longer entry must win even if a shorter, more generic
    entry (that happens to also be a substring of the text) is listed
    earlier in the registry."""
    registry = [
        {"match": ["musterort"], "category": "Ort", "city": "Musterort", "country": "DE", "region": None},
        {"match": ["klinik musterort"], "category": "Klinik", "city": "Musterort", "country": "DE", "region": None},
    ]
    specific = scrub_provider_text("Klinik Musterort", registry=registry)
    generic = scrub_provider_text("Musterort", registry=registry)
    assert specific.provider_category == "Klinik"
    assert generic.provider_category == "Ort"
    assert specific.provider_pseudonym != generic.provider_pseudonym


def test_german_postal_code_reduces_to_city():
    result = scrub_provider_text("Behandlung in Musterstr. 5, 12345 Beispielstadt", registry=[])
    assert "Musterstr" not in result.clean_text
    assert "12345" not in result.clean_text
    assert "Beispielstadt" in result.clean_text
    assert result.provider_country == "DE"


def test_title_name_pattern_without_registry_flags_review():
    result = scrub_provider_text("Termin bei Dr. Müller besprochen", registry=[])
    assert "Müller" not in result.clean_text
    assert result.needs_review is True
    assert result.provider_pseudonym is None


def test_title_name_pattern_with_registry_match_takes_precedence():
    result = scrub_provider_text("Termin bei Dr. Max Mustermann", registry=TEST_REGISTRY)
    assert result.needs_review is False
    assert result.provider_pseudonym is not None


def test_safety_net_flags_suspicious_leftover_text():
    result = scrub_provider_text("Hinweis Musterweg 12345 Sonstiges Weiteres Drittes", registry=[])
    assert result.needs_review is True
    # Nothing is discarded -- text is retained, just flagged
    assert result.clean_text


@pytest.mark.parametrize("text", [
    "Krankenhaus der Barmherzigen Brüder",
    "Klinikum rechts der Isar",
    "Krankenhaus für Naturheilweisen Musterstadt",
])
def test_safety_net_flags_german_institution_name_with_connector_words(text):
    """A capitalized institution name with 1-2 lowercase German connector
    words in the middle (der/von/rechts/für/...) must still be flagged --
    the plain '3 directly consecutive capitalized words' rule alone misses
    this, since the connector reduces the count of ADJACENT capitalized
    words below 3."""
    result = scrub_provider_text(text, registry=[])
    assert result.needs_review is True


def test_bare_name_without_title_or_address_is_not_detected():
    """Documented accepted gap: no title, no address -> not reliably detectable."""
    result = scrub_provider_text("mit Michael treffen", registry=[])
    assert result.needs_review is False
    assert result.provider_pseudonym is None
    assert "Michael" in result.clean_text


def test_plain_text_without_any_marker_passes_through_unflagged():
    result = scrub_provider_text("Routinekontrolle ohne besonderen Befund", registry=[])
    assert result.needs_review is False
    assert result.provider_pseudonym is None
    assert result.clean_text == "Routinekontrolle ohne besonderen Befund"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
