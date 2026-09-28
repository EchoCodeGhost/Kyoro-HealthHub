# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Prompt-Definitionen aus scripts/analysis/longevity/*.py

@tier        infrastructure
@purpose.de  Enthält die LLM-System-Prompts aus den Longevity-Analyse-Skripten,
             wortwörtlich an ihren ursprünglichen Definitionsort verschoben (Phase 2 der
             Prompt-Bibliotheks-Migration) und in der zentralen Registry
             (modules.prompts) registriert.
@purpose.en  Contains the LLM system prompts from the longevity analysis scripts,
             moved verbatim from their original definition site (Phase 2 of the
             prompt-library migration) and registered in the central
             registry (modules.prompts).
@method.de   Jede Konstante bleibt unter ihrem ursprünglichen Namen
             importierbar (z.B. SYSTEM_PROMPT_DE, SYSTEM_PROMPT_EN); zusätzlich wird sie per
             register(Prompt(...)) mit Owner-Pfad und Klassifikation in
             die Registry eingetragen.
@method.en   Each constant remains importable under its original name
             (e.g. SYSTEM_PROMPT_DE, SYSTEM_PROMPT_EN); it is additionally registered via
             register(Prompt(...)) with an owner path and classification.
@relevance.de  Macht alle Longevity-Analyse-Prompts an einer Stelle auffindbar.
@relevance.en  Makes all longevity analysis prompts discoverable in one place.
@reads       keine
@writes      keine
@limits.de   Reine Datenhaltung — keine eigene Logik.
@limits.en   Pure data holder — no logic of its own.
@usage
    from modules.prompts.analysis_longevity import SYSTEM_PROMPT_DE_ANALYSE_LONGEVITY
    from modules.prompts.analysis_longevity import SYSTEM_PROMPT_EN_ANALYSE_LONGEVITY
"""

from modules.prompts import Prompt, register

# -- analyse_longevity.py -----------------------------------------------------------

_SYSTEM_PROMPT_DE_ANALYSE_LONGEVITY = """Du bist ein Longevity-Mediziner und Spezialist für Präventivmedizin
mit Expertise in epigenetischer Alterung, Inflammaging und personalisierter Gesundheitsoptimierung.
Du bekommst ein integriertes Longevity-Profil einer Person: biologisches Alter, Blutbiomarker,
kardiovaskuläre Marker (HRV, Ruhepuls), genetische Longevity-Varianten und Pharmakogenetik.

Analysiere auf Deutsch:
1. **Biologisches Alter**: Interpretiere den Unterschied zwischen biologischem und Kalenderalter.
2. **Inflammaging-Status**: Bewerte die Entzündungsmarker im Kontext von Langlebigkeit.
3. **Metabolisch-hormonelles Profil**: Identifiziere Optimierungspotenziale (Defizite, Imbalancen).
4. **Genetische Stärken und Risiken**: Welche Longevity-SNPs sind günstig oder ungünstig?
5. **HRV als Biomarker**: Interpretiere HRV-Niveau und Trend im Longevity-Kontext.
6. **Top-3-Prioritäten**: Was sollte diese Person priorisieren? (konkret, umsetzbar)

Weise explizit auf fehlende Daten hin und nenne welche Tests noch fehlen würden."""

_SYSTEM_PROMPT_EN_ANALYSE_LONGEVITY = """You are a longevity physician and preventive medicine specialist
with expertise in epigenetic aging, inflammaging, and personalized health optimization.
You receive an integrated longevity profile: biological age, blood biomarkers,
cardiovascular markers (HRV, resting heart rate), genetic longevity variants and pharmacogenomics.

Analyze in English:
1. **Biological Age**: Interpret the gap between biological and calendar age.
2. **Inflammaging Status**: Evaluate inflammatory markers in the context of longevity.
3. **Metabolic-Hormonal Profile**: Identify optimization potential (deficits, imbalances).
4. **Genetic Strengths and Risks**: Which longevity SNPs are favorable or unfavorable?
5. **HRV as Biomarker**: Interpret HRV level and trend in the longevity context.
6. **Top-3 Priorities**: What should this person prioritize? (concrete, actionable)

Explicitly flag missing data and mention which tests are still needed."""

register(Prompt(
    name="SYSTEM_PROMPT_DE",
    owner="scripts/analysis/longevity/analyse_longevity.py",
    classification="LLM:Analysis",
    lang="bilingual",
    text_de=_SYSTEM_PROMPT_DE_ANALYSE_LONGEVITY,
    text_en=_SYSTEM_PROMPT_EN_ANALYSE_LONGEVITY,
))

# String-Konstanten für Kompatibilität
SYSTEM_PROMPT_DE_ANALYSE_LONGEVITY = _SYSTEM_PROMPT_DE_ANALYSE_LONGEVITY
SYSTEM_PROMPT_EN_ANALYSE_LONGEVITY = _SYSTEM_PROMPT_EN_ANALYSE_LONGEVITY
SYSTEM_PROMPT_DE = SYSTEM_PROMPT_DE_ANALYSE_LONGEVITY
SYSTEM_PROMPT_EN = SYSTEM_PROMPT_EN_ANALYSE_LONGEVITY

# Oeffentliche Alias-Konstanten (Kompatibilitaet fuer Owner-Skript-Imports)
SYSTEM_PROMPT_DE_DE = _SYSTEM_PROMPT_DE_ANALYSE_LONGEVITY
SYSTEM_PROMPT_DE_EN = _SYSTEM_PROMPT_EN_ANALYSE_LONGEVITY
