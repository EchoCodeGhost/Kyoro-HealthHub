#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
patient_scrubbing.py — Entfernt die eigene Identität der Nutzerin aus Freitext

@tier        infrastructure
@purpose.de  Entfernt den konfigurierten eigenen Namen, das eigene Geburtsdatum,
             Alters-Muster und das deutsche Versichertennummer-Format aus
             Freitext, bevor der Text in eine Tabelle oder Zwischendatei
             geschrieben wird -- anders als provider_scrubbing.py (unbekannte
             Dritt-Namen, Heuristik) ist die eigene Identität aus der Config
             exakt bekannt, daher Exakt-Abgleich statt Heuristik.
@purpose.en  Removes the configured user's own name, own birthdate, a
             "<number> years" pattern, and the German insurance-member-
             number format from free text before it is written to a table
             or intermediate
             file -- unlike provider_scrubbing.py (unknown third-party
             names, heuristic), the user's own identity is known exactly
             from config, so this is exact matching, not a heuristic.
@method.de   Name: alle Wortanordnungen (Reihenfolge, "Nachname, Vorname")
             werden exakt (case-insensitive) entfernt. Geburtsdatum: ISO-Form
             aus der Config sowie TT.MM.JJJJ-Variante (mit und ohne führende
             Nullen) werden exakt entfernt. Lebensjahr-Zählung: Muster
             "<Zahl> Jahre(alt)?"/"<Zahl> years (old)?" werden unabhängig
             vom aktuellen exakten Wert entfernt (ändert sich jährlich,
             exakter Abgleich wäre nächstes Jahr schon falsch). Versichertennummer/KV-Nummer:
             deutsches Standardformat (1 Buchstabe + 9 Ziffern, auch mit
             Leerzeichen dazwischen) wird per Muster entfernt, unabhängig
             davon, ob die eigene Nummer irgendwo konfiguriert ist.
@method.en   Name: all word orderings (including "lastname, firstname") are
             removed exactly (case-insensitive). Birthdate: the config's ISO
             form plus the DD.MM.YYYY variant (with and without leading
             zeros) are removed exactly. Years-lived count: the pattern
             "<number> years(old)?"/"<number> Jahre(alt)?" is removed
             regardless of the current exact value (changes yearly, an
             exact match would already be wrong next year). Insurance member number: the
             German standard format (1 letter + 9 digits, optionally
             space-separated) is removed by pattern, regardless of whether
             the user's own number is configured anywhere.
@reads       health_config.json (user.name, user.birthdate)
@writes      keine Tabellen (reine Textverarbeitungsfunktion)
@limits.de   Kein NER -- erkennt nur die exakt konfigurierten Werte plus die
             beiden dokumentierten Muster (Jahre-gezählt, Versichertennummer-Format).
             Ein abweichend geschriebener Name (Spitzname, OCR-Tippfehler)
             wird nicht erkannt. Das Versichertennummer-Muster kann auch
             fremde, zufällig gleich geformte Zahlen treffen (1 Buchstabe +
             9 Ziffern ist nicht einzigartig) -- akzeptiertes Risiko, da
             Entfernen hier weniger schadet als Übersehen.
@limits.en   No NER -- only detects the exactly configured values plus the
             two documented patterns (years-lived count, insurance-number format). A
             differently spelled name (nickname, OCR typo) is not detected.
             The insurance-number pattern can also match an unrelated
             number that happens to share the same shape (1 letter + 9
             digits isn't unique) -- accepted risk, since removing it here
             is less harmful than missing it.

@relevance.de  Verhindert, dass die eigene Identität der Nutzerin unpseudonymisiert in Tabellen oder Zwischendateien landet, essentiell für den Datenschutz jedes Freitext-verarbeitenden Importers
@relevance.en  Prevents the user's own identity from landing unpseudonymized in tables or intermediate files, essential for the privacy of every free-text-processing importer
@usage
    from modules.patient_scrubbing import scrub_patient_identity
    clean_text = scrub_patient_identity(raw_text)
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from health_config import Config  # noqa: E402

AGE_PATTERN_RE = re.compile(
    r"\b\d{1,3}\s*(?:Jahre\s*alt|Jahre|Jahr|years\s*old|years|year)\b",
    re.IGNORECASE,
)
# Deutsches Versichertennummer-/KV-Nummer-Format (SGB V): 1 Buchstabe +
# 9 Ziffern -- OCR trennt die Gruppe manchmal mit einem Leerzeichen.
INSURANCE_NUMBER_RE = re.compile(r"\b[A-Za-z]\s?\d{9}\b")


def _name_variants(full_name: str) -> list[str]:
    parts = full_name.split()
    variants = {full_name}
    if len(parts) >= 2:
        variants.add(f"{parts[-1]}, {' '.join(parts[:-1])}")
        variants.add(f"{parts[-1]} {' '.join(parts[:-1])}")
    return [v for v in variants if v.strip()]


def _birthdate_variants(iso_date: str) -> list[str]:
    variants = {iso_date}
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", iso_date)
    if m:
        y, mo, d = m.groups()
        variants.add(f"{d}.{mo}.{y}")
        variants.add(f"{int(d)}.{int(mo)}.{y}")
    return list(variants)


def scrub_patient_identity(text: str, cfg: Config | None = None) -> str:
    """Entfernt Name, Geburtsdatum, Alters- und Versichertennummer-Muster
    der konfigurierten Nutzerin aus text. Siehe Moduldocstring."""
    if not text:
        return text
    cfg = cfg or Config()
    clean = text

    name = getattr(cfg, "name", None)
    if name:
        for variant in _name_variants(name):
            clean = re.sub(re.escape(variant), "", clean, flags=re.IGNORECASE)

    birthdate = getattr(cfg, "birthdate", None)
    if birthdate:
        for variant in _birthdate_variants(birthdate):
            clean = re.sub(re.escape(variant), "", clean)

    clean = AGE_PATTERN_RE.sub("", clean)
    clean = INSURANCE_NUMBER_RE.sub("", clean)
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean
