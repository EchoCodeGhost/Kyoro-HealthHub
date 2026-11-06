#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
provider_scrubbing.py — Pseudonymisierung von Leistungserbringer-/Adress-Freitext

@tier        infrastructure
@purpose.de  Erkennt Leistungserbringer-Namen (Freitext-Nennungen eines
             behandelnden Anbieters) und Adressen in Freitext (z. B. aus
             gescannten Dokumenten) und entfernt sie, bevor der Text in eine
             Tabelle oder eine Zwischendatei geschrieben wird. Zentrales,
             wiederverwendbares Modul statt pro Importer eigener
             Scrubbing-Logik.
@purpose.en  Detects treating-provider name mentions and addresses in free
             text (e.g. from scanned documents) and removes them before the
             text is written to a table or an intermediate file. Central,
             reusable module instead of per-importer scrubbing logic.
@method.de   Vierstufig, ausschließlich Regex/Registry-basiert, kein NER/ML:
             1. Exakter Treffer in der lokalen, nie committeten Registry
                (~/.config/kyoro/provider_registry.json) — entfernt den
                Rohstring, setzt category/city/country/region aus dem
                Registry-Eintrag, löst provider_pseudonym über
                identity_resolver.resolve("provider", <kanonischer Schlüssel>)
                auf.
             2. Kein Registry-Treffer, aber deutsches PLZ+Ort-Muster
                (\\d{5}\\s+[A-ZÄÖÜ][a-zäöüß]+) → auf Stadtname reduzieren,
                country="DE" setzen.
             3. Titel+Name-Muster (Dr., Dr. med., Prof., Prof. Dr.,
                Facharzt/Fachärztin für ..., Zahnarzt/Zahnärztin, ...) +
                1-2 großgeschriebene Wörter → entfernen, needs_review=True,
                außer Schritt 1 hat den Namen schon aufgelöst.
             4. Sicherheitsnetz: verbleiben Straßen-Suffixe, eine
                5-stellige Restzahl oder mehrere aufeinanderfolgende
                Großwörter → needs_review=True, Text bleibt erhalten
                (kein Verwerfen).
@method.en   Four-tier, purely regex/registry-based, no NER/ML:
             1. Exact match against the local, never-committed registry
                (~/.config/kyoro/provider_registry.json) — strips the raw
                string, sets category/city/country/region from the
                registry entry, resolves provider_pseudonym via
                identity_resolver.resolve("provider", <canonical key>).
             2. No registry match but a German postal-code pattern
                (\\d{5}\\s+[A-ZÄÖÜ][a-zäöüß]+) → reduce to city name,
                set country="DE".
             3. Title+name pattern (Dr., Dr. med., Prof., Prof. Dr.,
                Facharzt/Fachärztin für ..., Zahnarzt/Zahnärztin, ...) +
                1-2 capitalized words → strip, needs_review=True, unless
                step 1 already resolved the name.
             4. Safety net: remaining street-suffix words, a leftover
                5-digit number, or several consecutive capitalized words
                → needs_review=True, text is kept (never discarded).
@reads       ~/.config/kyoro/provider_registry.json
@writes      keine Tabellen (reine Textverarbeitungsfunktion; Aufrufer
             entscheiden, was mit dem Ergebnis in ihre eigenen Tabellen
             geschrieben wird)
@limits.de   Keine echte Named-Entity-Recognition — ein blanker Name ohne
             Titel und ohne Adresse (z. B. "mit Michael treffen") wird
             NICHT erkannt, das ist eine dokumentierte, akzeptierte Lücke.
             Die Heuristiken (PLZ-Muster, Titel+Name-Muster) wurden gegen
             kalenderartigen Freitext entworfen, nicht gegen OCR-Rauschen
             aus gescannten Dokumenten — bei OCR-Eingabe trägt der exakte
             Registry-Treffer mehr Gewicht als die Muster-Heuristiken,
             da OCR-Fehler (vertauschte Zeichen, fehlende Umlaute) die
             Muster schneller zerstören als einen Wörterbuch-Treffer.
@limits.en   No real named-entity recognition — a bare name with neither a
             title nor an address (e.g. "mit Michael treffen") is NOT
             detected; this is a documented, accepted gap. The heuristics
             (postal-code pattern, title+name pattern) were designed
             against calendar-style free text, not against OCR noise from
             scanned documents — for OCR input, the exact registry match
             carries more weight than the pattern heuristics, since OCR
             errors (transposed characters, dropped umlauts) break the
             patterns faster than a dictionary lookup.

@relevance.de  Verhindert, dass Arztnamen/Adressen aus Freitext unpseudonymisiert in Tabellen oder Zwischendateien landen, essentiell für den Datenschutz jedes Freitext-verarbeitenden Importers
@relevance.en  Prevents treating-provider name mentions/addresses in free text from landing unpseudonymized in tables or intermediate files, essential for the privacy of every free-text-processing importer
@usage
    from modules.provider_scrubbing import scrub_provider_text
    result = scrub_provider_text("Termin bei Dr. Müller, Musterstr. 1, 12345 Musterstadt")
    result.clean_text          # -> "Termin bei , 12345 Musterstadt" (falls kein Registry-Treffer) oder vollständig bereinigt (falls Registry-Treffer)
    result.provider_pseudonym  # -> "PRV-xxxxxxxx" oder None
    result.needs_review        # -> True/False
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from modules.identity_resolver import resolve_provider  # noqa: E402

PROVIDER_REGISTRY_PATH = Path("~/.config/kyoro/provider_registry.json").expanduser()

# Deutsche PLZ gefolgt von einem großgeschriebenen Ortsnamen.
GERMAN_POSTAL_CODE_RE = re.compile(
    r"(?:[A-Za-zÄÖÜäöüß]+(?:straße|strasse|str\.)\s*\d+\w?,?\s*)?"
    r"\b\d{5}\s+([A-ZÄÖÜ][a-zäöüß]+)\b"
)

# Berufs-/akademische Titel, gefolgt von 1-2 großgeschriebenen Wörtern.
TITLE_NAME_RE = re.compile(
    r"\bPriv\.?-?\s*Doz\.?\s*(?:Prof\.\s*Dr\.|Prof\.|Dr\.)?\s*(?:(?:rer|med|jur|phil)\.?\s*)?"
    r"(?:(?:nat|soc|pol|dent)\.?\s*)?([A-ZÄÖÜ][a-zäöüß]+(?:\s+[A-ZÄÖÜ][a-zäöüß]+)?)"
    r"|\b(?:Prof\.\s*Dr\.|Prof\.|Dr\.)\s*(?:(?:rer|med|jur|phil)\.?\s*)?"
    r"(?:(?:nat|soc|pol|dent)\.?\s*)?"
    r"([A-ZÄÖÜ][a-zäöüß]+(?:\s+[A-ZÄÖÜ][a-zäöüß]+)?)"
    r"|\b(?:Facharzt(?:/Fachärztin)?|Fachärztin)\s+für\s+\w+\s+([A-ZÄÖÜ][a-zäöüß]+(?:\s+[A-ZÄÖÜ][a-zäöüß]+)?)"
    r"|\b(?:Zahnarzt(?:/Zahnärztin)?|Zahnärztin)\s+([A-ZÄÖÜ][a-zäöüß]+(?:\s+[A-ZÄÖÜ][a-zäöüß]+)?)"
    r"|\bDipl\.?-?\s*Psych\.?\s*([A-ZÄÖÜ][a-zäöüß]+(?:\s+[A-ZÄÖÜ][a-zäöüß]+)?)",
)

# Sicherheitsnetz-Indikatoren: Straßen-Suffixe, Restzahl, mehrere Großwörter.
STREET_SUFFIX_RE = re.compile(r"\b\w+(?:straße|strasse|str\.|weg|platz|allee|gasse)\b", re.IGNORECASE)
LEFTOVER_FIVE_DIGIT_RE = re.compile(r"\b\d{5}\b")
# Zwei getrennte Muster statt eines ueberladenen: (A) 3+ direkt aufeinander-
# folgende Grosswoerter (Name+Nachname-Stil, z.B. Briefanrede/-schluss) und
# (B) 2+ Grosswoerter MIT 1-2 Verbindungswoertern dazwischen (deutscher
# Institutionsname-Stil, z.B. "Krankenhaus der Barmherzigen Brüder",
# "Klinikum rechts der Isar" -- (A) allein uebersieht das, da "rechts der"
# zwei Kleinwoerter dazwischenschiebt und nur 2 statt 3 Grosswoerter uebrig
# bleiben).
CONSECUTIVE_CAPITALIZED_RE = re.compile(
    r"\b[A-ZÄÖÜ][a-zäöüß]+\s+[A-ZÄÖÜ][a-zäöüß]+\s+[A-ZÄÖÜ][a-zäöüß]+\b"
    r"|\b[A-ZÄÖÜ][a-zäöüß]+(?:\s+(?:der|von|zum|zur|im|am|in|des|an|für|rechts|links|bei)){1,2}\s+[A-ZÄÖÜ][a-zäöüß]+\b"
)


@dataclass
class ProviderScrubResult:
    clean_text: str
    provider_category: str | None = None
    provider_city: str | None = None
    provider_country: str | None = None
    provider_region: str | None = None
    provider_pseudonym: str | None = None
    needs_review: bool = False


def load_provider_registry(path: Path = PROVIDER_REGISTRY_PATH) -> list[dict]:
    """Lädt die lokale Provider-Registry; leere Liste, falls keine existiert."""
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("providers", [])


def _match_registry(text: str, registry: list[dict]) -> tuple[str, dict, str] | None:
    """Treffer mit der LÄNGSTEN passenden Teilzeichenkette + Eintrag +
    kanonischer Schlüssel, falls vorhanden -- nicht einfach der erste
    Treffer in Registry-Reihenfolge. Sonst würde ein kürzerer, generischerer
    Eintrag (z. B. "Neuburg") einen längeren, spezifischeren (z. B. "Ameos
    Neuburg") verdecken, nur weil er zufällig weiter oben in der Liste
    steht -- gefunden beim Testen, kein hypothetischer Fall."""
    tl = text.lower()
    best: tuple[str, dict, str] | None = None
    for entry in registry:
        for candidate in entry.get("match", []):
            if candidate.lower() in tl:
                if best is None or len(candidate) > len(best[0]):
                    canonical_key = entry["match"][0]
                    best = (candidate, entry, canonical_key)
    return best


def scrub_provider_text(text: str, registry: list[dict] | None = None) -> ProviderScrubResult:
    """Pseudonymisiert Leistungserbringer-/Adress-Freitext, siehe Moduldocstring für die 4 Stufen.

    registry: optional vorab geladene Registry (via load_provider_registry()) --
    wer viele Zeilen verarbeitet, sollte sie einmal laden und hier durchreichen
    statt sie bei jedem Aufruf neu von der Platte zu lesen.
    """
    if registry is None:
        registry = load_provider_registry()

    clean_text = text
    needs_review = False
    provider_category = provider_city = provider_country = provider_region = None
    provider_pseudonym = None

    # Stufe 1: Registry-Treffer
    match = _match_registry(text, registry)
    if match:
        matched_str, entry, canonical_key = match
        clean_text = re.sub(re.escape(matched_str), "", clean_text, flags=re.IGNORECASE)
        provider_category = entry.get("category")
        provider_city = entry.get("city")
        provider_country = entry.get("country")
        provider_region = entry.get("region")
        provider_pseudonym = resolve_provider(canonical_key)
    else:
        # Stufe 2: deutsches PLZ-Muster
        postal_match = GERMAN_POSTAL_CODE_RE.search(clean_text)
        if postal_match:
            city = postal_match.group(1)
            clean_text = clean_text[: postal_match.start()] + city + clean_text[postal_match.end():]
            provider_country = "DE"
            provider_city = provider_city or city

        # Stufe 3: Titel+Name-Muster (unabhängig von Stufe 2)
        title_match = TITLE_NAME_RE.search(clean_text)
        if title_match:
            clean_text = clean_text[: title_match.start()] + clean_text[title_match.end():]
            needs_review = True

    # Stufe 4: Sicherheitsnetz
    if (STREET_SUFFIX_RE.search(clean_text)
            or LEFTOVER_FIVE_DIGIT_RE.search(clean_text)
            or CONSECUTIVE_CAPITALIZED_RE.search(clean_text)):
        needs_review = True

    clean_text = re.sub(r"\s+", " ", clean_text).strip()

    return ProviderScrubResult(
        clean_text=clean_text,
        provider_category=provider_category,
        provider_city=provider_city,
        provider_country=provider_country,
        provider_region=provider_region,
        provider_pseudonym=provider_pseudonym,
        needs_review=needs_review,
    )
