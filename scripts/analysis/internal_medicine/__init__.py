# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors

"""
Internal Medicine Analysis Module — Innere Medizin Analyse-Skripte

@tier        infrastructure
@purpose.de  Enthält Analyse-Skripte für Daten der inneren Medizin
@purpose.en  Contains analysis scripts for internal medicine data
@method.de   Analyse von Stoffwechselparametern, Organfunktionen und
             systemischen Erkrankungen
@method.en   Analysis of metabolic parameters, organ functions,
             and systemic diseases
@reads       internal_medicine, measurements, symptoms
@writes      internal_medicine_analysis
@limits.de   Heuristische Analysen, ersetzen keine ärztliche Untersuchung

@relevance.de  Ermöglicht die Gesundheitsdatenanalyse, essentiell für die medizinische Diagnostik
@relevance.en  Enables health data analysis, essential for medical diagnostics
@limits.en   Heuristic analyses, do not replace medical examination

@usage
    python __init__.py
    python __init__.py --help
    python __init__.py --from 2024-01-01 --to 2024-12-31
"""
