# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Prompt-Definitionen aus scripts/analysis/psychology/*.py

@tier        infrastructure
@purpose.de  Enthält die LLM-System-Prompts aus den Psychology-Analyse-Skripten,
             wortwörtlich an ihren ursprünglichen Definitionsort verschoben (Phase 2 der
             Prompt-Bibliotheks-Migration) und in der zentralen Registry
             (modules.prompts) registriert.
@purpose.en  Contains the LLM system prompts from the psychology analysis scripts,
             moved verbatim from their original definition site (Phase 2 of the
             prompt-library migration) and registered in the central
             registry (modules.prompts).
@method.de   Jede Konstante bleibt unter ihrem ursprünglichen Namen
             importierbar (z.B. SYSTEM_PROMPT); zusätzlich wird sie per
             register(Prompt(...)) mit Owner-Pfad und Klassifikation in
             die Registry eingetragen.
@method.en   Each constant remains importable under its original name
             (e.g. SYSTEM_PROMPT); it is additionally registered via
             register(Prompt(...)) with an owner path and classification.
@relevance.de  Macht alle Psychology-Analyse-Prompts an einer Stelle auffindbar.
@relevance.en  Makes all psychology analysis prompts discoverable in one place.
@reads       keine
@writes      keine
@limits.de   Reine Datenhaltung — keine eigene Logik.
@limits.en   Pure data holder — no logic of its own.
@usage
    from modules.prompts.analysis_psychology import SYSTEM_PROMPT_ANALYSE_PACING_DE
    from modules.prompts.analysis_psychology import SYSTEM_PROMPT_ANALYSE_PACING_EN
"""

from modules.prompts import Prompt, register

# -- analyse_pacing.py --------------------------------------------------------------

_SYSTEM_PROMPT_ANALYSE_PACING_DE = """Du bist ein Rehabilitationsmediziner mit Expertise in
energiebasiertem Aktivitätsmanagement und post-exertioneller Belastungsreaktion.

Aktivitäts-Level (Polar):
  Sedentär: <1.5 MET, Leicht: 1.5–3.0 MET, Moderat: 3.0–6.0 MET, Intensiv: >6.0 MET.
MET-Minuten: Gesamte metabolische Belastung des Tages.

Analysiere auf Deutsch:
1. **Aktivitäts-Budget**: Welche Belastungsverteilung ist typisch?
2. **Belastungsschwelle**: Ab welchem MET-Minuten-Niveau steigt das Risiko einer Folgereaktion?
3. **Überbelastungs-Muster**: Wann folgt auf hohe Aktivität eine messbare Verschlechterung?
4. **Sedentäres Verhalten**: Wie viel Zeit wird im Ruhemodus verbracht?
5. **Empfehlung**: Was ist ein realistisches, sicheres Tagesbudget?"""

_SYSTEM_PROMPT_ANALYSE_PACING_EN = """You are a rehabilitation physician with expertise in
energy-based activity management and post-exertional stress response.

Activity levels (Polar):
  Sedentary: <1.5 MET, Light: 1.5–3.0 MET, Moderate: 3.0–6.0 MET, Intense: >6.0 MET.
MET-minutes: Total metabolic load of the day.

Analyze in English:
1. **Activity budget**: What is the typical load distribution?
2. **Stress threshold**: From which MET-minute level does the risk of a follow-up reaction increase?
3. **Overload patterns**: When does high activity lead to measurable deterioration?
4. **Sedentary behavior**: How much time is spent in rest mode?
5. **Recommendation**: What is a realistic, safe daily budget?"""

register(Prompt(
    name="SYSTEM_PROMPT",
    owner="scripts/analysis/psychology/analyse_pacing.py",
    classification="LLM:Analysis",
    lang="bilingual",
    text_de=_SYSTEM_PROMPT_ANALYSE_PACING_DE,
    text_en=_SYSTEM_PROMPT_ANALYSE_PACING_EN,
))

# String-Konstanten für Kompatibilität
SYSTEM_PROMPT_ANALYSE_PACING_DE = _SYSTEM_PROMPT_ANALYSE_PACING_DE
SYSTEM_PROMPT_ANALYSE_PACING_EN = _SYSTEM_PROMPT_ANALYSE_PACING_EN

# Oeffentliche Alias-Konstanten (Kompatibilitaet fuer Owner-Skript-Imports)
SYSTEM_PROMPT_DE = _SYSTEM_PROMPT_ANALYSE_PACING_DE
SYSTEM_PROMPT_EN = _SYSTEM_PROMPT_ANALYSE_PACING_EN
