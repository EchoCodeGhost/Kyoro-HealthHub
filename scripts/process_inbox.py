#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
process_inbox.py — Inbox-Prozessor für Import-Dateien

@tier        infrastructure
@purpose.de  Erkennt und routet Dateien aus imports/_inbox/ an die entsprechenden
             Importer. Ermöglicht einfaches Ablegen von Dateien ohne manuelle Zuordnung.
@purpose.en  Recognizes and routes files from imports/_inbox/ to the appropriate
             importers. Enables simple file drop without manual assignment.
@method.de   Unterstützt ZIP-Archive (Apple Health, Polar GDPR, Garmin GDPR, Oura CSV)
             und Einzeldateien (Symptom-History, WomanLog, Bearable, HRV4Training,
             Ecowitt, HealthManager Pro, RENPHO, Wellue O2Ring, ECGLogger, Omron,
             FDDB (diary_*.csv, userhistory_*.csv, kombinierter complete_*.csv-Export),
             Hilo-Blutdruckbericht, PDF-Laborergebnisse, Migraine-App, Shotsy,
             Kubios-Screenshots, Kubios-TXT, GPX). ECGLogger und Omron werden per
             Header-Sniffing erkannt (Dateinamen sind app-generisch, kein festes
             Muster). Dateien werden nach Verarbeitung nach _inbox/processed/
             verschoben.
@method.en   Supports ZIP archives (Apple Health, Polar GDPR, Garmin GDPR, Oura CSV)
             and single files (symptom history, WomanLog, Bearable, HRV4Training,
             Ecowitt, HealthManager Pro, RENPHO, Wellue O2Ring, ECGLogger, Omron,
             FDDB (diary_*.csv, userhistory_*.csv, combined complete_*.csv export),
             Hilo blood-pressure reports, PDF lab results, Migraine app, Shotsy,
             Kubios screenshots, Kubios TXT, GPX). ECGLogger and Omron are detected
             via header sniffing (filenames are app-generic, no fixed pattern).
             Files are moved to _inbox/processed/ after processing.
@reads       imports/_inbox/ Verzeichnis
@writes      Verschiedene imports/*/ Verzeichnisse, imports/_inbox/processed/
@limits.de   Erkennung basiert auf Dateinamen-Mustern. Unbekannte Formate werden stillschweigend uebersprungen.

@relevance.de  Bietet Gesundheitsdatenfunktionen, essentiell für die medizinische Datenverarbeitung
@relevance.en  Provides health data functions, essential for medical data processing
@limits.en   Detection is based on filename patterns. Unknown formats are silently skipped.
@usage
    python3 scripts/process_inbox.py              # alle Dateien in _inbox/
    python3 scripts/process_inbox.py --dry-run    # zeigt was passieren würde
    python3 scripts/process_inbox.py --import     # danach import_all.py --update
    python3 scripts/process_inbox.py --file a.zip
"""

import argparse
import fnmatch
import shutil
import subprocess
import sys
import zipfile
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from health_config import Config as _Cfg
from modules.i18n import t, add_lang_arg, apply_lang_from_args

_cfg     = _Cfg()
INBOX    = _cfg.data_root / "_inbox"
DONE_DIR = INBOX / "processed"
SCRIPT_DIR = Path(__file__).parent


# ── ZIP-Quellen-Erkennung ─────────────────────────────────────────────────────

_POLAR_PATTERNS = (
    "training*.json",
    "nightly_recovery*.json",
    "activity-*.json",
    "ppi*.json",
    "247ohr_*.json",
    "fitness*.json",
    "sleep_result_*.json",
    "sleep_score_*.json",
    "sleep_wake_*.json",
    "orthostatic-test-result-*.json",
    "generic-period*.json",
)


def _detect_zip(zf: zipfile.ZipFile) -> str | None:
    names = set(zf.namelist())

    if any("apple_health_export/Export.xml" == n for n in names):
        return "apple_health"

    if any(n == "App Data/dailysleep.csv" or n.startswith("App Data/dailysleep.csv")
           for n in names):
        return "oura"

    if any(n.startswith("DI_CONNECT/") for n in names):
        return "garmin_gdpr"

    for pat in _POLAR_PATTERNS:
        if any(fnmatch.fnmatch(Path(n).name, pat) for n in names):
            return "polar"

    return None


# ── Einzeldatei-Erkennung ─────────────────────────────────────────────────────

def _sniff_csv(path: Path) -> str | None:
    name = path.name.lower()
    if fnmatch.fnmatch(name, "symptom-history*.csv"):
        return "kyoro_st"
    if fnmatch.fnmatch(name, "symptomtagebuch*.csv"):
        return "symptomtagebuch"
    if fnmatch.fnmatch(name, "womanlog*.csv"):
        return "womanlog"
    if fnmatch.fnmatch(name, "bearable*.csv") or fnmatch.fnmatch(name, "bearable-export*.csv"):
        return "bearable"
    if fnmatch.fnmatch(name, "hrv4t*.csv") or fnmatch.fnmatch(name, "hrv4training*.csv"):
        return "hrv4training"
    if fnmatch.fnmatch(name, "ecowitt*.csv"):
        return "ecowitt"
    if fnmatch.fnmatch(name, "sleepdata*.csv"):
        return "sleep_cycle"
    if fnmatch.fnmatch(name, "healthmanager pro export*.csv"):
        return "health_manager"
    if fnmatch.fnmatch(name, "renpho*.csv"):
        return "renpho"
    if fnmatch.fnmatch(name, "o2ring*.csv"):
        return "wellue_o2ring"
    if fnmatch.fnmatch(name, "diary_*.csv") or fnmatch.fnmatch(name, "userhistory_*.csv") \
            or fnmatch.fnmatch(name, "complete_*.csv"):
        return "fddb"
    # Header-Sniffing für unbenannte Exporte
    try:
        raw = path.read_bytes()[:1000].decode("utf-8-sig", errors="replace")
        first = raw.splitlines()[0].lower() if raw else ""
        cols = {c.strip().strip('"') for c in first.split(",")}
        if "rmssd" in cols and ("hrv4t" in cols or "morning readiness" in cols):
            return "hrv4training"
        if "outdoor temperature" in cols or "ecowitt" in first:
            return "ecowitt"
        if "symptom auswählen" in raw.lower() or "symptom wählen" in raw.lower():
            return "kyoro_st"
        if "ecg" in cols and ("hr" in cols or "rr" in cols):
            return "ecg_logger"
        if "unregelmäßiger herzschlag festgestellt" in first or "mögliches afib" in first:
            return "omron"
    except Exception:
        pass
    return None


def _sniff_json(path: Path) -> str | None:
    if path.suffix.lower() == ".shotsyjson":
        return "shotsy"
    if path.name.lower().startswith("shotsy"):
        return "shotsy"
    try:
        sample = path.read_bytes()[:500].decode("utf-8-sig", errors="replace").lower()
        if '"drug"' in sample or '"injections"' in sample or '"injection_date"' in sample:
            return "shotsy"
    except Exception:
        pass
    return None


def _sniff_txt(path: Path) -> str | None:
    try:
        sample = path.read_bytes()[:400].decode("utf-8-sig", errors="replace")
        if "KubiosHRV" in sample or "Kubios HRV" in sample or "Analysis type" in sample:
            return "kubios"
    except Exception:
        pass
    return None


def _sniff_pdf(path: Path) -> str | None:
    """Detect Medical Motion / Hilo PDFs by filename pattern."""
    name = path.name.lower()
    if name.startswith("hilo"):
        return "hilo"
    if name.startswith("mm_") or "medical" in name or "motion" in name:
        return "medical_motion"

    try:
        # Try to read first few bytes to detect Medical Motion content
        sample = path.read_bytes()[:1000].decode("utf-8-sig", errors="replace")
        if "Medical Motion" in sample or "Physiotherapie" in sample or "Schmerzbereiche" in sample:
            return "medical_motion"
    except Exception:
        pass
    return None


# ── ZIP-Handler ───────────────────────────────────────────────────────────────

def _handle_apple_health(zf: zipfile.ZipFile, dry: bool) -> list[str]:
    extract_root = _cfg.data_root
    xml_in_zip   = _cfg.data_root / "apple_health_export" / "Export.xml"
    xml_target   = _cfg.apple_xml

    n = sum(1 for n in zf.namelist() if not n.endswith("/"))
    msgs = [f"  → {extract_root / 'apple_health_export'}/ ({n} Dateien)"]

    if not dry:
        extract_root.mkdir(parents=True, exist_ok=True)
        zf.extractall(extract_root)
        if xml_target != xml_in_zip and xml_in_zip.exists():
            xml_target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(xml_in_zip, xml_target)
            msgs.append(f"  Export.xml → {xml_target} (cfg-Override)")

    return msgs


def _handle_polar(zf: zipfile.ZipFile, dry: bool) -> list[str]:
    target = _cfg.polar_dir
    msgs   = []
    for name in zf.namelist():
        if name.endswith("/"):
            continue
        fname = Path(name).name
        if not any(fnmatch.fnmatch(fname, p) for p in _POLAR_PATTERNS):
            continue
        dst = target / fname
        msgs.append(f"  {name} → {dst}")
        if not dry:
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(zf.read(name))
    return msgs


def _handle_garmin_gdpr(zf: zipfile.ZipFile, dry: bool) -> list[str]:
    gdpr_root = _cfg.data_root / "garmin_gdpr"
    msgs = [f"  → {gdpr_root}/ (entpacken)"]
    if not dry:
        gdpr_root.mkdir(parents=True, exist_ok=True)
        zf.extractall(gdpr_root)
        script = SCRIPT_DIR / "importers" / "import_garmin_gdpr.py"
        if script.exists():
            msgs.append(f"  → import_garmin_gdpr.py --dir {gdpr_root}")
            subprocess.run(
                [sys.executable, str(script), "--dir", str(gdpr_root)],
                check=False,
            )
        else:
            msgs.append(t(
                f"  Warnung: {script} nicht gefunden — manuell ausführen.",
                f"  Warning: {script} not found — run manually.",
            ))
    return msgs


def _handle_oura_zip(zf: zipfile.ZipFile, zip_path: Path, dry: bool) -> list[str]:
    oura_dir = _cfg.data_root / "oura"
    dst_name = f"data-{date.today()}.zip"
    dst      = oura_dir / dst_name
    msgs     = [f"  → {dst}"]
    if not dry:
        oura_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(zip_path, dst)
    return msgs


# ── Einzeldatei-Handler ───────────────────────────────────────────────────────

def _run(script_rel: str, extra_args: list[str], dry: bool) -> list[str]:
    script = SCRIPT_DIR / script_rel
    if dry:
        return [f"  würde aufrufen: {script.name} {' '.join(extra_args)}"]
    if not script.exists():
        return [t(f"  Warnung: {script} nicht gefunden — übersprungen.",
                  f"  Warning: {script} not found — skipped.")]
    subprocess.run([sys.executable, str(script)] + extra_args, check=False)
    return [f"  → {script.name} {' '.join(extra_args)}"]


def _copy_to(src: Path, dest_dir: Path, dry: bool) -> list[str]:
    dest = dest_dir / src.name
    if not dry:
        dest_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
    return [f"  → {dest}"]


def _handle_kyoro_st(src: Path, dry: bool) -> list[str]:
    dest_dir = Path(_cfg._cfg.get("paths", {}).get(
        "kyoro_st_dir", str(_cfg.data_root / "kyoro-ST")
    ))
    msgs = _copy_to(src, dest_dir, dry)
    dest = dest_dir / src.name
    msgs += _run("importers/import_kyoro_symptoms.py", ["--file", str(dest)], dry)
    return msgs


def _handle_symptomtagebuch(src: Path, dry: bool) -> list[str]:
    dest_dir = _cfg.data_root / "symptomtagebuch"
    msgs = _copy_to(src, dest_dir, dry)
    dest = dest_dir / src.name
    msgs += _run("importers/import_symptomtagebuch.py", ["--file", str(dest)], dry)
    return msgs


def _handle_womanlog(src: Path, dry: bool) -> list[str]:
    return _copy_to(src, _cfg.data_root / "WomanLogApp", dry)


def _handle_bearable(src: Path, dry: bool) -> list[str]:
    return _copy_to(src, _cfg.data_root / "bearable", dry)


def _handle_hrv4training(src: Path, dry: bool) -> list[str]:
    return _run("importers/import_hrv4training.py", ["--file", str(src)], dry)


def _handle_ecowitt(src: Path, dry: bool) -> list[str]:
    return _run("importers/import_ecowitt_csv.py", [str(src)], dry)


def _handle_sleep_cycle(src: Path, dry: bool) -> list[str]:
    dest_dir = _cfg.data_root / "sleep_cycle"
    msgs = _copy_to(src, dest_dir, dry)
    msgs += _run("importers/import_sleep_cycle.py", [], dry)
    return msgs


def _handle_health_manager(src: Path, dry: bool) -> list[str]:
    dest_dir = _cfg.data_root / "beurer"
    msgs = _copy_to(src, dest_dir, dry)
    msgs += _run("importers/import_beurer.py", ["--file", str(dest_dir / src.name)], dry)
    return msgs


def _handle_fddb(src: Path, dry: bool) -> list[str]:
    # import_fddb.py hat keinen --file-Parameter, es globbt sein Zielverzeichnis
    # selbst (diary_*.csv / userhistory_*.csv) — Kopieren reicht, kein --file-Aufruf.
    dest_dir = _cfg.data_root / "fddb"
    msgs = _copy_to(src, dest_dir, dry)
    msgs += _run("importers/import_fddb.py", [], dry)
    return msgs


def _handle_pdf(src: Path, dry: bool) -> list[str]:
    return _run("importers/import_lab_results.py", [str(src)], dry)


def _handle_hilo(src: Path, dry: bool) -> list[str]:
    dest_dir = _cfg.data_root / "hilo"
    msgs = _copy_to(src, dest_dir, dry)
    msgs += _run("importers/import_hilo_pdf.py", ["--file", str(dest_dir / src.name)], dry)
    return msgs


def _handle_renpho(src: Path, dry: bool) -> list[str]:
    dest_dir = _cfg.data_root / "renpho"
    msgs = _copy_to(src, dest_dir, dry)
    msgs += _run("importers/import_renpho_tape.py", ["--file", str(dest_dir / src.name)], dry)
    return msgs


def _handle_wellue_o2ring(src: Path, dry: bool) -> list[str]:
    return _run("importers/import_wellue_o2ring.py", ["--file", str(src)], dry)


def _handle_ecg_logger(src: Path, dry: bool) -> list[str]:
    return _run("importers/import_ecg_logger.py", ["--file", str(src)], dry)


def _handle_omron(src: Path, dry: bool) -> list[str]:
    return _run("importers/import_omron.py", ["--file", str(src)], dry)


def _handle_mbu(src: Path, dry: bool) -> list[str]:
    return _copy_to(src, _cfg.migraine_dir, dry)


def _handle_shotsy(src: Path, dry: bool) -> list[str]:
    return _copy_to(src, _cfg.data_root / "shotsy", dry)


def _handle_png(src: Path, dry: bool) -> list[str]:
    return _run("importers/import_kubios_screenshot.py", ["--file", str(src)], dry)


def _handle_medical_motion(src: Path, dry: bool) -> list[str]:
    return _run("importers/import_medical_motion.py", ["--file", str(src)], dry)


def _handle_kubios_txt(src: Path, dry: bool) -> list[str]:
    return _run("importers/import_kubios_orthostatic.py", ["--file", str(src)], dry)


def _handle_gpx(src: Path, dry: bool) -> list[str]:
    return _copy_to(src, _cfg.data_root / "garmin_gpsmap", dry)


# ── Dispatcher ────────────────────────────────────────────────────────────────

def _move_to_done(path: Path) -> None:
    DONE_DIR.mkdir(parents=True, exist_ok=True)
    dst = DONE_DIR / path.name
    if dst.exists():
        dst = DONE_DIR / f"{path.stem}-{date.today()}{path.suffix}"
    shutil.move(str(path), dst)
    print(t(f"  → verschoben nach {dst.relative_to(INBOX.parent.parent)}",
            f"  → moved to {dst.relative_to(INBOX.parent.parent)}"))


def process_zip(zip_path: Path, dry: bool) -> bool:
    try:
        zf = zipfile.ZipFile(zip_path)
    except zipfile.BadZipFile:
        print(t(f"  Kein gültiges ZIP: {zip_path.name}",
                f"  Not a valid ZIP: {zip_path.name}"))
        return False

    source = _detect_zip(zf)
    if source is None:
        print(t(f"  Unbekannte ZIP-Quelle: {zip_path.name} — übersprungen",
                f"  Unknown ZIP source: {zip_path.name} — skipped"))
        return False

    label = {
        "apple_health": "Apple Health",
        "polar":        "Polar GDPR",
        "garmin_gdpr":  "Garmin GDPR",
        "oura":         "Oura CSV",
    }[source]

    print(t(f"  [ZIP/{label}] {zip_path.name}", f"  [ZIP/{label}] {zip_path.name}"))

    if source == "apple_health":
        msgs = _handle_apple_health(zf, dry)
    elif source == "polar":
        msgs = _handle_polar(zf, dry)
    elif source == "garmin_gdpr":
        msgs = _handle_garmin_gdpr(zf, dry)
    else:
        msgs = _handle_oura_zip(zf, zip_path, dry)

    for m in msgs:
        print(m)

    if not dry:
        _move_to_done(zip_path)

    return True


def process_file(path: Path, dry: bool) -> bool:
    """Handle non-ZIP files. Returns True if recognized and processed."""
    suf  = path.suffix.lower()
    name = path.name

    if suf == ".csv":
        source = _sniff_csv(path)
        if source == "kyoro_st":
            label, handler = "Kyoro SymptomTrack", _handle_kyoro_st
        elif source == "symptomtagebuch":
            label, handler = "Symptomtagebuch", _handle_symptomtagebuch
        elif source == "womanlog":
            label, handler = "WomanLog", _handle_womanlog
        elif source == "bearable":
            label, handler = "Bearable", _handle_bearable
        elif source == "hrv4training":
            label, handler = "HRV4Training", _handle_hrv4training
        elif source == "ecowitt":
            label, handler = "Ecowitt", _handle_ecowitt
        elif source == "sleep_cycle":
            label, handler = "Sleep Cycle", _handle_sleep_cycle
        elif source == "health_manager":
            label, handler = "HealthManager Pro", _handle_health_manager
        elif source == "renpho":
            label, handler = "RENPHO", _handle_renpho
        elif source == "wellue_o2ring":
            label, handler = "Wellue O2Ring", _handle_wellue_o2ring
        elif source == "fddb":
            label, handler = "fddb Ernährungstagebuch", _handle_fddb
        elif source == "ecg_logger":
            label, handler = "ECGLogger", _handle_ecg_logger
        elif source == "omron":
            label, handler = "Omron", _handle_omron
        else:
            print(t(f"  Unbekannte CSV-Quelle: {name} — übersprungen",
                    f"  Unknown CSV source: {name} — skipped"))
            return False

    elif suf == ".pdf":
        pdf_type = _sniff_pdf(path)
        if pdf_type == "medical_motion":
            label, handler = "Medical Motion PDF", _handle_medical_motion
        elif pdf_type == "hilo":
            label, handler = "Hilo Blutdruckbericht", _handle_hilo
        else:
            label, handler = "Laborbefund PDF", _handle_pdf

    elif suf == ".mbu":
        label, handler = "Migraine .mbu", _handle_mbu

    elif suf in (".json", ".shotsyjson"):
        source = _sniff_json(path)
        if source == "shotsy":
            label, handler = "Shotsy", _handle_shotsy
        else:
            print(t(f"  Unbekannte JSON-Quelle: {name} — übersprungen",
                    f"  Unknown JSON source: {name} — skipped"))
            return False

    elif suf == ".png":
        label, handler = "Kubios Screenshot", _handle_png

    elif suf == ".txt":
        source = _sniff_txt(path)
        if source == "kubios":
            label, handler = "Kubios TXT", _handle_kubios_txt
        else:
            print(t(f"  Unbekannte TXT-Quelle: {name} — übersprungen",
                    f"  Unknown TXT source: {name} — skipped"))
            return False

    elif suf == ".gpx":
        label, handler = "GPX", _handle_gpx

    else:
        print(t(f"  Unbekannter Dateityp: {name} — übersprungen",
                f"  Unknown file type: {name} — skipped"))
        return False

    print(t(f"  [{label}] {name}", f"  [{label}] {name}"))
    msgs = handler(path, dry)
    for m in msgs:
        print(m)

    if not dry:
        _move_to_done(path)

    return True


# ── Hauptprogramm ─────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description=t("Inbox-Dateien erkennen und routen",
                      "Detect and route inbox files")
    )
    parser.add_argument("--dry-run", action="store_true",
                        help=t("Nur anzeigen, nichts tun",
                               "Show what would happen, do nothing"))
    parser.add_argument("--import",  dest="run_import", action="store_true",
                        help=t("Nach Verarbeitung import_all.py --update aufrufen",
                               "Run import_all.py --update after processing"))
    parser.add_argument("--file", metavar="PATH",
                        help=t("Nur diese Datei verarbeiten",
                               "Process only this file"))
    add_lang_arg(parser)

    args = parser.parse_args()
    apply_lang_from_args(args)

    if not INBOX.exists():
        print(t(f"Inbox-Verzeichnis nicht gefunden: {INBOX}",
                f"Inbox directory not found: {INBOX}"))
        sys.exit(1)

    if args.file:
        files = [Path(args.file).expanduser()]
    else:
        files = sorted(
            f for f in INBOX.iterdir()
            if f.is_file() and not f.name.startswith(".")
        )

    if not files:
        print(t("Keine Dateien in _inbox/ gefunden.", "No files found in _inbox/."))
        return

    dry = args.dry_run
    if dry:
        print(t("── Dry-run (keine Änderungen) ──────────────────────",
                "── Dry-run (no changes) ────────────────────────────"))

    n_ok = n_total = 0
    for fp in files:
        n_total += 1
        print()
        if fp.suffix.lower() == ".zip":
            if process_zip(fp, dry):
                n_ok += 1
        else:
            if process_file(fp, dry):
                n_ok += 1

    print(t(f"\n{n_ok}/{n_total} Datei(en) erkannt und verarbeitet.",
            f"\n{n_ok}/{n_total} file(s) detected and processed."))

    if args.run_import and n_ok and not dry:
        print(t("\n── Starte import_all.py --update ───────────────────",
                "\n── Running import_all.py --update ──────────────────"))
        import_all = SCRIPT_DIR / "import_all.py"
        subprocess.run([sys.executable, str(import_all), "--update"], check=False)


if __name__ == "__main__":
    main()
