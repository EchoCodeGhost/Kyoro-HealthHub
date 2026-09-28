# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors

"""
Cycle Analysis Module — Zyklus-Analyse-Skripte

@tier        infrastructure
@purpose.de  Enthält Analyse-Skripte für Menstruationszyklus-Daten
@purpose.en  Contains analysis scripts for menstrual cycle data
@method.de   Analyse von Zykluslänge, Ovulation, Hormonverläufen und
             zyklusbedingten Symptomen
@method.en   Analysis of cycle length, ovulation, hormone patterns,
             and cycle-related symptoms
@relevance.de Ermöglicht die systematische Analyse des Menstruationszyklus und
             zyklusbedingter Gesundheitsmuster, essentiell für die Identifikation
             hormoneller Einflüsse und die personalisierte Gesundheitsvorsorge
@relevance.en Enables systematic analysis of the menstrual cycle and cycle-related
             health patterns, essential for identifying hormonal influences and
             personalized health care
@reads       cycle, symptoms, measurements
@writes      cycle_analysis, ovulation_prediction
@limits.de   Heuristische Analysen basierend auf subjektiven Daten
@limits.en   Heuristic analyses based on subjective data

@usage
    python __init__.py
    python __init__.py --help
    python __init__.py --from 2024-01-01 --to 2024-12-31
"""
