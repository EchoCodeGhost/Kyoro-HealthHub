#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Master-Analyse — führt alle analyse_*.py-Skripte aus.

@tier        infrastructure
@purpose.de  Führt alle Analyse-Skripte zentral aus und verwaltet die Ausgabe
@purpose.en  Central execution of all analysis scripts and manages output
@method.de   Durchsucht rekursiv alle analyse_*.py-Skripte im analysis/-Verzeichnis,
             erstellt für jedes Skript ein eigenes Ausgabeverzeichnis:
             <analyses_dir>/<YYYY-MM-DD>/<scriptname>/
             Plots (PNG/PDF) und Text-Output (Markdown) werden dort gespeichert.
             stdout + stderr werden als <scriptname>.log gespeichert.
             Unterstützt Filterung nach Datum, Skriptnamen und Trockenlauf.
@method.en   Recursively scans all analyse_*.py scripts in analysis/ directory,
             creates dedicated output directory for each script:
             <analyses_dir>/<YYYY-MM-DD>/<scriptname>/
             Plots (PNG/PDF) and text output (Markdown) are saved there.
             stdout + stderr are saved as <scriptname>.log.
             Supports filtering by date, script names, and dry-run mode.
@reads       Alle Tabellen, die von den einzelnen Analyse-Skripten gelesen werden
@writes      Analyseergebnisse in <analyses_dir>/<YYYY-MM-DD>/<scriptname>/
@limits.de   Keine direkte Validierung der Ergebnisse. Abhängig von den einzelnen Analyse-Skripten.

@relevance.de  Ermöglicht die umfassende Gesundheitsdatenanalyse, essentiell für die ganzheitliche Gesundheitsbewertung
@relevance.en  Enables comprehensive health data analysis, essential for holistic health assessment
@limits.en   No direct validation of results. Dependent on individual analysis scripts.
@usage
    python analyse_all.py                        # alle Skripte, mit KI-Kommentaren (Standard)
    python analyse_all.py --no-llm                # ohne KI-Kommentare
    python analyse_all.py --from 2026-01-01      # Datums-Filter
    python analyse_all.py --only afib,sleep      # nur bestimmte (Namensbestandteil)
    python analyse_all.py --skip cgm,h7          # bestimmte überspringen
    python analyse_all.py --date 2026-05-31      # wird an Skripte weitergegeben die --date kennen
    python analyse_all.py --dry-run              # zeigt was laufen würde, ohne Ausführung
"""

import argparse
import ast
import os
import subprocess
import sys
import time
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from health_config import Config as _Cfg, OWN_PERSON_ID
from modules.i18n import t, add_lang_arg, apply_lang_from_args

SCRIPT_DIR = Path(__file__).parent

# Cache: Skriptpfad -> Menge der von seinem argparse akzeptierten Flags.
# Vermeidet, dass jedes Skript pro Lauf mehrfach geparst wird.
_FLAG_CACHE: dict[Path, frozenset] = {}

# Aufrufe dieser Helper (statt eines sichtbaren add_argument(...)) haengen
# intern ein Flag an; siehe modules/i18n.add_lang_arg().
_HELPER_FLAGS = {
    "add_lang_arg": "--lang",
    "add_person_arg": "--person",
}


def _supported_flags(script_path: Path) -> frozenset:
    """Ermittelt, welche --Flags <script_path> per argparse akzeptiert.

    Liest den Quelltext statisch (AST) statt das Skript zu importieren oder
    per --help auszufuehren — kein Seiteneffekt, kein DB-Zugriff, kein Kosten-
    Subprozess pro Skript. analyse_all.py haengt sonst pauschal --from/--to/
    --date/--plot/--lang an jeden Aufruf; nicht jedes Analyse-Skript kennt
    alle davon (z. B. analyse_postcovid_sleep_wearable.py kein --from/--to),
    was mit "unrecognized arguments" (argparse Exit 2) abbricht.
    """
    cached = _FLAG_CACHE.get(script_path)
    if cached is not None:
        return cached

    flags: set = set()
    try:
        tree = ast.parse(script_path.read_text(encoding="utf-8"), filename=str(script_path))
    except (OSError, SyntaxError, UnicodeDecodeError):
        # Nicht lesbar/parsebar -> konservativ: keine Flags bekannt. run_script
        # haengt dann außer dem Skriptnamen nichts an; das Skript scheitert im
        # schlimmsten Fall an fehlenden Pflichtargumenten, nicht an unbekannten.
        _FLAG_CACHE[script_path] = frozenset()
        return frozenset()

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr == "add_argument":
            for arg in node.args:
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str) \
                        and arg.value.startswith("-"):
                    flags.add(arg.value)
        elif isinstance(func, ast.Name) and func.id in _HELPER_FLAGS:
            flags.add(_HELPER_FLAGS[func.id])

    result = frozenset(flags)
    _FLAG_CACHE[script_path] = result
    return result

# Zusätzliche Flags pro Skript (über common_flags hinaus).
# Schlüssel = Script-Stem ohne Pfad-Präfix.
SCRIPT_EXTRA_FLAGS: dict[str, list[str]] = {
    # Alle 27 konfigurierten Syndrome automatisch ranken statt nur post_covid.
    "analyse_postinfectious_diagnose": ["--syndrome", "auto"],
    # Interaktiver Anamnese-Dialog darf in unbemannt laufendem Batch nicht blockieren.
    "analyse_acute_response": ["--no-interactive"],
}

# Scripts die clinical.infection_date benötigen — werden übersprungen wenn nicht gesetzt.
REQUIRES_INFECTION_DATE = {
    "analyse_postinfectious_diagnose",
    "analyse_postinfectious_its",
    "analyse_postcovid_sleep_wearable",
    "analyse_health_timeline",
    "analyse_mcas_muster",
    "analyse_mecfs",
    "analyse_pacing",
    "analyse_pem_cascade",
    "analyse_pem_threshold",
}

# ┌─────────────────────────────────────────────────────────────────────────┐
# │  MANUELLE / ON-DEMAND Skripte → scripts/analysis/manual/               │
# │  Diese laufen NICHT in analyse_all.py. Explizit aufrufen:              │
# │                                                                         │
# │  analyse_synthesis.py       — Konsil-Gesamtbefund (LLM, teuer)         │
# │    python3 scripts/analysis/manual/analyse_synthesis.py                 │
# │                                                                         │
# │  analyse_skin.py            — Hautläsionen Verlauf + LLM-Delta         │
# │    python3 scripts/analysis/manual/analyse_skin.py --lesion 3           │
# │                                                                         │
# │  analyse_urine.py           — Urin-Heimmonitoring Trendanalyse         │
# │    python3 scripts/analysis/manual/analyse_urine.py --plot             │
# │                                                                         │
# │  analyse_ecg_session.py     — Einzelne ECG-Session (braucht --session) │
# │    python3 scripts/analysis/manual/analyse_ecg_session.py --session 42 │
# │                                                                         │
# │  analyse_lab_verlauf.py     — Verlaufstabelle aller Laborwerte         │
# │    python3 scripts/analysis/manual/analyse_lab_verlauf.py --plot        │
# │                                                                         │
# │  analyse_saliva_ph.py       — Speichel-pH-Heimmonitoring Trendanalyse  │
# │    python3 scripts/analysis/manual/analyse_saliva_ph.py --plot          │
# │                                                                         │
# │  explain_synthesis.py       — Konsil-Bericht in Alltagssprache         │
# │    python3 scripts/analysis/manual/explain_synthesis.py                 │
# │                                                                         │
# │  analyse_clinical_addendum.py — Addendum zum neuesten Konsil-Bericht   │
# │    (klinische Beobachtungen aus clinical.observations, die aus reinen  │
# │    Wearable-/Labordaten nicht ableitbar sind — LLM, teuer)             │
# │    python3 scripts/analysis/manual/analyse_clinical_addendum.py         │
# └─────────────────────────────────────────────────────────────────────────┘

# Alle automatisch laufenden Analyse-Skripte.
# Reihenfolge ist inhaltlich egal — Abhängigkeiten sind in compute_all.py geregelt.
ANALYSE_SCRIPTS = [
    "analysis/cardiovascular/analyse_afib_burden.py",
    "analysis/cardiovascular/analyse_ans_battery.py",
    "analysis/cardiovascular/analyse_ans_dysfunction_evidence.py",
    "analysis/cardiovascular/analyse_bp_sleep.py",
    "analysis/neurology/analyse_changepoint.py",
    "analysis/activity/analyse_daily_load.py",
    "analysis/activity/analyse_energy_domains.py",
    "analysis/cardiovascular/analyse_ecg_24h.py",
    "analysis/cardiovascular/analyse_ecg_longterm.py",
    "analysis/infectious/analyse_outbreak_exposure.py",
    "analysis/infectious/analyse_pathogen_exposure.py",
    "analysis/infectious/analyse_background_infection_activity.py",
    "analysis/environment/analyse_airquality_symptoms.py",
    "analysis/internal_medicine/analyse_undocumented_events.py",
    "analysis/immunology/analyse_allergens.py",
    "analysis/cardiovascular/analyse_arrhythmia.py",
    "analysis/metabolic/analyse_blood_glucose.py",
    "analysis/cardiovascular/analyse_blood_pressure.py",
    "analysis/metabolic/analyse_body_composition.py",
    "analysis/metabolic/analyse_body_temperature.py",
    "analysis/metabolic/analyse_cgm_glucose.py",
    "analysis/internal_medicine/analyse_clinical_findings.py",
    "analysis/cycle/analyse_cycle_health.py",
    "analysis/cycle/analyse_cycle_hrv.py",
    "analysis/cycle/analyse_cycle_sleep.py",
    "analysis/environment/analyse_daylight.py",
    "analysis/cardiovascular/analyse_dfa_alpha1.py",
    "analysis/cardiovascular/analyse_ecg_detail.py",
    "analysis/environment/analyse_product_exposures.py",
    "analysis/activity/analyse_fitness_vo2max.py",
    "analysis/neurology/analyse_gait.py",
    "analysis/cardiovascular/analyse_high_hr.py",
    "analysis/sleep/analyse_home_environment_sleep.py",
    "analysis/cardiovascular/analyse_hrv_fatigue.py",
    "analysis/cardiovascular/analyse_hrv_multisource.py",
    "analysis/cardiovascular/analyse_hrv_verlauf.py",
    "analysis/sleep/analyse_hypnogram.py",
    "analysis/cardiovascular/analyse_intraday_stress.py",
    "analysis/infectious/analyse_postinfectious_diagnose.py",
    "analysis/infectious/analyse_postinfectious_its.py",
    "analysis/infectious/analyse_postcovid_sleep_wearable.py",
    "analysis/infectious/analyse_acute_response.py",
    "analysis/internal_medicine/analyse_health_timeline.py",
    "analysis/immunology/analyse_mcas_muster.py",
    "analysis/neurology/analyse_mecfs.py",
    "analysis/internal_medicine/analyse_medication_effects.py",
    "analysis/internal_medicine/analyse_environmental_triggers.py",
    "analysis/internal_medicine/analyse_treatment_response.py",
    "analysis/neurology/analyse_migraine_pressure.py",
    "analysis/neurology/analyse_migraine_triggers.py",
    "analysis/internal_medicine/analyse_overview.py",
    "analysis/sleep/analyse_nightly_recharge.py",
    "analysis/sleep/analyse_nightmare.py",
    "analysis/environment/analyse_noise.py",
    "analysis/metabolic/analyse_nutrition.py",
    "analysis/cardiovascular/analyse_orthostatic.py",
    "analysis/cardiovascular/analyse_recovery.py",
    "analysis/cardiovascular/analyse_oura_temperature.py",
    "analysis/psychology/analyse_pacing.py",
    "analysis/neurology/analyse_pem.py",
    "analysis/neurology/analyse_pem_cascade.py",
    "analysis/neurology/analyse_pem_threshold.py",
    "analysis/immunology/analyse_pollen_symptoms.py",
    "analysis/cardiovascular/analyse_ptt_hrv.py",
    "analysis/sleep/analyse_respiration.py",
    "analysis/activity/analyse_sedentary.py",
    "analysis/sleep/analyse_sleep_apnea.py",
    "analysis/sleep/analyse_sleep_respiration.py",
    "analysis/sleep/analyse_sleep_environment.py",
    "analysis/sleep/analyse_sleep_multisource.py",
    "analysis/sleep/analyse_sleep_stages.py",
    "analysis/sleep/analyse_sleep_polar.py",
    "analysis/sleep/analyse_snoring_spo2.py",
    "analysis/sleep/analyse_spo2.py",
    "analysis/neurology/analyse_symptom_progression.py",
    "analysis/activity/analyse_training_load.py",
    "analysis/cardiovascular/analyse_vascular_health.py",
    "analysis/activity/analyse_workout_performance.py",
    "analysis/activity/analyse_sport_environment.py",
    "analysis/neurology/analyse_cognitive.py",
    "analysis/activity/analyse_functional_capacity.py",
    "analysis/immunology/analyse_histamine_triggers.py",
    "analysis/cardiovascular/analyse_fluid_orthostatic.py",
    "analysis/longevity/analyse_longevity.py",
]


def _script_stem(script_name: str) -> str:
    """'analysis/analyse_afib_burden.py' → 'analyse_afib_burden'"""
    return Path(script_name).stem


def _matches(stem: str, patterns: list[str]) -> bool:
    return any(p.lower() in stem.lower() for p in patterns)


def run_script(
    script_path: Path,
    out_dir: Path,
    extra_flags: list[str],
    dry_run: bool,
    plot_supported: bool = True,
    skipped_flags: list[str] | None = None,
) -> tuple[bool, float]:
    """Führt ein Analyse-Skript aus. Gibt (success, elapsed_s) zurück."""
    out_dir.mkdir(parents=True, exist_ok=True)
    log_path = out_dir / f"{script_path.stem}.log"

    cmd = [sys.executable, str(script_path)]
    if plot_supported:
        cmd.append("--plot")
    cmd += extra_flags

    if dry_run:
        print(f"  [dry-run] {' '.join(cmd)}")
        print(f"            → {out_dir}")
        if skipped_flags:
            print(f"            (nicht unterstützt, übersprungen: {', '.join(skipped_flags)})")
        return True, 0.0

    env = os.environ.copy()
    env["KYORO_ANALYSES_DIR"] = str(out_dir)
    env["MPLBACKEND"] = "Agg"  # kein interaktives Fenster im Batch-Modus

    t0 = time.monotonic()
    with open(log_path, "w", encoding="utf-8") as log:
        log.write(f"CMD: {' '.join(cmd)}\n")
        log.write(f"OUT: {out_dir}\n")
        log.write(f"TIME: {datetime.now().isoformat()}\n")
        if skipped_flags:
            log.write(f"SKIPPED (vom Skript nicht unterstützt): {', '.join(skipped_flags)}\n")
        log.write("-" * 60 + "\n")
        result = subprocess.run(
            cmd,
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        log.write(f"\nEXIT: {result.returncode}\n")
    elapsed = time.monotonic() - t0

    from modules.pipeline_runner import _log_analysis_run
    _log_analysis_run(script_path.name, result.returncode, elapsed)

    return result.returncode == 0, elapsed


def main():
    parser = argparse.ArgumentParser(
        description=t(
            "Master-Analyse: führt alle analyse_*.py-Skripte aus",
            "Master analysis: runs all analyse_*.py scripts",
        )
    )
    parser.add_argument("--llm", action="store_true",
                        help=t("Veraltet, ohne Wirkung — KI-Kommentare sind jetzt Standard",
                               "Deprecated, no effect — AI comments are now the default"))
    parser.add_argument("--no-llm", action="store_true",
                        help=t("KI-Kommentare deaktivieren (Standard: aktiviert)",
                               "Disable AI comments (default: enabled)"))
    parser.add_argument("--from", dest="date_from", metavar="DATE",
                        help="Nur Daten ab Datum (YYYY-MM-DD), wird weitergegeben")
    parser.add_argument("--to", dest="date_to", metavar="DATE",
                        help="Nur Daten bis Datum (YYYY-MM-DD), wird weitergegeben")
    parser.add_argument("--date", dest="single_date", metavar="DATE",
                        help="Einzeldatum (YYYY-MM-DD), wird weitergegeben wo unterstützt")
    parser.add_argument("--only", metavar="PATTERN[,PATTERN]",
                        help="Nur Skripte deren Name diese Begriffe enthält (Komma-getrennt)")
    parser.add_argument("--skip", metavar="PATTERN[,PATTERN]",
                        help="Skripte überspringen deren Name diese Begriffe enthält")
    parser.add_argument("--person", default=OWN_PERSON_ID,
                        help="Person (default: OWN_PERSON_ID aus health_config)")
    parser.add_argument("--run-date", metavar="DATE",
                        help="Ausgabeverzeichnis-Datum (default: heute, YYYY-MM-DD)")
    parser.add_argument("--all", dest="all_data", action="store_true",
                        help=t("Alle verfügbaren Daten (gibt --all an alle Skripte weiter)",
                               "All available data (passes --all to all scripts)"))
    parser.add_argument("--dry-run", action="store_true",
                        help=t("Zeigt was laufen würde ohne Ausführung",
                               "Show what would run without executing"))
    add_lang_arg(parser)
    args = parser.parse_args()
    apply_lang_from_args(args)

    # Ausgabe-Basisverzeichnis
    cfg = _Cfg()
    run_date = args.run_date or date.today().isoformat()
    base_dir = Path(cfg.analyses_dir).expanduser() / run_date

    # Gemeinsame Flags für alle Skripte, als (Name, Wert) — Wert None bei
    # reinen store_true-Flags. Nicht jedes Skript kennt jedes dieser Flags
    # (z. B. analyse_postcovid_sleep_wearable.py kein --from/--to); welche
    # tatsächlich angehängt werden, entscheidet sich pro Skript weiter unten
    # anhand von _supported_flags(script_path).
    common_flags: list[tuple[str, str | None]] = []
    if args.no_llm:
        common_flags.append(("--no-llm", None))
    if args.date_from:
        common_flags.append(("--from", args.date_from))
    if args.date_to:
        common_flags.append(("--to", args.date_to))
    if args.person and args.person != "self":
        common_flags.append(("--person", args.person))
    if args.single_date:
        common_flags.append(("--date", args.single_date))
    if args.all_data and not args.date_from:
        common_flags.append(("--from", cfg.data_start or "1900-01-01"))
    if getattr(args, "lang", None):
        common_flags.append(("--lang", args.lang))

    only_patterns = [p.strip() for p in args.only.split(",")] if args.only else []
    skip_patterns = [p.strip() for p in args.skip.split(",")] if args.skip else []

    cfg = _Cfg()
    has_infection_date = bool(cfg.infection_date)

    # Skript-Liste filtern
    scripts: list[Path] = []
    skipped_missing = []
    skipped_filter  = []
    skipped_no_infection = []

    for name in ANALYSE_SCRIPTS:
        path = SCRIPT_DIR / name
        stem = _script_stem(name)

        if not path.exists():
            skipped_missing.append(stem)
            continue
        if only_patterns and not _matches(stem, only_patterns):
            skipped_filter.append(stem)
            continue
        if skip_patterns and _matches(stem, skip_patterns):
            skipped_filter.append(stem)
            continue
        if stem in REQUIRES_INFECTION_DATE and not has_infection_date:
            skipped_no_infection.append(stem)
            continue
        scripts.append(path)

    total = len(scripts)
    print(t(
        f"\n[analyse_all] {total} Skripte · Ausgabe: {base_dir}",
        f"\n[analyse_all] {total} scripts · output: {base_dir}",
    ))
    if args.no_llm:
        print(t("  KI-Kommentare: deaktiviert (--no-llm)",
                "  AI comments: disabled (--no-llm)"))
    if skipped_missing:
        print(t(f"  Nicht gefunden: {', '.join(skipped_missing)}",
                f"  Not found: {', '.join(skipped_missing)}"))
    if skipped_filter:
        print(t(f"  Übersprungen (Filter): {len(skipped_filter)} Skripte",
                f"  Skipped (filter): {len(skipped_filter)} scripts"))
    if skipped_no_infection:
        print(t(f"  Übersprungen (kein infection_date): {', '.join(skipped_no_infection)}",
                f"  Skipped (no infection_date): {', '.join(skipped_no_infection)}"))
    print()

    errors:  list[str] = []
    barren:  list[str] = []   # exit 0, aber kein Bericht erzeugt
    t_total = 0.0

    for i, script_path in enumerate(scripts, 1):
        stem = script_path.stem
        out_dir = base_dir / stem

        supported = _supported_flags(script_path)
        flags: list[str] = []
        skipped_flags: list[str] = []
        for name, value in common_flags:
            if name in supported:
                flags.append(name)
                if value is not None:
                    flags.append(value)
            else:
                skipped_flags.append(name)
        flags += SCRIPT_EXTRA_FLAGS.get(stem, [])
        plot_supported = "--plot" in supported
        if not plot_supported:
            skipped_flags.append("--plot")

        print(t(f"[{i:>2}/{total}] {stem} ...", f"[{i:>2}/{total}] {stem} ..."),
              end="", flush=True)

        t_start = time.time()
        success, elapsed = run_script(
            script_path, out_dir, flags, args.dry_run,
            plot_supported=plot_supported, skipped_flags=skipped_flags,
        )
        t_total += elapsed

        # Exit 0 heisst nur "durchgelaufen", nicht "hat etwas ausgewertet". Skripte
        # ohne Quelldaten enden ebenfalls mit 0 und hinterlassen nur ein Log. Ohne
        # diese Unterscheidung meldet analyse_all 100 % Erfolg bei einem Bruchteil
        # an tatsaechlichem Ertrag.
        #
        # Nur Berichte AUS DIESEM Lauf zaehlen: bei einem zweiten Lauf am selben Tag
        # liegen die Dateien des ersten noch im Verzeichnis und wuerden ein Skript,
        # das inzwischen nichts mehr liefert, faelschlich als produktiv ausweisen.
        if args.dry_run:
            produced = True
        else:
            produced = any(p.stat().st_mtime >= t_start - 1
                           for p in out_dir.rglob("*.md"))
        if not produced and success:
            barren.append(stem)

        status = t("OK", "OK") if success else t("FEHLER", "ERROR")
        if not args.dry_run:
            mark = "" if produced or not success else t("  (ohne Bericht)", "  (no report)")
            print(f"  {status}  ({elapsed:.0f}s){mark}")
        else:
            print("")

        if not success:
            errors.append(stem)
            log_hint = out_dir / f"{stem}.log"
            print(t(f"         → Log: {log_hint}", f"         → Log: {log_hint}"))
            if log_hint.exists():
                try:
                    tail = log_hint.read_text(encoding="utf-8", errors="replace").splitlines()
                    for ln in tail[-20:]:
                        print(f"           {ln}", file=sys.stderr)
                except Exception:
                    pass

    # Zusammenfassung
    print(t(
        "\n── analyse_all abgeschlossen ────────────────────────────────",
        "\n── analyse_all completed ────────────────────────────────────",
    ))
    print(t(
        f"  Ausgeführt: {total}  |  Fehler: {len(errors)}  |  Dauer: {t_total:.0f}s",
        f"  Ran: {total}  |  Errors: {len(errors)}  |  Duration: {t_total:.0f}s",
    ))
    n_report = total - len(errors) - len(barren)
    print(t(
        f"  Datenausbeute: {n_report}/{total} mit Bericht"
        f"  |  {len(barren)} ohne Bericht",
        f"  Data yield: {n_report}/{total} produced a report"
        f"  |  {len(barren)} produced none",
    ))
    print(t(f"  Ausgabe:    {base_dir}", f"  Output:     {base_dir}"))

    if barren:
        print(t(
            f"\n  Ohne Bericht (fehlerfrei gelaufen, kein Report erzeugt):\n"
            f"    {', '.join(barren)}\n"
            f"  Ursache offen — leere abgeleitete Tabellen sind bekanntes Verhalten;\n"
            f"  bei frischer DB zuerst compute_all.py ausfuehren (s. openspec/specs/\n"
            f"  pipeline-architecture, 'Stille Leerergebnisse als bekanntes Verhalten').",
            f"\n  No report (ran cleanly, produced no report):\n"
            f"    {', '.join(barren)}\n"
            f"  Cause undetermined — empty derived tables are known behaviour;\n"
            f"  on a fresh DB run compute_all.py first (see openspec/specs/\n"
            f"  pipeline-architecture, 'Silent empty results as known behavior').",
        ))

    if errors:
        print(t(f"\n  Fehlgeschlagen: {', '.join(errors)}",
                f"\n  Failed: {', '.join(errors)}"), file=sys.stderr)
        error_pct = len(errors) / max(total, 1) * 100
        if error_pct > 30:
            print(t(f"  ⚠ {error_pct:.0f}% der Skripte fehlgeschlagen — Systemzustand prüfen!",
                    f"  ⚠ {error_pct:.0f}% of scripts failed — check system state!"),
                  file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
