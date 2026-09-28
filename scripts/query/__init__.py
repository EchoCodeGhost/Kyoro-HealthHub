# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors

"""
Query Module — Abfrage- und Berichts-Skripte für Kyoro-HealthHub

@tier        infrastructure
@purpose.de  Enthält Abfrage- und Berichts-Skripte für Gesundheitsdaten
@purpose.en  Contains query and report scripts for health data
@method.de   Generierung von Gesundheitsberichten, Datenabfragen und
             Visualisierungen basierend auf den gespeicherten Daten
@method.en   Generation of health reports, data queries, and visualizations
             based on stored data
@reads       Alle Tabellen aus Kyoro-HealthHub-Datenbank
@writes      Berichte, Visualisierungen, Export-Dateien
@limits.de   Abfragen sind lesend, keine Datenmodifikation

@relevance.de  Ermöglicht Datenabfragen, essentiell für die Gesundheitsdatenanalyse
@relevance.en  Enables data queries, essential for health data analysis
@limits.en   Queries are read-only, no data modification

@usage
    python __init__.py
    python __init__.py --help
    python __init__.py --from 2024-01-01 --to 2024-12-31
"""
