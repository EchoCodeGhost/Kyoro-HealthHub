# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors

"""
Compute Module — Berechnungs-Skripte für Kyoro-HealthHub

@tier        infrastructure
@purpose.de  Enthält alle Berechnungs- und Analyse-Skripte für Gesundheitsmetriken
@purpose.en  Contains all computation and analysis scripts for health metrics
@method.de   Berechnung von HRV-Metriken, Herzfrequenzanalysen, Schlafparametern,
             Stresslevel, Stoffwechselwerten und anderen Gesundheitsindikatoren
@method.en   Computation of HRV metrics, heart rate analyses, sleep parameters,
             stress levels, metabolic values, and other health indicators
@reads       ppi_raw, ecg, measurements, sessions
@writes      ppi_hrv_advanced, hrv_daily, sleep_analysis, clinical_analysis
@limits.de   Berechnungen basieren auf verfügbaren Sensordaten

@relevance.de  Ermöglicht die Berechnung von Gesundheitsmetriken, essentiell für die Datenanalyse
@relevance.en  Enables calculation of health metrics, essential for data analysis
@limits.en   Computations are based on available sensor data

@usage
    python __init__.py
    python __init__.py --help
    python __init__.py --from 2024-01-01 --to 2024-12-31
"""
