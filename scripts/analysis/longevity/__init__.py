# SPDX-License-Identifier: GPL-3.0-or-later
"""
Longevity-Analyse: biologisches Alter, Longevity-Biomarker und Genetik.

@tier        infrastructure
@purpose.de  Analyse-Paket für Longevity-Medizin: biologisches Alter, Inflammaging,
             Hormonstatus, Mikronährstoffe, genetische Longevity-Varianten und HRV-Trends.
@purpose.en  Analysis package for longevity medicine: biological age, inflammaging,
             hormone status, micronutrients, genetic longevity variants and HRV trends.
@method.de   Sammelt Skripte, die Longevity-relevante Daten aus lab_manual,
             genetic_variants, genetic_risk_markers und measurements auswerten.
@method.en   Collects scripts that evaluate longevity-relevant data from lab_manual,
             genetic_variants, genetic_risk_markers and measurements.
@reads       lab_manual, genetic_variants, genetic_risk_markers, measurements
@writes      analyses/longevity/
@limits.de   Heuristisch. Kein Ersatz für ärztliche Beratung.

@relevance.de  Ermöglicht die Gesundheitsdatenanalyse, essentiell für die medizinische Diagnostik
@relevance.en  Enables health data analysis, essential for medical diagnostics
@limits.en   Heuristic. Not a substitute for medical advice.
@usage
    python3 scripts/analysis/longevity/analyse_longevity.py
    python3 scripts/analysis/longevity/analyse_longevity.py --plot --no-llm
"""
