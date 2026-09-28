# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors

"""
Sleep Analysis Module — Schlaf-Analyse-Skripte

@tier        infrastructure
@purpose.de  Enthält Analyse-Skripte für Schlaf-Daten
@purpose.en  Contains analysis scripts for sleep data
@method.de   Analyse von Schlafdauer, Schlafqualität, Schlafstadien,
             Hypnogrammen und schlafbezogenen Atmungsstörungen
@method.en   Analysis of sleep duration, sleep quality, sleep stages,
             hypnograms, and sleep-related breathing disorders
@reads       sleep, ppi_raw, spo2, measurements
@writes      sleep_analysis, hypnogram_analysis, sleep_stages
@limits.de   Heuristische Analysen, ersetzen keine Schlaflabor-Untersuchung

@relevance.de  Ermöglicht die Schlafanalyse, essentiell für die Schlafforschung und Gesundheitsüberwachung
@relevance.en  Enables sleep analysis, essential for sleep research and health monitoring
@limits.en   Heuristic analyses, do not replace sleep lab examination

@usage
    python __init__.py
    python __init__.py --help
    python __init__.py --from 2024-01-01 --to 2024-12-31
"""
