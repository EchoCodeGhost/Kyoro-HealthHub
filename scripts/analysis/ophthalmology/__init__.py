# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors

"""
Ophthalmology Analysis Module — Ophthalmologische Analyse-Skripte

@tier        infrastructure
@purpose.de  Enthält Analyse-Skripte für ophthalmologische Bilddaten
@purpose.en  Contains analysis scripts for ophthalmological imaging data
@method.de   VLM-gestützte Auswertung von Fundusfotos (Sehnervkopf, Gefäße, Netzhaut)
@method.en   VLM-based evaluation of fundus photographs (optic disc, vessels, retina)
@relevance.de Ermöglicht die automatisierte Analyse ophthalmologischer Bilddaten,
             essentiell für die Früherkennung von Netzhauterkrankungen und die
             Unterstützung der ophthalmologischen Diagnostik
@relevance.en Enables automated analysis of ophthalmological imaging data, essential
             for early detection of retinal diseases and supporting ophthalmological assessment
@reads       imaging_analysis
@writes      imaging_analysis
@limits.de   Heuristische Analysen, ersetzen keine ophthalmologische Diagnostik
@limits.en   Heuristic analyses, do not replace ophthalmological diagnostics

@usage
    python __init__.py
    python __init__.py --help
"""
