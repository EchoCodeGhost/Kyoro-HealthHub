# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Prompt-Definitionen aus scripts/analysis/ophthalmology/*.py

@tier        infrastructure
@purpose.de  Enthält die LLM-System-Prompts aus den Ophthalmology-Analyse-Skripten,
             wortwörtlich an ihren ursprünglichen Definitionsort verschoben (Phase 2 der
             Prompt-Bibliotheks-Migration) und in der zentralen Registry
             (modules.prompts) registriert.
@purpose.en  Contains the LLM system prompts from the ophthalmology analysis scripts,
             moved verbatim from their original definition site (Phase 2 of the
             prompt-library migration) and registered in the central
             registry (modules.prompts).
@method.de   Jede Konstante bleibt unter ihrem ursprünglichen Namen
             importierbar (z.B. _SYSTEM_DE, _SYSTEM_EN); zusätzlich wird sie per
             register(Prompt(...)) mit Owner-Pfad und Klassifikation in
             die Registry eingetragen.
@method.en   Each constant remains importable under its original name
             (e.g. _SYSTEM_DE, _SYSTEM_EN); it is additionally registered via
             register(Prompt(...)) with an owner path and classification.
@relevance.de  Macht alle Ophthalmology-Analyse-Prompts an einer Stelle auffindbar.
@relevance.en  Makes all ophthalmology analysis prompts discoverable in one place.
@reads       keine
@writes      keine
@limits.de   Reine Datenhaltung — keine eigene Logik.
@limits.en   Pure data holder — no logic of its own.
@usage
    from modules.prompts.analysis_ophthalmology import SYSTEM_DE_ANALYSE_FUNDUS
    from modules.prompts.analysis_ophthalmology import SYSTEM_EN_ANALYSE_FUNDUS
"""

from modules.prompts import Prompt, register

# -- analyse_fundus.py ------------------------------------------------------------

_SYSTEM_DE_ANALYSE_FUNDUS = ("Du bist ein erfahrener Augenarzt mit Spezialisierung auf Glaukomdiagnostik "
         "und Netzhauterkrankungen. Analysiere Fundusfotos klinisch präzise und strukturiert. "
         "Keine Diagnose — nur Befundbeschreibung und Differenzialdiagnosen.")

_SYSTEM_EN_ANALYSE_FUNDUS = ("You are an experienced ophthalmologist specializing in glaucoma diagnostics "
         "and retinal disease. Analyze fundus photos clinically, precisely, and in a structured format. "
         "No diagnosis — findings and differential diagnoses only.")

register(Prompt(
    name="_SYSTEM_DE",
    owner="scripts/analysis/ophthalmology/analyse_fundus.py",
    classification="LLM:Analysis",
    lang="bilingual",
    text_de=_SYSTEM_DE_ANALYSE_FUNDUS,
    text_en=_SYSTEM_EN_ANALYSE_FUNDUS,
))

# String-Konstanten für Kompatibilität
SYSTEM_DE_ANALYSE_FUNDUS = _SYSTEM_DE_ANALYSE_FUNDUS
SYSTEM_EN_ANALYSE_FUNDUS = _SYSTEM_EN_ANALYSE_FUNDUS
_SYSTEM_DE = SYSTEM_DE_ANALYSE_FUNDUS
_SYSTEM_EN = SYSTEM_EN_ANALYSE_FUNDUS

# Oeffentliche Alias-Konstanten (Kompatibilitaet fuer Owner-Skript-Imports)
_SYSTEM_DE_DE = _SYSTEM_DE_ANALYSE_FUNDUS
_SYSTEM_DE_EN = _SYSTEM_EN_ANALYSE_FUNDUS
