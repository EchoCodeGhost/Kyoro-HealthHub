#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Master Compute — Orchestriert die Ausführung aller Compute-Skripte.

@tier        infrastructure
@purpose.de  Orchestriert die Ausführung aller Compute-Skripte in der korrekten
             Abhängigkeitsreihenfolge. Stell sicher, dass alle abgeleiteten Metriken
             aktuell sind, bevor Abfragen oder Analysen durchgeführt werden.
@purpose.en  Orchestrates the execution of all compute scripts in the correct
             dependency order. Ensures all derived metrics are up-to-date before
             queries or analyses are performed.
@method.de   Ausführungsreihenfolge ist abhänigkeitsbedingt. Skripte werden sequentiell
             gestartet, wobei jedes Skript nur dann ausgeführt wird, wenn seine
             Abhängigkeiten (Eingabetabellen) verfügbar sind. Bei Fehlern wird die
             Ausführung fortgesetzt, aber der Fehler wird protokolliert.
             
             Abhängigkeitskette:
               1. compute_ecg_rpeaks    → ecg_rpeaks, ppi_raw (unabhängig)
               2. compute_arrhythmia    → arrhythmie_episoden (benötigt ppi_raw)
               3. compute_ppi_dfa       → ppi_dfa (unabhängig, liest ppi_raw)
               4. compute_hrv_advanced  → ppi_hrv_advanced (unabhängig, liest ppi_raw)
               5. compute_stress        → daily_stress (unabhängig, liest Rohtabellen)
               6. compute_sleep_hypnogram → sleep_hypnogram (unabhängig, liest Schlaf-Raw)
               7. compute_postinfectious → pem_correlation (benötigt daily_stress)
               8. compute_bp_pulse_bridge → measurements(heart_rate) aus BP-Geräte-Puls (unabhängig, vor canonical!)
               9. compute_canonical     → health_canonical (benötigt daily_stress)
              10. compute_af_evidence   → af_evidence_scores (benötigt ppi_dfa + arrhythmie_episoden)
              11. compute_pem           → pem_evidence_scores (benötigt daily_stress + measurements)
              12. compute_sleep_spo2    → sleep_spo2_min (unabhängig)
              13. compute_hr_zones      → daily_hr_zones (unabhängig)
              14. compute_activity_log_from_symptoms → activity_log (unabhängig, liest PWA-symptoms)
              15. compute_gesamtpensum  → daily_energy_summary (benötigt daily_hr_zones + activity_log)
              16. compute_hrv_anomaly   → measurements (hrv_anomaly_*) (benötigt ppi_hrv_advanced)
              17. compute_symptoms      → symptoms_canonical (unabhängig)
              18. compute_clinical      → clinical_findings (benötigt pem_correlation + health_canonical)
              19. compute_personal_baseline → personal_baseline (benötigt alle Metriken)
              20. compute_daily_context → daily_context (benötigt alle vorherigen)
              21. compute_acute_events  → acute_events (benötigt personal_baseline)
              22. compute_ans_dysfunction_evidence → ans_dysfunction_evidence (benötigt daily_context + personal_baseline)
              23. compute_quality       → data_quality_flags (validiert alles, läuft zuletzt)
@method.en   Execution order is dependency-based. Scripts are started sequentially,
             with each script only executing if its dependencies (input tables) are
             available. On errors, execution continues but the error is logged.
             
             Dependency chain:
               1. compute_ecg_rpeaks    → ecg_rpeaks, ppi_raw (independent)
               2. compute_arrhythmia    → arrhythmie_episoden (requires ppi_raw)
               3. compute_ppi_dfa       → ppi_dfa (independent, reads ppi_raw)
               4. compute_hrv_advanced  → ppi_hrv_advanced (independent, reads ppi_raw)
               5. compute_stress        → daily_stress (independent, reads raw tables)
               6. compute_sleep_hypnogram → sleep_hypnogram (independent, reads sleep raw)
               7. compute_postinfectious → pem_correlation (requires daily_stress)
               8. compute_bp_pulse_bridge → measurements(heart_rate) from BP device pulse (independent, before canonical!)
               9. compute_canonical     → health_canonical (requires daily_stress)
              10. compute_af_evidence   → af_evidence_scores (requires ppi_dfa + arrhythmie_episoden)
              11. compute_pem           → pem_evidence_scores (requires daily_stress + measurements)
              12. compute_sleep_spo2    → sleep_spo2_min (independent)
              13. compute_hr_zones      → daily_hr_zones (independent)
              14. compute_activity_log_from_symptoms → activity_log (independent, reads PWA symptoms)
              15. compute_gesamtpensum  → daily_energy_summary (requires daily_hr_zones + activity_log)
              16. compute_hrv_anomaly   → measurements (hrv_anomaly_*) (requires ppi_hrv_advanced)
              17. compute_symptoms      → symptoms_canonical (independent)
              18. compute_clinical      → clinical_findings (requires pem_correlation + health_canonical)
              19. compute_personal_baseline → personal_baseline (requires all metrics)
              20. compute_daily_context → daily_context (requires all previous)
              21. compute_acute_events  → acute_events (requires personal_baseline)
              22. compute_ans_dysfunction_evidence → ans_dysfunction_evidence (requires daily_context + personal_baseline)
              23. compute_quality       → data_quality_flags (validates all, runs last)
@reads       Keine direkten Eingabetabellen (orchestriert andere Skripte)
@writes      compute_log in health.db (Skriptname, Git-Commit, Returncode, Laufzeit
             pro Compute-Lauf — s. modules/pipeline_runner.py); sonst keine direkten
             Ausgabetabellen (orchestriert andere Skripte)
@limits.de   Keine medizinische Interpretation. Rein technische Orchestrierung.
             Fehlschläge einzelner Skripte führen nicht zum Abbruch des gesamten
             Prozesses, können aber zu unvollständigen Daten führen.

@relevance.de  Bietet Gesundheitsdatenfunktionen, essentiell für die medizinische Datenverarbeitung
@relevance.en  Provides health data functions, essential for medical data processing
@limits.en   No medical interpretation. Pure technical orchestration.
             Failures of individual scripts do not abort the entire process,
             but may result in incomplete data.
@usage
    python3 compute_all.py                  # alle Compute-Scripts
    python3 compute_all.py --skip-quality   # ohne abschließende Qualitätsprüfung
    python3 compute_all.py --recompute      # bestehende Ergebnisse neu berechnen
    python3 compute_all.py --from 2024-01-01 --to 2024-12-31
    python3 compute_all.py --person self
"""

import argparse
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from modules.pipeline_runner import run_pipeline_script

SCRIPT_DIR = Path(__file__).parent

# Scripts die --recompute/--rebuild unterstützen, mit ihrem jeweiligen Flag-Namen
RECOMPUTE_FLAGS: dict[str, str] = {
    "compute/compute_ecg_rpeaks.py":       "--recompute",
    "compute/compute_gesamtpensum.py":     "--recompute",
    "compute/compute_af_evidence.py":      "--recompute",
    "compute/compute_hrv_advanced.py":     "--rebuild",
    "compute/compute_ppi_dfa.py":          "--recompute",
    "compute/compute_sleep_hypnogram.py":  "--rebuild",
    "compute/compute_hr_zones.py":         "--recompute",
    "compute/compute_daily_context.py":    "--recompute",
    "compute/compute_acute_events.py":     "--recompute",
    # compute_ans_dysfunction_evidence kennt --recompute, hat dasselbe INSERT-
    # OR-IGNORE-Verhalten wie compute_pem.py unten: ohne Flag bleiben
    # bestehende Zeilen bei Kriterien-/Gewichtungs-Aenderungen stumm auf
    # altem Stand.
    "compute/compute_ans_dysfunction_evidence.py": "--recompute",
    # compute_pem kennt --recompute, stand hier aber nicht. Ohne Flag setzt das
    # Skript bei MAX(date) auf und schreibt mit INSERT OR IGNORE — bestehende Zeilen
    # bleiben unangetastet. `compute_all --recompute` hat pem_evidence_scores damit
    # nie neu gebaut, Aenderungen an der Score-Logik wirkten nur auf neue Tage
    # waehrend die Historie stumm auf altem Stand blieb.
    "compute/compute_pem.py":              "--recompute",
}

# Ausführungsreihenfolge ist abhängigkeitsbedingt — nicht ändern
COMPUTE_SCRIPTS = [
    "compute/compute_ecg_rpeaks.py",       # → ecg_rpeaks, ppi_raw (ecg_apple)  [vor arrhythmia!]
    "compute/compute_arrhythmia.py",       # → arrhythmie_episoden
    "compute/compute_ppi_dfa.py",          # → ppi_dfa  (benötigt von compute_af_evidence)
    "compute/compute_hrv_advanced.py",     # → ppi_windows
    "compute/compute_stress.py",           # → daily_stress
    "compute/compute_sleep_hypnogram.py",  # → sleep_hypnogram
    "compute/compute_postinfectious.py",        # → pem_correlation  (benötigt daily_stress)
    "compute/compute_bp_pulse_bridge.py",  # → measurements(heart_rate) aus BP-Geräte-Puls  (vor canonical!)
    "compute/compute_canonical.py",        # → health_canonical  (benötigt daily_stress)
    "compute/compute_af_evidence.py",      # → af_evidence_scores  (benötigt ppi_dfa + arrhythmie_episoden)
    "compute/compute_pem.py",             # → pem_evidence_scores  (benötigt daily_stress + measurements)
    "compute/compute_sleep_spo2.py",       # → sleep_spo2_min  (aus Roh-SpO2-Messungen, unabhängig)
    "compute/compute_hr_zones.py",         # → daily_hr_zones + tageslast  (unabhängig)
    "compute/compute_activity_log_from_symptoms.py",  # → activity_log  (unabhängig, liest PWA-symptoms)
    "compute/compute_gesamtpensum.py",     # → daily_energy_summary  (benötigt daily_hr_zones + activity_log)
    "compute/compute_hrv_anomaly.py",      # → measurements (hrv_anomaly_*z, flag)  (benötigt ppi_hrv_advanced)
    "compute/compute_symptoms.py",         # → symptoms_canonical  (Kanonisierung, unabhängig)
    "compute/compute_clinical.py",         # → clinical_findings
    "compute/compute_personal_baseline.py", # → personal_baseline  (nach allen Metriken)
    "compute/compute_daily_context.py",    # → daily_context  (benötigt alle vorherigen)
    "compute/compute_acute_events.py",     # → acute_events  (benötigt personal_baseline)
    "compute/compute_ans_dysfunction_evidence.py",  # → ans_dysfunction_evidence  (benötigt daily_context + personal_baseline)
    "compute/compute_quality.py",          # Qualitätsprüfung, immer zuletzt
]


def main():
    parser = argparse.ArgumentParser(
        description="Master-Compute: berechnet abgeleitete Metriken in korrekter Reihenfolge"
    )
    parser.add_argument("--skip-quality", action="store_true",
                        help="compute_quality.py überspringen")
    parser.add_argument("--recompute", action="store_true",
                        help="Bestehende Ergebnisse neu berechnen (wird als --recompute/--rebuild weitergegeben)")
    add_lang_arg(parser)
    args = parser.parse_args()
    apply_lang_from_args(args)
    lang_flag = ["--lang", args.lang] if getattr(args, "lang", None) else []

    scripts = COMPUTE_SCRIPTS
    if args.skip_quality:
        scripts = [s for s in scripts if "quality" not in s]

    errors = []
    for script_name in scripts:
        script_path = SCRIPT_DIR / script_name
        if not script_path.exists():
            print(t(f"[compute_all] Überspringe {script_name} (nicht gefunden)", f"[compute_all] Skipping {script_name} (not found)"))
            continue

        cmd = [sys.executable, str(script_path)] + lang_flag
        if args.recompute and script_name in RECOMPUTE_FLAGS:
            cmd.append(RECOMPUTE_FLAGS[script_name])
        run_pipeline_script("compute_all", script_path, cmd, errors, log_compute=True)

    if errors:
        print(t(f"\n[compute_all] {len(errors)} Scripts mit Fehlern: {', '.join(errors)}", f"\n[compute_all] {len(errors)} scripts with errors: {', '.join(errors)}"),
              file=sys.stderr)
        sys.exit(1)
    else:
        print(t("\n[compute_all] Alle Compute-Scripts erfolgreich abgeschlossen.",
                "\n[compute_all] All compute scripts completed successfully."))


if __name__ == "__main__":
    main()
