# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors

"""
Metabolic Analysis Module — Stoffwechsel-Analyse-Skripte

@tier        infrastructure
@purpose.de  Enthält Analyse-Skripte für Stoffwechsel-Daten
@purpose.en  Contains analysis scripts for metabolic data
@method.de   Analyse von Glukosewerten, Insulinresistenz, Fettstoffwechsel
             und anderen metabolischen Parametern
@method.en   Analysis of glucose levels, insulin resistance, fat metabolism,
             and other metabolic parameters
@reads       metabolic, cgm, measurements
@writes      metabolic_analysis, glucose_analysis
@limits.de   Heuristische Analysen, keine Ersatz für Labordiagnostik

@relevance.de  Ermöglicht die Stoffwechselanalyse, essentiell für die metabolische Gesundheit
@relevance.en  Enables metabolic analysis, essential for metabolic health
@limits.en   Heuristic analyses, not a substitute for laboratory diagnostics

@usage
    python __init__.py
    python __init__.py --help
    python __init__.py --from 2024-01-01 --to 2024-12-31
"""
