#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
import_genetics_aniva.py — Aniva Health Biomarker- und Genetik-Daten importieren

@tier        infrastructure
@purpose.de  Importiert Aniva Health Daten in zwei Modi:
             1. Biomarker-CSV (Standard-Mitgliedschaft): 100+ Blutmarker → lab_manual
             2. Genetik-CSV (Genetik-Add-on): SNP-Panel → genetic_risk_markers
             Aniva ist eine Longevity-Plattform mit biologischer Altersbestimmung,
             personalisierten Empfehlungen und optionalem Genetik-Add-on.
@purpose.en  Imports Aniva Health data in two modes:
             1. Biomarker CSV (standard membership): 100+ blood markers → lab_manual
             2. Genetics CSV (genetics add-on): SNP panel → genetic_risk_markers
             Aniva is a longevity platform with biological age assessment,
             personalized recommendations, and optional genetics add-on.
@method.de   Modus 1 (--mode biomarker): Liest Aniva-Biomarker-CSV
             (Template: templates/aniva_biomarker_template.csv) → lab_manual.
             Modus 2 (--mode genetics): Liest Aniva-Genetik-CSV
             (Template: templates/genetics_manual_template.csv) → genetic_risk_markers.
             Erkennt Modus automatisch anhand der CSV-Spaltenköpfe falls --mode fehlt.
@method.en   Mode 1 (--mode biomarker): Reads Aniva biomarker CSV
             (template: templates/aniva_biomarker_template.csv) → lab_manual.
             Mode 2 (--mode genetics): Reads Aniva genetics CSV
             (template: templates/genetics_manual_template.csv) → genetic_risk_markers.
             Auto-detects mode from CSV column headers if --mode is omitted.
@reads       CSV-Datei (Aniva Dashboard-Export oder manuell ausgefüllt)
@writes      health.db:lab_manual (Biomarker), health.db:genetic_risk_markers (Genetik),
             health.db:import_log
@limits.de   Aniva stellt keinen standardisierten Maschinenexport bereit (Stand 2026).
             Daten müssen manuell aus dem Dashboard in das Template übertragen werden.
             Für biologisches Alter: Wert in Jahren in lab_manual (parameter='Biologisches Alter').

@relevance.de  Ermöglicht den Import von genetischen Daten, essentiell für die genetische Analyse
@relevance.en  Enables import of genetic data, essential for genetic analysis
@limits.en   Aniva does not provide a standardized machine export (as of 2026).
             Data must be manually transferred from the dashboard into the template.
             For biological age: value in years stored in lab_manual (parameter='Biologisches Alter').
@usage
    # Biomarker (Standard-Mitgliedschaft):
    python3 scripts/importers/import_genetics_aniva.py aniva_biomarker_2026-01.csv
    python3 scripts/importers/import_genetics_aniva.py aniva_biomarker.csv --mode biomarker --dry-run

    # Genetik-Add-on:
    python3 scripts/importers/import_genetics_aniva.py aniva_genetics.csv --mode genetics
    python3 scripts/importers/import_genetics_aniva.py aniva_genetics.csv --mode genetics --dry-run

    # Templates anzeigen:
    python3 scripts/importers/import_genetics_aniva.py --show-template biomarker
    python3 scripts/importers/import_genetics_aniva.py --show-template genetics
"""

import argparse
import csv
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from health_config import Config, OWN_PERSON_ID
from modules.db import open_db, open_medicine_db
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from modules.base import log_import, resolve_person

_cfg = Config()
_NOW = datetime.now(timezone.utc).isoformat()

_REPO_ROOT = Path(__file__).parents[2]
_TEMPLATE_BIOMARKER = _REPO_ROOT / "templates" / "aniva_biomarker_template.csv"
_TEMPLATE_GENETICS  = _REPO_ROOT / "templates" / "genetics_manual_template.csv"

# Spalten die eindeutig Biomarker-Mode anzeigen
_BIOMARKER_COLS = {"datum", "parameter", "wert", "einheit"}
# Spalten die eindeutig Genetik-Mode anzeigen
_GENETICS_COLS  = {"rsid", "gene", "genotype", "category"}


def _detect_mode(headers: list[str]) -> str:
    lower = {h.lower() for h in headers}
    if _GENETICS_COLS <= lower:
        return "genetics"
    if _BIOMARKER_COLS <= lower:
        return "biomarker"
    return "unknown"


def _parse_float(val: str) -> float | None:
    if not val or val.strip() in ("-", ""):
        return None
    try:
        return float(val.strip().replace(",", "."))
    except ValueError:
        return None


def _status(val_num: float | None, ref_min: float | None, ref_max: float | None,
            explicit: str) -> str:
    if explicit:
        return explicit.strip()
    if val_num is None:
        return ""
    if ref_max is not None and val_num > ref_max:
        return "high"
    if ref_min is not None and val_num < ref_min:
        return "low"
    return "normal"


def _import_biomarkers(conn, path: Path, dry_run: bool, person: str) -> int:
    inserted = 0
    with open(path, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            first_val = list(row.values())[0] if row else ""
            if not row or first_val.startswith("#"):
                continue

            datum    = row.get("datum", "").strip()
            param    = row.get("parameter", "").strip()
            kat      = row.get("kategorie", "Longevity").strip() or "Longevity"
            wert_raw = row.get("wert", "").strip()
            einheit  = row.get("einheit", "").strip()
            ref_min  = _parse_float(row.get("ref_min", ""))
            ref_max  = _parse_float(row.get("ref_max", ""))
            stat_raw = row.get("status", "").strip()
            kommentar = row.get("kommentar", "").strip()

            if not datum or not param or not wert_raw:
                continue

            wert_num = _parse_float(wert_raw)
            status   = _status(wert_num, ref_min, ref_max, stat_raw)

            if dry_run:
                flag = f" [{status}]" if status and status != "normal" else ""
                print(f"  [DRY] {datum}  {param:35s} {wert_raw:10s} {einheit:10s}{flag}")
            else:
                conn.execute("""
                    INSERT OR IGNORE INTO lab_manual
                      (date, parameter, kategorie, wert, wert_num, einheit,
                       ref_min, ref_max, labor, status, kommentar, person, source)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, (datum, param, kat, wert_raw, wert_num, einheit,
                      ref_min, ref_max, "Aniva Health", status,
                      kommentar or None, person, "import_genetics_aniva"))
            inserted += 1
    return inserted


def _import_genetics(conn, path: Path, dry_run: bool, person: str) -> int:
    from importers.import_genetics_manual import _insert
    inserted = 0
    with open(path, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            first_val = list(row.values())[0] if row else ""
            if not row or first_val.startswith("#"):
                continue
            if _insert(conn, person, row, "aniva_genetics", dry_run):
                inserted += 1
    return inserted


def main() -> None:
    parser = argparse.ArgumentParser(
        description=t("Aniva Health Biomarker- oder Genetik-CSV importieren",
                       "Import Aniva Health biomarker or genetics CSV")
    )
    parser.add_argument("file", nargs="?", type=Path,
                        help=t("CSV-Datei (Biomarker oder Genetik)",
                               "CSV file (biomarker or genetics)"))
    parser.add_argument("--mode", choices=["biomarker", "genetics"],
                        help=t("Import-Modus (auto-detect falls weggelassen)",
                               "Import mode (auto-detect if omitted)"))
    parser.add_argument("--show-template", choices=["biomarker", "genetics"],
                        help=t("Template-Pfad anzeigen", "Show template path"))
    parser.add_argument("--person",  default=None)
    parser.add_argument("--dry-run", action="store_true")
    add_lang_arg(parser)
    args = parser.parse_args()
    apply_lang_from_args(args)

    if args.show_template:
        tpl = _TEMPLATE_BIOMARKER if args.show_template == "biomarker" else _TEMPLATE_GENETICS
        print(str(tpl))
        sys.exit(0)

    if not args.file:
        parser.print_help()
        sys.exit(1)

    if not args.file.exists():
        print(t(f"Datei nicht gefunden: {args.file}", f"File not found: {args.file}"),
              file=sys.stderr)
        sys.exit(1)

    person = resolve_person(args.person, OWN_PERSON_ID)

    # Auto-detect mode
    mode = args.mode
    if not mode:
        with open(args.file, newline="", encoding="utf-8-sig") as fh:
            reader = csv.reader(fh)
            for row in reader:
                if row and not row[0].startswith("#"):
                    headers = row
                    break
            else:
                headers = []
        mode = _detect_mode(headers)
        if mode == "unknown":
            print(t(
                "Fehler: Modus konnte nicht erkannt werden. Bitte --mode angeben.",
                "Error: Mode could not be detected. Please specify --mode."
            ), file=sys.stderr)
            sys.exit(1)
        print(t(f"Erkannter Modus: {mode}", f"Detected mode: {mode}"))

    # Biomarker (klinische Messwerte) → medicine.db; Genetik → health.db
    conn = open_medicine_db() if mode == "biomarker" else open_db()

    if mode == "biomarker":
        inserted = _import_biomarkers(conn, args.file, args.dry_run, person)
        log_key = "import_aniva_biomarker"
    else:
        inserted = _import_genetics(conn, args.file, args.dry_run, person)
        log_key = "import_aniva_genetics"

    if not args.dry_run:
        log_import(conn, log_key, str(args.file), inserted)
        conn.commit()
    conn.close()

    label = t("Biomarker" if mode == "biomarker" else "Genetik-Marker",
              "biomarkers" if mode == "biomarker" else "genetic markers")
    print(t(f"{inserted} {label} {'(DRY) ' if args.dry_run else ''}importiert.",
            f"{inserted} {label} {'(DRY) ' if args.dry_run else ''}imported."))


if __name__ == "__main__":
    main()
