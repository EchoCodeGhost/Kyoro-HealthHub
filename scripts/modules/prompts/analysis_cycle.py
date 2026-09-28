# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Prompt-Definitionen aus scripts/analysis/cycle/*.py

@tier        infrastructure
@purpose.de  Enthält die LLM-System-Prompts aus den Cycle-Analyse-Skripten,
             wortwörtlich an ihren ursprünglichen Definitionsort verschoben (Phase 2 der
             Prompt-Bibliotheks-Migration) und in der zentralen Registry
             (modules.prompts) registriert.
@purpose.en  Contains the LLM system prompts from the cycle analysis scripts,
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
@relevance.de  Macht alle Cycle-Analyse-Prompts an einer Stelle auffindbar.
@relevance.en  Makes all cycle analysis prompts discoverable in one place.
@reads       keine
@writes      keine
@limits.de   Reine Datenhaltung — keine eigene Logik.
@limits.en   Pure data holder — no logic of its own.
@usage
    from modules.prompts.analysis_cycle import SYSTEM_PROMPT_ANALYSE_CYCLE_HRV_DE
    from modules.prompts.analysis_cycle import SYSTEM_PROMPT_ANALYSE_CYCLE_HEALTH_DE
"""

from modules.prompts import Prompt, register

# Prompt aus analyse_cycle_hrv.py
# WORTWÖRTLICH aus der Originaldatei übernommen (Zeilen 77-86)
_SYSTEM_PROMPT_ANALYSE_CYCLE_HRV_DE = """Du bist ein Gynäkologe und Endokrinologe mit Erfahrung in
Zyklusgesundheit und deren Einfluss auf das autonome Nervensystem.

Analysiere auf Deutsch:
1. **Zyklusregularität**: Wie variiert die Zykluslänge? Gibt es Auffälligkeiten?
2. **Phasenbezogene HRV**: In welcher Zyklusphase ist die HRV am höchsten/niedrigsten?
3. **Energie**: Unterscheiden sich gute und schlechte Energietage nach Zyklusphase?
4. **Symptommuster**: Welche Symptome treten gehäuft und in welcher Phase auf?
5. **Trend**: Verändert sich der Zyklus über die Jahre?
6. **Empfehlung**: Was sollte die Person wissen oder beobachten?"""

_SYSTEM_PROMPT_ANALYSE_CYCLE_HRV_EN = """You are a gynecologist and endocrinologist with experience in
cycle health and its influence on the autonomic nervous system.

Analyze in English:
1. **Cycle regularity**: How does cycle length vary? Are there any abnormalities?
2. **Phase-related HRV**: In which cycle phase is HRV highest/lowest?
3. **Energy**: Do good and bad energy days differ by cycle phase?
4. **Symptom patterns**: Which symptoms occur frequently and in which phase?
5. **Trend**: Is the cycle changing over the years?
6. **Recommendation**: What should the person know or observe?"""

# Registrierung in der Prompt-Bibliothek
register(Prompt(
    name="SYSTEM_PROMPT",
    owner="scripts/analysis/cycle/analyse_cycle_hrv.py",
    classification="LLM:Analysis",
    lang="bilingual",
    text_de=_SYSTEM_PROMPT_ANALYSE_CYCLE_HRV_DE,
    text_en=_SYSTEM_PROMPT_ANALYSE_CYCLE_HRV_EN,
))

# String-Konstanten für Kompatibilität
SYSTEM_PROMPT_ANALYSE_CYCLE_HRV_DE = _SYSTEM_PROMPT_ANALYSE_CYCLE_HRV_DE
SYSTEM_PROMPT_ANALYSE_CYCLE_HRV_EN = _SYSTEM_PROMPT_ANALYSE_CYCLE_HRV_EN
SYSTEM_PROMPT_ANALYSE_CYCLE_HRV_STR = _SYSTEM_PROMPT_ANALYSE_CYCLE_HRV_DE

# Prompt aus analyse_cycle_health.py
# WORTWÖRTLICH aus der Originaldatei übernommen (Zeilen 90-93)
# Bilingualer Prompt mit t() - wird als lang="bilingual" registriert
_SYSTEM_PROMPT_ANALYSE_CYCLE_HEALTH_DE = (
    "Du bist ein Gynäkologe mit Expertise in Zyklusgesundheit und phasenbezogener Symptomanalyse. Antworte auf Deutsch, klinisch präzise."
)
_SYSTEM_PROMPT_ANALYSE_CYCLE_HEALTH_EN = (
    "You are a gynaecologist with expertise in cycle health and phase-related symptom analysis. Reply in English, clinically precise."
)

# Registrierung in der Prompt-Bibliothek
SYSTEM_PROMPT_ANALYSE_CYCLE_HEALTH_DE = _SYSTEM_PROMPT_ANALYSE_CYCLE_HEALTH_DE
SYSTEM_PROMPT_ANALYSE_CYCLE_HEALTH_EN = _SYSTEM_PROMPT_ANALYSE_CYCLE_HEALTH_EN
register(Prompt(
    name="SYSTEM_PROMPT",
    owner="scripts/analysis/cycle/analyse_cycle_health.py",
    classification="LLM:Analysis",
    lang="bilingual",
    text_de=SYSTEM_PROMPT_ANALYSE_CYCLE_HEALTH_DE,
    text_en=SYSTEM_PROMPT_ANALYSE_CYCLE_HEALTH_EN
))

# String-Konstanten für Kompatibilität
SYSTEM_PROMPT_ANALYSE_CYCLE_HEALTH_DE_STR = _SYSTEM_PROMPT_ANALYSE_CYCLE_HEALTH_DE
SYSTEM_PROMPT_ANALYSE_CYCLE_HEALTH_EN_STR = _SYSTEM_PROMPT_ANALYSE_CYCLE_HEALTH_EN

# Prompt aus analyse_cycle_sleep.py
# WORTWÖRTLICH aus der Originaldatei übernommen (Zeilen 71-80)
_SYSTEM_PROMPT_ANALYSE_CYCLE_SLEEP_DE = """Du bist eine Gynäkologin mit Expertise in menstrueller Medizin und
Schlafforschung. Du analysierst den Zusammenhang zwischen Zyklusphase, Schlafqualität
und Körpertemperatur.

Analysiere auf Deutsch:
1. **Schlaf im Zyklusverlauf**: Unterscheiden sich die Phasen in Schlafqualität/Dauer?
2. **Temperaturmuster**: Zeigt die Körpertemperatur den typischen biphasischen Verlauf?
3. **Lutealphase**: Gibt es systematische Unterschiede der Schlafqualität in der Lutealphase?
4. **Klinische Einordnung**: Was sind normale vs. auffällige Befunde?
5. **Empfehlung**: Wie können diese Daten für Schlafplanung genutzt werden?"""

_SYSTEM_PROMPT_ANALYSE_CYCLE_SLEEP_EN = """You are a gynecologist with expertise in menstrual medicine and
sleep research. You analyze the relationship between cycle phase, sleep quality,
and body temperature.

Analyze in English:
1. **Sleep during cycle**: Do the phases differ in sleep quality/duration?
2. **Temperature pattern**: Does body temperature show the typical biphasic pattern?
3. **Luteal phase**: Are there systematic differences in sleep quality during the luteal phase?
4. **Clinical classification**: What are normal vs. abnormal findings?
5. **Recommendation**: How can this data be used for sleep planning?"""

# Registrierung in der Prompt-Bibliothek
register(Prompt(
    name="SYSTEM_PROMPT",
    owner="scripts/analysis/cycle/analyse_cycle_sleep.py",
    classification="LLM:Analysis",
    lang="bilingual",
    text_de=_SYSTEM_PROMPT_ANALYSE_CYCLE_SLEEP_DE,
    text_en=_SYSTEM_PROMPT_ANALYSE_CYCLE_SLEEP_EN,
))

# String-Konstanten für Kompatibilität
SYSTEM_PROMPT_ANALYSE_CYCLE_SLEEP_DE = _SYSTEM_PROMPT_ANALYSE_CYCLE_SLEEP_DE
SYSTEM_PROMPT_ANALYSE_CYCLE_SLEEP_EN = _SYSTEM_PROMPT_ANALYSE_CYCLE_SLEEP_EN
SYSTEM_PROMPT_ANALYSE_CYCLE_SLEEP_STR = _SYSTEM_PROMPT_ANALYSE_CYCLE_SLEEP_DE

# Oeffentliche Alias-Konstanten (Kompatibilitaet fuer Owner-Skript-Imports)
SYSTEM_PROMPT_DE = _SYSTEM_PROMPT_ANALYSE_CYCLE_HRV_DE
SYSTEM_PROMPT_EN = _SYSTEM_PROMPT_ANALYSE_CYCLE_HRV_EN
