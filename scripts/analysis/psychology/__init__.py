# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors

"""
Psychology Analysis Module — Psychologische Analyse-Skripte

@tier        infrastructure
@purpose.de  Enthält Analyse-Skripte für psychologische Daten
@purpose.en  Contains analysis scripts for psychological data
@method.de   Analyse von Stresslevel, kognitiver Leistung, emotionalem Wohlbefinden
             und anderen psychologischen Parametern
@method.en   Analysis of stress levels, cognitive performance, emotional well-being,
             and other psychological parameters
@relevance.de Ermöglicht die systematische Analyse psychologischer Daten und Muster,
             essentiell für das Verständnis des Zusammenhangs zwischen körperlicher
             Gesundheit und psychischem Wohlbefinden
@relevance.en Enables systematic analysis of psychological data and patterns, essential
             for understanding the relationship between physical health and mental well-being
@reads       psychology, symptoms, cognitive_tests
@writes      psychology_analysis, stress_analysis
@limits.de   Heuristische Analysen, keine psychologische Diagnostik
@limits.en   Heuristic analyses, no psychological diagnostics

@usage
    python __init__.py
    python __init__.py --help
    python __init__.py --from 2024-01-01 --to 2024-12-31
"""
