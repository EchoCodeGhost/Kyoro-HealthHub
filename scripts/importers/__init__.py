# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors

"""
Importers Module — Datenimport-Skripte für Kyoro-HealthHub

@tier        infrastructure
@purpose.de  Enthält alle Import-Skripte für Gesundheitsdaten aus verschiedenen Quellen
@purpose.en  Contains all import scripts for health data from various sources
@method.de   Import von Daten aus Wearables (Polar, Garmin, Apple, Oura, etc.),
             manuellen Eingaben, Laborwerten, Umweltdaten und anderen Quellen
@method.en   Import of data from wearables (Polar, Garmin, Apple, Oura, etc.),
             manual entries, lab values, environmental data, and other sources
@reads       Externe Datenquellen (CSV, JSON, APIs)
@writes      Rohdaten-Tabellen in Kyoro-HealthHub-Datenbank
@limits.de   Datenformat und -qualität hängt von der Quelle ab

@relevance.de  Ermöglicht den Import von Gesundheitsdaten, essentiell für die umfassende Datenanalyse
@relevance.en  Enables import of health data, essential for comprehensive data analysis
@limits.en   Data format and quality depends on the source

@usage
    python __init__.py
    python __init__.py --help
    python __init__.py --from 2024-01-01 --to 2024-12-31
"""
