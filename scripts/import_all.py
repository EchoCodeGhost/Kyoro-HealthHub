#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Master Health Data Import

@tier        infrastructure
@purpose.de  Ruft alle verfügbaren Importer als Subprozesse auf und koordiniert
             den Import von Gesundheitsdaten aus verschiedenen Quellen in die
             health.db-Datenbank.
@purpose.en  Calls all available importers as subprocesses and coordinates the
             import of health data from various sources into the health.db database.
@method.de   Ausführungsreihenfolge: 0) registry.json → health.db.devices
             abgleichen (sync_registry_to_devices.run(), nicht-blockierend),
             1) process_inbox.py für Inbox-Dateien, 2) Dateibasierte
             Importer, 3) API-Importer. Jeder Importer wird als Subprozess
             aufgerufen. Fehler werden gesammelt und am Ende zusammenfassend
             angezeigt. Nach dem Import wird automatisch post_import_sanitize
             ausgeführt.
             --person wird NUR an Importer mit verifiziertem --person-Flag
             weitergegeben (_PERSON_AWARE-Allowlist) — wichtig bei geteilten
             Geraeten (z.B. ein Sensor, den auch eine andere Person nutzt), wo
             die Geraete-ID allein nichts ueber die Person aussagt. Blindes
             Weiterreichen an alle Importer ist bewusst NICHT implementiert: die
             meisten kennen --person nicht und wuerden mit "unrecognized
             arguments" abstuerzen. Vollstaendige In-Process-run()-Umstellung
             (statt Subprozess-Flag-Weiterreichen) ist als groessere Folge-Change
             geplant, s. openspec/changes/switch-import-all-to-inprocess-run/.
@method.en   Execution order: 0) sync registry.json → health.db.devices
             (sync_registry_to_devices.run(), non-blocking), 1)
             process_inbox.py for inbox files, 2) File-based importers, 3)
             API importers. Each importer is called as a subprocess. Errors
             are collected and displayed summarily at the end. After import,
             post_import_sanitize is automatically executed.
             --person is forwarded ONLY to importers with a verified --person
             flag (_PERSON_AWARE allowlist) — important for shared devices
             (e.g. a sensor also used by another person), where the device id
             alone says nothing about the person. Blindly forwarding to every
             importer is deliberately NOT implemented: most don't know
             --person and would crash with "unrecognized arguments". A full
             switch to in-process run() calls (instead of forwarding a
             subprocess flag) is planned as a larger follow-up change, see
             openspec/changes/switch-import-all-to-inprocess-run/.
@reads       imports/_inbox/ (Dateien), verschiedene API-Datenquellen
@writes      health.db (alle Tabellen basierend auf importierten Daten)
@limits.de   Abhängig von der Verfügbarkeit und Korrektheit der einzelnen Importer.
             Keine zentrale Datenvalidierung. Fehler in Subprozessen werden
             nicht zwingend als Fehler des Hauptskripts behandelt. Keine medizinische
             Interpretation.

@relevance.de  Bietet Gesundheitsdatenfunktionen, essentiell für die medizinische Datenverarbeitung
@relevance.en  Provides health data functions, essential for medical data processing
@limits.en   Dependent on the availability and correctness of individual importers.
             No central data validation. Errors in subprocesses are not necessarily
             treated as errors of the main script. No medical interpretation.

Ablauf:
  -1. sync_registry_to_devices.run() — registry.json → health.db.devices abgleichen
  0. process_inbox.py     — Dateien aus imports/_inbox/ erkennen und routen (ZIP + Einzeldateien)
  1. Dateibasierte Importer (Polar, Apple Health, Oura CSV …)
  2. API-Importer (Oura API, Garmin Download + Import …)

Automatische Importer (kein Dateiargument nötig):
  import_polar.py            — Polar GDPR Export (JSON)
  import_apple.py            — Apple Health (XML)
  import_ecg_apple.py        — Apple Watch EKG-CSVs (electrocardiograms/-Folder)
  import_homeassistant.py    — Home Assistant (falls vorhanden)
  import_oura.py             — Oura Ring API
  import_polar_accesslink.py — Polar AccessLink API (Schlaf, Nightly Recharge, Trainings)
  import_oura_csv.py         — Oura CSV-Export (Membership Hub)
  import_beurer.py           — Beurer Waage/Blood glucose/Temperatur
  import_omron.py            — Omron Blood pressure
  import_womanlog.py         — WomanLog CSV (scannt imports/WomanLogApp/)
  import_bearable.py         — Bearable CSV (scannt imports/bearable/)
  import_migraine.py         — Migraine-App (.mbu)
  import_symptom_diary.py    — Symptomtagebuch
  import_sleep_cycle.py      — Sleep Cycle CSV
  import_fddb.py             — FDDB Ernährungstagebuch
  garmin_download.py         — Garmin Connect Download
  import_garmin.py           — Garmin Import
  import_garmin_gdpr.py      — Garmin GDPR-Export (scannt imports/garmin_gdpr/, --dir überschreibbar)
  import_6mwt.py             — 6-Minuten-Gehtest (scannt imports/6mwt/)
  import_travel_environment.py — Reiseklima + Krankheitsausbrüche aus travel_history
  import_lab_csv.py          — Manuelle Laborbefund-CSVs (medicine/laborbefunde/ + imports/manual/)
  import_camerahRV.py        — CameraHRV App CSV-Exporte (scannt imports/camerahRV/)

Manuell — Datei-/Verzeichnis-Argument erforderlich:
  python3 importers/import_lab_results.py <datei.pdf>
  python3 importers/import_hrv4training.py --file export.csv
  python3 importers/import_hrv4training.py --dir ~/Downloads/
  python3 importers/import_hrv_logger.py --dir <pfad>
  python3 importers/import_ecg_logger.py --dir <pfad>
  python3 importers/import_kubios_orthostatic.py --file export.txt
  python3 importers/import_kubios_screenshot.py --file screenshot.png
  python3 importers/import_ecowitt_csv.py <datei.csv>
  python3 importers/import_aemet.py --lat <lat> --lon <lon>   # Spanien-Wetter

Manuell — medizinische Befunde / Bilddaten (→ medicine.db / medicine_imaging.db):
  python3 importers/import_urine_strip.py <datei.csv>   # Template: templates/urine_strip_template.csv
  python3 importers/import_skin.py foto.jpg --location "..."
  python3 importers/import_skin.py --lesion-id 3 folgefoto.jpg
  python3 importers/import_skin.py --update-lesion 3 --histology "..." --histology-date ...
  python3 importers/import_skin.py --list-lesions
  python3 importers/import_fundus.py <datei.dcm|.jpg> --analyse

@usage
    python import_all.py
    python import_all.py --update
    python import_all.py --update --person PER-xxxxxxxx
"""

import argparse
import sys
from pathlib import Path
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from modules.pipeline_runner import run_pipeline_script
from utils.post_import_sanitize import run as _run_post_import_sanitize
from utils.sync_registry_to_devices import run as _run_sync_registry_to_devices
from utils.check_outbreak_source_health import run as _run_outbreak_source_health

sys.path.insert(0, str(Path(__file__).parent))
from health_config import Config as _Cfg

SCRIPT_DIR = Path(__file__).parent

# Importer in Ausführungsreihenfolge; wird stillschweigend übersprungen if nicht vorhanden
IMPORTERS = [
    "importers/import_polar.py",
    "importers/import_apple.py",
    "importers/import_homeassistant.py",
    "importers/import_oura.py",
    "importers/import_polar_accesslink.py",
    "importers/import_oura_csv.py",
    "importers/import_beurer.py",
    "importers/import_renpho_tape.py",
    "importers/import_cgm.py",
    "importers/import_omron.py",
    "importers/import_withings.py",
    "importers/import_hilo_pdf.py",
    "importers/import_medical_motion.py",
    "importers/import_womanlog.py",
    "importers/import_bearable.py",
    "importers/import_migraine.py",
    "importers/import_symptom_diary.py",
    "importers/import_symptomtagebuch.py",
    "importers/import_kyoro_symptoms.py",
    "importers/import_sleep_cycle.py",
    "importers/import_fddb.py",
    "importers/garmin_download.py",
    "importers/import_garmin.py",
    "importers/import_garmin_gdpr.py",
    "importers/import_dwd_brightsky.py",
    "importers/import_airquality.py",
    "importers/import_pollen_dwd.py",
    "importers/import_pollen_google.py",
    "importers/import_outbreak_data.py",
    "importers/import_amelag.py",
    "importers/import_notaufnahme.py",
    "importers/import_tracks.py",
    "importers/import_cognitive_tests.py",
    "importers/import_orthostatic_manual.py",
    "importers/import_histamine_diary.py",
    "importers/import_fluid_intake.py",
    "importers/import_6mwt.py",
    "importers/import_travel_environment.py",
    "importers/import_lab_csv.py",
    "importers/import_shotsy.py",
    "importers/import_camerahRV.py",
    "importers/import_activity_log.py",
    "importers/import_wellue_o2ring.py",
    # Genetik-Importer (brauchen Dateiargument — werden hier übersprungen,
    # direkt aufrufen: import_genetics_manual.py, import_genetics_aniva.py, etc.)
    # import_nightmare_log.py braucht ebenfalls ein Dateiargument (CSV) —
    # direkt aufrufen: python3 scripts/importers/import_nightmare_log.py <csv>
    # import_symptomtrack_export.py braucht ebenfalls ein Dateiargument (JSON,
    # zweites Gerät/Familienmitglied) — direkt aufrufen:
    # python3 scripts/importers/import_symptomtrack_export.py <json> --person <id>
    # import_blue_me.py braucht ebenfalls ein Dateiargument (JSON-Export der
    # blue-ME-App) — direkt aufrufen:
    # python3 scripts/importers/import_blue_me.py <json> --person <id>
    # import_stryd.py braucht ebenfalls ein Dateiargument (Stryd-CSV-Export) —
    # direkt aufrufen:
    # python3 scripts/importers/import_stryd.py --file <csv> --person <id>
]


def run_script(script_path: Path, cmd: list[str], errors: list[str]) -> None:
    """Führt ein Importer-Skript als Subprozess aus (siehe modules/pipeline_runner.py).

    check_import_log=True: Chain-of-Custody-Check auf Lauf-Ebene (s. dortigen
    Docstring) — nur hier in import_all.py, nicht in compute_all.py, das
    denselben Runner ohne diesen Parameter nutzt.
    """
    run_pipeline_script("import_all", script_path, cmd, errors, show_command=True, check_import_log=True)


def main():
    """
    Hauptfunktion: Führt alle Importer in der definierten Reihenfolge aus.

    Command-Line-Argumente:
        --update: Nur neue Daten importieren
    """
    parser = argparse.ArgumentParser(
        description="Master-Import: ruft alle verfügbaren Importer auf")
    parser.add_argument("--update", action="store_true",
                        help="Nur neue Daten ergänzen (wird an alle Importer weitergegeben)")
    parser.add_argument("--from", dest="date_from", metavar="DATE",
                        help="Nur Daten ab diesem Datum (YYYY-MM-DD, wird weitergegeben)")
    parser.add_argument("--to", dest="date_to", metavar="DATE",
                        help="Nur Daten bis zu diesem Datum (YYYY-MM-DD, wird weitergegeben)")
    parser.add_argument("--person", default=None, metavar="PERSON_ID",
                        help="Person-ID (Standard: eigene Person aus Config) — wird nur an "
                             "Importer mit --person-Unterstuetzung weitergegeben (s. "
                             "_PERSON_AWARE), andere ignorieren das Flag stillschweigend "
                             "statt zu crashen")
    add_lang_arg(parser)
    args = parser.parse_args()
    apply_lang_from_args(args)
    lang_flag = ["--lang", args.lang] if getattr(args, "lang", None) else []
    person_flag = ["--person", args.person] if args.person else []

    common_flags = []
    if args.update:
        common_flags.append("--update")
    if args.date_from:
        common_flags.extend(["--from", args.date_from])
    if args.date_to:
        common_flags.extend(["--to", args.date_to])

    errors = []

    # ── Schritt -1: registry.json → health.db.devices abgleichen ─────────────
    # Muss vor allen Importern laufen, damit korrigierte date_from/date_to
    # o.ä. schon beim aktuellen Lauf greifen, nicht erst beim naechsten.
    _run_sync_registry_to_devices()

    # ── Schritt 0: Inbox-Dateien routen ──────────────────────────────────────
    inbox_script = SCRIPT_DIR / "process_inbox.py"
    if inbox_script.exists():
        inbox = _Cfg().data_root / "_inbox"
        has_files = inbox.exists() and any(
            f for f in inbox.iterdir()
            if f.is_file() and not f.name.startswith(".")
        ) if inbox.exists() else False
        if has_files:
            run_script(inbox_script, [sys.executable, str(inbox_script)] + lang_flag, errors)
        else:
            print(t("[import_all] _inbox/ leer — überspringe process_inbox.py",
                    "[import_all] _inbox/ empty — skipping process_inbox.py"))

    # Importer ohne --update/--from/--to Support
    _NO_COMMON_FLAGS = {
        "import_outbreak_data.py",
        "import_histamine_diary.py",
        "import_6mwt.py",
        "import_travel_environment.py",
        "import_lab_csv.py",
        "import_amelag.py",
        "import_notaufnahme.py",
        "import_garmin_gdpr.py",
    }

    # Importer mit funktionierendem --person-Flag (verifiziert, s. OpenSpec-Change
    # add-importer-person-override-convention). --person wird NUR an diese
    # weitergegeben — ein blindes Weiterreichen an alle ~40 Importer wuerde jeden
    # ohne --person-Unterstuetzung mit "unrecognized arguments" abstuerzen lassen
    # (derselbe Fehlerklasse wie der create_medicine_imaging_schema.py-Crash, der
    # beim import_fundus.py-Fix gefunden wurde). import_ecg_logger.py hat ebenfalls
    # ein funktionierendes --person-Flag, wird aber unten separat behandelt (kein
    # Teil der generischen IMPORTERS-Schleife).
    _PERSON_AWARE = {
        "import_bearable.py",
        "import_symptomtagebuch.py",
        "import_kyoro_symptoms.py",
        "import_tracks.py",
        "import_camerahRV.py",
        "import_activity_log.py",
        "import_shotsy.py",
        # add-importer-person-parameterization-remaining:
        "import_apple.py",
        "import_homeassistant.py",
        "import_polar_accesslink.py",
        "import_oura_csv.py",
        "import_beurer.py",
        "import_renpho_tape.py",
        "import_womanlog.py",
        "import_migraine.py",
        "import_sleep_cycle.py",
        "import_fddb.py",
        "import_travel_environment.py",
    }

    # Standard-Importer
    for script_name in IMPORTERS:
        script_path = SCRIPT_DIR / script_name
        if not script_path.exists():
            print(t(f"[import_all] Überspringe {script_name} (nicht gefunden)", f"[import_all] Skipping {script_name} (not found)"))
            continue
        flags = [] if script_path.name in _NO_COMMON_FLAGS else common_flags
        if script_path.name in _PERSON_AWARE:
            flags = flags + person_flag
        run_script(script_path, [sys.executable, str(script_path)] + flags + lang_flag, errors)

    # ECGLogger / Polar H10 — liest imports/ecglogger/ wenn Dateien vorhanden
    ecglogger_script = SCRIPT_DIR / "importers/import_ecg_logger.py"
    if ecglogger_script.exists():
        try:
            ecglogger_dir = Path(_Cfg().data_root) / "ecglogger"
            if ecglogger_dir.is_dir() and any(ecglogger_dir.glob("*.csv")):
                run_script(ecglogger_script,
                           [sys.executable, str(ecglogger_script), "--dir", str(ecglogger_dir)] + person_flag + lang_flag,
                           errors)
            else:
                print(t(f"[import_all] Überspringe import_ecg_logger.py ({ecglogger_dir} leer oder nicht vorhanden)",
                        f"[import_all] Skipping import_ecg_logger.py ({ecglogger_dir} empty or not found)"))
        except Exception as e:
            print(t(f"[import_all] Überspringe import_ecg_logger.py (Config-Fehler: {e})",
                    f"[import_all] Skipping import_ecg_logger.py (config error: {e})"))

    # Apple Watch EKG — Path aus Config ableiten (electrocardiograms/ neben Export.xml)
    ecg_script = SCRIPT_DIR / "importers/import_ecg_apple.py"
    if ecg_script.exists():
        try:
            cfg = _Cfg()
            ecg_dir = cfg.apple_xml.parent / "electrocardiograms"
            if ecg_dir.is_dir():
                run_script(ecg_script,
                           [sys.executable, str(ecg_script), "--dir", str(ecg_dir)] + lang_flag,
                           errors)
            else:
                print(t(f"[import_all] Überspringe import_ecg_apple.py ({ecg_dir} nicht vorhanden)",
                        f"[import_all] Skipping import_ecg_apple.py ({ecg_dir} not found)"))
        except Exception as e:
            print(t(f"[import_all] Überspringe import_ecg_apple.py (Config-Fehler: {e})",
                    f"[import_all] Skipping import_ecg_apple.py (config error: {e})"))

    if errors:
        print(t(f"\n[import_all] {len(errors)} Importer mit Fehlern: {', '.join(errors)}",
                f"\n[import_all] {len(errors)} importers with errors: {', '.join(errors)}"),
              file=sys.stderr)
    else:
        print(t("\n[import_all] Alle Importer erfolgreich abgeschlossen.",
                "\n[import_all] All importers completed successfully."))

    # ── Post-Import: PII-Bereinigung + Compliance-Check ───────────────────
    _run_post_import_sanitize(errors)

    # ── Proaktive Quell-Gesundheitspruefung (Ausbruchsdaten) ───────────────
    # Meldet nur bei Zustandsaenderung (neu kaputt/wiederhergestellt) — bei
    # unveraendertem Zustand bleibt dieser Schritt stumm. Blockiert den
    # Gesamtlauf nicht (kein Eintrag in errors), da eine kaputte
    # Drittanbieter-Quelle kein Fehler dieses Imports ist.
    try:
        newly_broken, _, _ = _run_outbreak_source_health(quiet=True)
        if newly_broken:
            print(t("\n[import_all] ACHTUNG — Ausbruchsdatenquelle(n) neu ausgefallen "
                    "(siehe scripts/utils/check_outbreak_source_health.py):",
                    "\n[import_all] WARNING — outbreak data source(s) newly broken "
                    "(see scripts/utils/check_outbreak_source_health.py):"))
            for line in newly_broken:
                print(f"    - {line}")
    except Exception as e:
        print(t(f"[import_all] Quell-Gesundheitspruefung uebersprungen (Fehler: {e})",
                f"[import_all] Source health check skipped (error: {e})"))

    if errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
