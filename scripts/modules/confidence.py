#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
confidence.py — Einheitliche Konfidenz-Kennzeichnung für Analyse-Befunde

@tier        infrastructure
@purpose.de  Stellt ein einheitliches Vokabular bereit, um jeden in einem
             Analyse-Report kommunizierten Befund einer von drei
             Konfidenzstufen zuzuordnen: bestätigt, vermutet, offener
             Hinweis.
@purpose.en  Provides a unified vocabulary to tag every finding
             communicated in an analysis report with one of three
             confidence levels: confirmed, suspected, open lead.
@relevance.de Ohne einheitliche Kennzeichnung vermischen Analyse-Reports
             gesicherte Fakten mit bloßen Hypothesen, ohne dass Leser:innen
             (Patient:in, Arzt, Gutachter) den Unterschied erkennen können —
             kritisch für ein Projekt mit gerichtstauglichem Anspruch.
@relevance.en Without a unified label, analysis reports mix established
             facts with mere hypotheses without readers (patient,
             physician, expert witness) being able to tell them apart —
             critical for a project with a court-admissibility goal.
@method.de   Reines Formatierungs-Modul, keine Berechnung. Eine Funktion
             `label_finding()` nimmt deutschen Text, englischen Text und
             eine Konfidenzstufe entgegen und gibt beide Texte mit
             passendem Emoji-Präfix zurück.
@method.en   Pure formatting module, no computation. A single function
             `label_finding()` takes German text, English text and a
             confidence level, and returns both texts with the matching
             emoji prefix.
@reads       keine
@writes      keine
@usage
    from modules.confidence import label_finding
    de, en = label_finding("Borrelia-Infektion serologisch bestätigt",
                           "Borrelia infection serologically confirmed",
                           "confirmed")
    # de == "✅ Bestätigt: Borrelia-Infektion serologisch bestätigt"
    from modules.confidence import label_finding
    de, en = label_finding("Erhöhtes AFib-Risiko", "Elevated AFib risk", "suspected")
@limits.de  Reines Formatierungsmodul ohne medizinische Logik oder Einschränkungen.
@limits.en  Pure formatting module with no medical logic or limitations.
"""

from typing import Literal

Level = Literal["confirmed", "suspected", "lead"]

_PREFIXES: dict[str, tuple[str, str]] = {
    "confirmed": ("✅ Bestätigt", "✅ Confirmed"),
    "suspected": ("⚠️ Vermutet", "⚠️ Suspected"),
    "lead":      ("❓ Offener Hinweis", "❓ Open lead"),
}


def label_finding(text_de: str, text_en: str, level: Level) -> tuple[str, str]:
    """Formatiert einen Befund mit Konfidenz-Präfix (DE, EN)."""
    if level not in _PREFIXES:
        raise ValueError(
            f"Ungültige Konfidenzstufe {level!r}, erwartet: "
            f"{sorted(_PREFIXES)}"
        )
    prefix_de, prefix_en = _PREFIXES[level]
    return f"{prefix_de}: {text_de}", f"{prefix_en}: {text_en}"
