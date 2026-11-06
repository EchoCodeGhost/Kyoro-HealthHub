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
@method.de   Ausführungsreihenfolge ist abhängigkeitsbedingt. Skripte werden sequentiell
             gestartet. Bei Fehlern wird die Ausführung fortgesetzt, aber der Fehler
             wird protokolliert. --only-exact führt nur die genannten Skripte aus, in
             derselben Reihenfolge. --on-demand führt ein Skript außerhalb des vollen
             Laufs aus und protokolliert es.

             Abhängigkeitskette, aus dem SQL der Skripte abgeleitet (maschinenlesbar
             in COMPUTE_REQUIRES; "←" nennt die Skripte, deren Ausgabe gelesen wird,
             auch über Views und einzelne Metriken in measurements):
               1. compute_ecg_rpeaks    → ecg_rpeaks, ppi_raw, measurements(ecg_*)
               2. compute_arrhythmia    → arrhythmie_episoden, ppi_windows ← 1
               3. compute_ppi_dfa       → ppi_dfa, measurements(dfa_*) ← 1
               4. compute_hrv_advanced  → ppi_hrv_advanced ← 1
               5. compute_stress        → daily_stress ← 1, 4
               6. compute_sleep_hypnogram → sleep_hypnogram
               7. compute_postinfectious → pem_correlation ← 5
               8. compute_bp_pulse_bridge → measurements(heart_rate)
               9. compute_canonical     → health_canonical, source_confidence ← 6, 8
              10. compute_af_evidence   → af_evidence_scores ← 2, 3, 4, 8
              11. compute_pem           → pem_evidence_scores ← 3, 5, 6, 8
              12. compute_sleep_spo2    → measurements(sleep_spo2_min)
              13. compute_hr_zones      → daily_hr_zones ← 8
              14. compute_activity_log_from_symptoms → activity_log
              15. compute_gesamtpensum  → daily_energy_summary ← 13, 14
              16. compute_hrv_anomaly   → measurements(hrv_anomaly_*) ← 4
              17. compute_symptoms      → symptoms_canonical
              18. compute_clinical      → clinical_findings ← 5, 6, 7, 8, 9
              19. compute_personal_baseline → personal_baseline
              20. compute_daily_context → daily_context ← 5, 9, 10, 11, 15, 17
              21. compute_acute_events  → acute_events ← 8, 12, 19
              22. compute_ans_dysfunction_evidence → ans_dysfunction_evidence ← 12, 20
              23. compute_quality       → data_quality_flags ← 1, 6, 8 (läuft zuletzt)

             Drei Lesezugriffe gehen gegen die Reihenfolge und sehen den Stand des
             vorherigen Laufs (COMPUTE_READS_LATER): compute_stress liest heart_rate
             von 8 und die View sleep von 6, compute_af_evidence die View daily_summary
             von 20.
@method.en   Execution order is dependency-based. Scripts are started sequentially.
             On errors, execution continues but the error is logged. --only-exact runs
             only the named scripts, in the same order. --on-demand runs one script
             outside the full run and logs it.

             Dependency chain, derived from the scripts' SQL (machine-readable in
             COMPUTE_REQUIRES; "←" names the scripts whose output is read, including
             through views and single metrics in measurements):
               1. compute_ecg_rpeaks    → ecg_rpeaks, ppi_raw, measurements(ecg_*)
               2. compute_arrhythmia    → arrhythmie_episoden, ppi_windows ← 1
               3. compute_ppi_dfa       → ppi_dfa, measurements(dfa_*) ← 1
               4. compute_hrv_advanced  → ppi_hrv_advanced ← 1
               5. compute_stress        → daily_stress ← 1, 4
               6. compute_sleep_hypnogram → sleep_hypnogram
               7. compute_postinfectious → pem_correlation ← 5
               8. compute_bp_pulse_bridge → measurements(heart_rate)
               9. compute_canonical     → health_canonical, source_confidence ← 6, 8
              10. compute_af_evidence   → af_evidence_scores ← 2, 3, 4, 8
              11. compute_pem           → pem_evidence_scores ← 3, 5, 6, 8
              12. compute_sleep_spo2    → measurements(sleep_spo2_min)
              13. compute_hr_zones      → daily_hr_zones ← 8
              14. compute_activity_log_from_symptoms → activity_log
              15. compute_gesamtpensum  → daily_energy_summary ← 13, 14
              16. compute_hrv_anomaly   → measurements(hrv_anomaly_*) ← 4
              17. compute_symptoms      → symptoms_canonical
              18. compute_clinical      → clinical_findings ← 5, 6, 7, 8, 9
              19. compute_personal_baseline → personal_baseline
              20. compute_daily_context → daily_context ← 5, 9, 10, 11, 15, 17
              21. compute_acute_events  → acute_events ← 8, 12, 19
              22. compute_ans_dysfunction_evidence → ans_dysfunction_evidence ← 12, 20
              23. compute_quality       → data_quality_flags ← 1, 6, 8 (runs last)

             Three reads go against the order and see the previous run's state
             (COMPUTE_READS_LATER): compute_stress reads heart_rate from 8 and the
             sleep view from 6, compute_af_evidence the daily_summary view from 20.
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
    python3 compute_all.py --only-exact compute_stress,compute_canonical
    python3 compute_all.py --on-demand compute_orthostatic_detection -- --date-from 2020-01-01
"""

import argparse
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from modules.pipeline_runner import is_preview_run, parse_exact_stems, run_pipeline_script, split_forwarded_args

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
    "compute/compute_arrhythmia.py",       # → arrhythmie_episoden, ppi_windows
    "compute/compute_ppi_dfa.py",          # → ppi_dfa  (benötigt von compute_af_evidence)
    "compute/compute_hrv_advanced.py",     # → ppi_hrv_advanced
    "compute/compute_stress.py",           # → daily_stress
    "compute/compute_sleep_hypnogram.py",  # → sleep_hypnogram
    "compute/compute_postinfectious.py",        # → pem_correlation  (benötigt daily_stress)
    "compute/compute_bp_pulse_bridge.py",  # → measurements(heart_rate) aus BP-Geräte-Puls  (vor canonical!)
    "compute/compute_canonical.py",        # → health_canonical
    "compute/compute_af_evidence.py",      # → af_evidence_scores  (benötigt ppi_dfa + arrhythmie_episoden)
    "compute/compute_pem.py",             # → pem_evidence_scores  (benötigt daily_stress + measurements)
    "compute/compute_sleep_spo2.py",       # → sleep_spo2_min  (aus Roh-SpO2-Messungen, unabhängig)
    "compute/compute_hr_zones.py",         # → daily_hr_zones + tageslast  (liest Puls aus compute_bp_pulse_bridge)
    "compute/compute_activity_log_from_symptoms.py",  # → activity_log  (unabhängig, liest PWA-symptoms)
    "compute/compute_gesamtpensum.py",     # → daily_energy_summary  (benötigt daily_hr_zones + activity_log)
    "compute/compute_hrv_anomaly.py",      # → measurements (hrv_anomaly_*z, flag)  (benötigt ppi_hrv_advanced)
    "compute/compute_symptoms.py",         # → symptoms_canonical  (Kanonisierung, unabhängig)
    "compute/compute_clinical.py",         # → clinical_findings
    "compute/compute_personal_baseline.py", # → personal_baseline
    "compute/compute_daily_context.py",    # → daily_context
    "compute/compute_acute_events.py",     # → acute_events  (benötigt personal_baseline)
    "compute/compute_ans_dysfunction_evidence.py",  # → ans_dysfunction_evidence  (benötigt daily_context + sleep_spo2_min)
    "compute/compute_quality.py",          # Qualitätsprüfung, immer zuletzt
]


# Direkte Abhängigkeiten, aus dem SQL der Skripte abgeleitet: wer liest die Ausgabe
# von wem, auch über Views (heart_rate, sleep) und einzelne Metriken in measurements.
COMPUTE_REQUIRES: dict[str, list[str]] = {
    "compute/compute_ecg_rpeaks.py": [],
    "compute/compute_arrhythmia.py": ["compute/compute_ecg_rpeaks.py"],
    "compute/compute_ppi_dfa.py": ["compute/compute_ecg_rpeaks.py"],
    "compute/compute_hrv_advanced.py": ["compute/compute_ecg_rpeaks.py"],
    "compute/compute_stress.py": ["compute/compute_ecg_rpeaks.py", "compute/compute_hrv_advanced.py"],
    "compute/compute_sleep_hypnogram.py": [],
    "compute/compute_postinfectious.py": ["compute/compute_stress.py"],
    "compute/compute_bp_pulse_bridge.py": [],
    "compute/compute_canonical.py": ["compute/compute_sleep_hypnogram.py", "compute/compute_bp_pulse_bridge.py"],
    "compute/compute_af_evidence.py": [
        "compute/compute_arrhythmia.py", "compute/compute_ppi_dfa.py",
        "compute/compute_hrv_advanced.py", "compute/compute_bp_pulse_bridge.py",
    ],
    "compute/compute_pem.py": [
        "compute/compute_ppi_dfa.py", "compute/compute_stress.py",
        "compute/compute_sleep_hypnogram.py", "compute/compute_bp_pulse_bridge.py",
    ],
    "compute/compute_sleep_spo2.py": [],
    "compute/compute_hr_zones.py": ["compute/compute_bp_pulse_bridge.py"],
    "compute/compute_activity_log_from_symptoms.py": [],
    "compute/compute_gesamtpensum.py": ["compute/compute_hr_zones.py", "compute/compute_activity_log_from_symptoms.py"],
    "compute/compute_hrv_anomaly.py": ["compute/compute_hrv_advanced.py"],
    "compute/compute_symptoms.py": [],
    "compute/compute_clinical.py": [
        "compute/compute_stress.py", "compute/compute_sleep_hypnogram.py", "compute/compute_postinfectious.py",
        "compute/compute_bp_pulse_bridge.py", "compute/compute_canonical.py",
    ],
    "compute/compute_personal_baseline.py": [],
    "compute/compute_daily_context.py": [
        "compute/compute_stress.py", "compute/compute_canonical.py", "compute/compute_af_evidence.py",
        "compute/compute_pem.py", "compute/compute_gesamtpensum.py", "compute/compute_symptoms.py",
    ],
    "compute/compute_acute_events.py": [
        "compute/compute_bp_pulse_bridge.py", "compute/compute_sleep_spo2.py", "compute/compute_personal_baseline.py",
    ],
    "compute/compute_ans_dysfunction_evidence.py": ["compute/compute_sleep_spo2.py", "compute/compute_daily_context.py"],
    "compute/compute_quality.py": [
        "compute/compute_ecg_rpeaks.py", "compute/compute_sleep_hypnogram.py", "compute/compute_bp_pulse_bridge.py",
    ],
}

# Lesezugriffe auf Ausgaben, die erst später im Lauf entstehen. Das Ergebnis stützt
# sich dort auf den Stand des vorherigen Laufs.
COMPUTE_READS_LATER: dict[str, list[str]] = {
    "compute/compute_stress.py": ["compute/compute_sleep_hypnogram.py", "compute/compute_bp_pulse_bridge.py"],
    "compute/compute_af_evidence.py": ["compute/compute_daily_context.py"],
}

# Laufen nicht im vollen Lauf, nur über --on-demand
ON_DEMAND_COMPUTE_SCRIPTS = [
    "compute/compute_body_composition_from_measurements.py",
    "compute/compute_calibrate_sources.py",
    "compute/compute_histamine_triggers.py",
    "compute/compute_orthostatic_detection.py",
    "compute/compute_orthostatic_detection_nightly.py",
]


def run_on_demand(stem: str, forwarded: list[str]) -> list[str]:
    """Führt ein On-Demand-Skript aus und gibt die Fehlerliste zurück. Eine Vorschau wird nicht protokolliert."""
    script_name = next(n for n in ON_DEMAND_COMPUTE_SCRIPTS if Path(n).stem == stem)
    script_path = SCRIPT_DIR / script_name
    errors: list[str] = []
    run_pipeline_script("compute_all", script_path, [sys.executable, str(script_path), *forwarded], errors,
                        log_compute=not is_preview_run(forwarded))
    return errors


def main():
    own_args, forwarded = split_forwarded_args(sys.argv[1:])
    parser = argparse.ArgumentParser(
        description="Master-Compute: berechnet abgeleitete Metriken in korrekter Reihenfolge"
    )
    parser.add_argument("--skip-quality", action="store_true",
                        help="compute_quality.py überspringen")
    parser.add_argument("--recompute", action="store_true",
                        help="Bestehende Ergebnisse neu berechnen (wird als --recompute/--rebuild weitergegeben)")
    parser.add_argument("--only-exact", metavar="STEM[,STEM]",
                        help=t("Nur genau diese Skripte (ganzer Dateiname ohne .py), in der festen Reihenfolge",
                               "Only exactly these scripts (full file stem), in the fixed order"))
    parser.add_argument("--on-demand", metavar="STEM",
                        help=t("Ein On-Demand-Skript ausführen und protokollieren; seine Argumente folgen nach --",
                               "Run and log one on-demand script; its arguments follow after --"))
    add_lang_arg(parser)
    args = parser.parse_args(own_args)
    apply_lang_from_args(args)
    lang_flag = ["--lang", args.lang] if getattr(args, "lang", None) else []

    if forwarded and not args.on_demand:
        parser.error(t("Argumente nach -- gibt es nur mit --on-demand",
                       "Arguments after -- require --on-demand"))
    if args.on_demand:
        if args.skip_quality or args.recompute or args.only_exact:
            parser.error(t("--on-demand nimmt die Argumente des Skripts nur nach --",
                           "--on-demand takes the script's arguments only after --"))
        if args.on_demand not in {Path(n).stem for n in ON_DEMAND_COMPUTE_SCRIPTS}:
            parser.error(t(f"--on-demand: unbekannt: {args.on_demand}",
                           f"--on-demand: unknown: {args.on_demand}"))
        if args.lang:
            os.environ["KYORO_LANG"] = args.lang
        if run_on_demand(args.on_demand, forwarded):
            sys.exit(1)
        return

    scripts = COMPUTE_SCRIPTS
    if args.only_exact is not None:
        if args.skip_quality:
            parser.error(t("--only-exact und --skip-quality schließen sich aus",
                           "--only-exact and --skip-quality are mutually exclusive"))
        selected, unknown = parse_exact_stems(args.only_exact, {Path(n).stem for n in COMPUTE_SCRIPTS})
        if unknown or not selected:
            parser.error(t(f"--only-exact: unbekannt oder leer: {', '.join(unknown) or args.only_exact!r}",
                           f"--only-exact: unknown or empty: {', '.join(unknown) or args.only_exact!r}"))
        scripts = [s for s in scripts if Path(s).stem in selected]
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
