# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors

"""
Cardiovascular Analysis Module — Herz-Kreislauf-Analyse-Skripte

@tier        infrastructure
@purpose.de  Enthält Analyse-Skripte für Herz-Kreislauf-Daten
@purpose.en  Contains analysis scripts for cardiovascular data
@method.de   Analyse von Herzfrequenz, Herzrhythmusmustern, AF-Episoden,
             AF-Belastung und anderen kardiovaskulären Parametern
@method.en   Analysis of heart rate, arrhythmia patterns, AF episodes,
             AF burden, and other cardiovascular parameters
@reads       ppi_raw, ecg, measurements, afib_episodes
@writes      cardiovascular_analysis, afib_burden, arrhythmia_analysis
@limits.de   Heuristische Analysen, nicht für klinische Bewertung geeignet

@relevance.de  Ermöglicht die kardiovaskuläre Analyse, essentiell für die Herz-Kreislauf-Diagnostik
@relevance.en  Enables cardiovascular analysis, essential for cardiac diagnostics
@limits.en   Heuristic analyses, not suitable for clinical evaluation

@usage
    python __init__.py
    python __init__.py --help
    python __init__.py --from 2024-01-01 --to 2024-12-31
"""
