# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors

"""
Activity Analysis Module — Aktivitäts-Analyse-Skripte

@tier        infrastructure
@purpose.de  Enthält Analyse-Skripte für körperliche Aktivität und Fitness
@purpose.en  Contains analysis scripts for physical activity and fitness
@method.de   Analyse von Bewegungsdaten, Trainingsleistung, Energieverbrauch,
             funktioneller Kapazität und sitzender Lebensweise
@method.en   Analysis of motion data, workout performance, energy expenditure,
             functional capacity, and sedentary lifestyle
@reads       activity, measurements, ppi_raw, sessions
@writes      activity_analysis, workout_performance, energy_domains, functional_capacity
@limits.de   Heuristische Analysen basierend auf verfügbaren Sensordaten

@relevance.de  Ermöglicht die Analyse von Aktivitätsdaten, essentiell für die Bewegungs- und Fitnessanalyse
@relevance.en  Enables activity data analysis, essential for movement and fitness analysis
@limits.en   Heuristic analyses based on available sensor data

@usage
    python __init__.py
    python __init__.py --help
    python __init__.py --from 2024-01-01 --to 2024-12-31
"""
