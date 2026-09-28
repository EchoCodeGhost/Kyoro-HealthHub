# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors

"""
Psychiatry Analysis Module — Psychiatrische Analyse-Skripte

@tier        infrastructure
@purpose.de  Enthält Analyse-Skripte für psychiatrische Daten
@purpose.en  Contains analysis scripts for psychiatric data
@method.de   Analyse von Stimmungsverläufen, Angstsymptomen, Affektstörungen
             und anderen psychiatrischen Parametern
@method.en   Analysis of mood patterns, anxiety symptoms, affective disorders,
             and other psychiatric parameters
@reads       psychiatry, symptoms, mood
@writes      psychiatry_analysis, mood_analysis
@limits.de   Heuristische Analysen, ersetzen keine psychiatrische Diagnostik

@relevance.de  Ermöglicht die Gesundheitsdatenanalyse, essentiell für die medizinische Diagnostik
@relevance.en  Enables health data analysis, essential for medical diagnostics
@limits.en   Heuristic analyses, do not replace psychiatric diagnostics

@usage
    python __init__.py
    python __init__.py --help
    python __init__.py --from 2024-01-01 --to 2024-12-31
"""
