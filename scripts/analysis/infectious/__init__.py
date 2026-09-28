# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors

"""
Infectious Analysis Module — Infektionsbezogene Analyse-Skripte

@tier        infrastructure
@purpose.de  Enthält Analyse-Skripte für Infektionsdaten
@purpose.en  Contains analysis scripts for infection-related data
@method.de   Analyse von Infektionsverläufen, Symptommustern und
             postinfektiösen Mustern
@method.en   Analysis of infection courses, symptom patterns,
             and post-infectious patterns
@relevance.de Ermöglicht die systematische Analyse von Infektionsdaten und
             postinfektiösen Mustern, essentiell für die Identifikation von
             Langzeitfolgen und die Abgrenzung ähnlicher Krankheitsbilder
@relevance.en Enables systematic analysis of infection data and post-infectious
             patterns, essential for identifying long-term consequences and
             distinguishing between similar clinical pictures
@reads       infectious, symptoms, measurements
@writes      infectious_analysis, postinfectious_analysis
@limits.de   Heuristische Analysen, keine medizinische Bewertung
@limits.en   Heuristic analyses, no clinical assessment

@usage
    python __init__.py
    python __init__.py --help
    python __init__.py --from 2024-01-01 --to 2024-12-31
"""
