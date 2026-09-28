# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors

"""
Analysis Module — Analyse-Skripte für Kyoro-HealthHub

@tier        infrastructure
@purpose.de  Enthält alle Analyse-Skripte für Gesundheitsdaten aus verschiedenen Domänen
@purpose.en  Contains all analysis scripts for health data from various domains
@method.de   Modul organisiert Analyse-Skripte in thematischen Unterverzeichnissen:
             - activity: Körperliche Aktivität und Fitness
             - cardiovascular: Herz-Kreislauf-Analysen
             - cycle: Menstruationszyklus-Analysen
             - environment: Umweltfaktoren
             - immunology: Immunologische Analysen
             - infectious: Infektionsbezogene Analysen
             - internal_medicine: Innere Medizin
             - metabolic: Stoffwechselanalysen
             - neurology: Neurologische Analysen
             - psychiatry: Psychiatrische Analysen
             - psychology: Psychologische Analysen
             - sleep: Schlafanalysen
@method.en   Module organizes analysis scripts in thematic subdirectories:
             - activity: Physical activity and fitness
             - cardiovascular: Cardiovascular analyses
             - cycle: Menstrual cycle analyses
             - environment: Environmental factors
             - immunology: Immunological analyses
             - infectious: Infection-related analyses
             - internal_medicine: Internal medicine
             - metabolic: Metabolic analyses
             - neurology: Neurological analyses
             - psychiatry: Psychiatric analyses
             - psychology: Psychological analyses
             - sleep: Sleep analyses
@relevance.de Bietet eine zentrale Schnittstelle für alle Gesundheitsdatenanalysen,
             essentiell für die integrierte Auswertung von Wearable-, Symptom- und
             klinischen Daten zur Unterstützung der personalisierten Medizin
@relevance.en Provides a central interface for all health data analyses, essential for
             integrated evaluation of wearable, symptom, and clinical data to support
             personalized medicine
@reads       Alle Tabellen aus Kyoro-HealthHub-Datenbank
@writes      Analyse-Ergebnisse in verschiedenen Zieltabellen
@limits.de   Analyse-Skripte sind heuristisch und nicht klinisch validiert
@limits.en   Analysis scripts are heuristic and not clinically validated

@usage
    python __init__.py
    python __init__.py --help
    python __init__.py --from 2024-01-01 --to 2024-12-31
"""
