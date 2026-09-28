#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
import_urine_strip.py — Urin-Streifentest und 24h-Sammelurin importieren

@tier        infrastructure
@purpose.de  Importiert Urin-Streifentest und 24h-Sammelurin Daten aus CSV-Templates in die medicine.db
@purpose.en  Imports urine strip test and 24h collection urine data from CSV templates into medicine.db
@method.de   Liest das CSV-Template (data/templates/urine_strip_template.csv) und schreibt alle Parameter
             als einzelne Zeilen in medicine.db → lab_manual.
             Probe_Art: spot (Sofortprobe) | 24h (Sammelurin).
             Bei 24h-Sammelurin wird Volumen_ml als eigener Parameter gespeichert.
             12 Parameter werden unterstuetzt: Leukozyten, Urobilinogen, Protein, Bilirubin, Glukose,
             Ascorbinsaeure, Spez.Gewicht, Ketone, Nitrit, Kreatinin, pH, Blut.
             Referenzwerte sind fuer jeden Parameter definiert.
@method.en   Reads the CSV template (data/templates/urine_strip_template.csv) and writes all parameters
             as individual rows into medicine.db → lab_manual.
             Sample type: spot (instant sample) | 24h (collected urine).
             For 24h collected urine, volume_ml is stored as a separate parameter.
             12 parameters are supported: Leukozyten, Urobilinogen, Protein, Bilirubin, Glukose,
             Ascorbinsaeure, Spez.Gewicht, Ketone, Nitrit, Kreatinin, pH, Blut.
             Reference values are defined for each parameter.
@reads       CSV-Datei (Template-Format) mit Urin-Parametern
@writes      lab_manual, import_log
@limits.de   Abhaengig vom CSV-Template Format. Keine automatische Validierung der Werte.
             Referenzwerte basieren auf Standard-Laborwerten.

@relevance.de  Ermöglicht den Import von Gesundheitsdaten, essentiell für die umfassende Datenanalyse
@relevance.en  Enables import of health data, essential for comprehensive data analysis
@limits.en   Depends on CSV template format. No automatic validation of values.
             Reference values are based on standard laboratory values.
@usage
    python3 scripts/importers/import_urine_strip.py datei.csv
    python3 scripts/importers/import_urine_strip.py data/templates/urine_strip_template.csv --dry-run
"""

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from health_config import Config
from modules.base import log_import, resolve_person
from modules.db import open_medicine_db
from modules.i18n import t, add_lang_arg, apply_lang_from_args

_cfg = Config()

# ── Parameterdefinitionen ─────────────────────────────────────────────────────
# (csv_spalte, db_parameter, einheit_spot, einheit_24h, ref_min, ref_max, kategorie)
PARAMS: list[tuple] = [
    ("Leukozyten",     "Urin-Leukozyten",       "Leu/µl",  "Leu/µl",  None, 10.0,  "Urinstatus"),
    ("Urobilinogen",   "Urin-Urobilinogen",      "mg/dl",   "mg/dl",   0.1,  1.0,   "Urinstatus"),
    ("Protein",        "Urin-Protein",           "mg/dl",   "mg/24h",  None, 10.0,  "Urinstatus"),
    ("Bilirubin",      "Urin-Bilirubin",         "",        "",        None, None,  "Urinstatus"),
    ("Glukose",        "Urin-Glukose",           "mg/dl",   "mg/24h",  None, 0.0,   "Urinstatus"),
    ("Ascorbinsaeure", "Urin-Ascorbinsäure",     "mg/l",    "mg/l",    None, None,  "Urinstatus"),
    ("Spez_Gewicht",   "Urin-Spez.Gewicht",      "g/ml",    "",        1.003, 1.030, "Urinstatus"),
    ("Ketone",         "Urin-Ketone",            "mg/dl",   "mg/dl",   None, 0.0,   "Urinstatus"),
    ("Nitrit",         "Urin-Nitrit",            "",        "",        None, None,  "Urinstatus"),
    ("Kreatinin",      "Urin-Kreatinin",         "mg/dl",   "mg/24h",  20.0, 370.0, "Urinstatus"),
    ("pH",             "Urin-pH",                "",        "",        4.5,  8.0,   "Urinstatus"),
    ("Blut",           "Urin-Blut/Hämoglobin",  "Ery/µl",  "Ery/µl",  None, 5.0,   "Urinstatus"),
]

QUALITATIVE_NEG = {"neg", "negativ", "negative", "-", ""}
QUALITATIVE_POS = {"pos", "positiv", "positive", "+", "++", "+++", "trace", "spuren"}


def _parse_value(raw: str) -> tuple[str, float | None]:
    """Gibt (wert_text, wert_num) zurück."""
    raw = raw.strip()
    if not raw or raw.startswith("#"):
        return ("", None)
    try:
        num = float(raw.replace(",", "."))
        return (raw, num)
    except ValueError:
        return (raw, None)


def _status(wert_num: float | None, wert_text: str,
            ref_min: float | None, ref_max: float | None) -> str:
    if wert_text.lower() in QUALITATIVE_NEG and ref_max == 0.0:
        return "normal"
    if wert_text.lower() in QUALITATIVE_POS and ref_max == 0.0:
        return "high"
    if wert_num is None:
        return ""
    if ref_max is not None and wert_num > ref_max:
        return "high"
    if ref_min is not None and wert_num < ref_min:
        return "low"
    return "normal"


def import_file(path: Path, dry_run: bool, lang: str, person: str | None = None) -> int:
    person = resolve_person(person)
    conn = open_medicine_db()
    inserted = 0

    with open(path, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            # Kommentarzeilen überspringen
            datum = row.get("Datum", "").strip()
            if not datum or datum.startswith("#"):
                continue

            probe_art  = row.get("Probe_Art", "spot").strip().lower() or "spot"
            volumen    = row.get("Volumen_ml", "").strip()
            labor      = row.get("Labor", "").strip() or "Selbsttest"
            kommentar  = row.get("Kommentar", "").strip()
            is_24h     = probe_art == "24h"

            note_base = f"Probe: {probe_art}"
            if is_24h and volumen:
                note_base += f" | Volumen: {volumen} ml"
            if kommentar:
                note_base += f" | {kommentar}"

            # Volumen als eigener Parameter bei 24h
            if is_24h and volumen:
                wert_text, wert_num = _parse_value(volumen)
                if not dry_run:
                    conn.execute("""
                        INSERT OR IGNORE INTO lab_manual
                          (date, parameter, kategorie, wert, wert_num, einheit,
                           ref_min, ref_max, labor, status, kommentar, person, source)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """, (datum, "Urin-Sammelvolumen", "Urinstatus",
                          wert_text, wert_num, "ml",
                          500.0, 3000.0, labor, _status(wert_num, wert_text, 500.0, 3000.0),
                          note_base, person, "import_urine_strip"))
                else:
                    print(f"  [DRY] {datum}  Urin-Sammelvolumen: {volumen} ml")
                inserted += 1

            for csv_col, db_param, unit_spot, unit_24h, ref_min, ref_max, kat in PARAMS:
                raw = row.get(csv_col, "").strip()
                if not raw or raw.startswith("#"):
                    continue

                wert_text, wert_num = _parse_value(raw)
                if not wert_text:
                    continue

                einheit = unit_24h if is_24h else unit_spot
                status  = _status(wert_num, wert_text, ref_min, ref_max)
                note    = note_base

                # Spezifisches Gewicht ist spot-only
                if csv_col == "Spez_Gewicht" and is_24h:
                    continue

                if dry_run:
                    flag = f" [{status}]" if status and status != "normal" else ""
                    print(f"  [DRY] {datum}  {db_param}: {wert_text} {einheit}{flag}")
                    inserted += 1
                    continue

                conn.execute("""
                    INSERT OR IGNORE INTO lab_manual
                      (date, parameter, kategorie, wert, wert_num, einheit,
                       ref_min, ref_max, labor, status, kommentar, person, source)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, (datum, db_param, kat,
                      wert_text, wert_num, einheit,
                      ref_min, ref_max, labor, status,
                      note, person, "import_urine_strip"))
                inserted += 1

    if not dry_run:
        log_import(conn, "import_urine_strip", str(path), inserted, person=person)
        conn.commit()

    conn.close()
    return inserted


def main() -> None:
    ap = argparse.ArgumentParser(
        description=t("Urin-Streifentest / 24h-Sammelurin → medicine.db",
                      "Urine strip / 24h collection → medicine.db")
    )
    ap.add_argument("file", help=t("CSV-Datei (Template-Format)", "CSV file (template format)"))
    ap.add_argument("--dry-run", action="store_true",
                    help=t("Zeigt was importiert würde, schreibt nichts",
                           "Show what would be imported, write nothing"))
    ap.add_argument("--person", default=None, help="Ziel-Person (Default: OWN_PERSON_ID)")
    add_lang_arg(ap)
    args = ap.parse_args()
    apply_lang_from_args(args)
    lang = getattr(args, "lang", "de")
    person = resolve_person(args.person)

    path = Path(args.file)
    if not path.exists():
        print(t(f"Datei nicht gefunden: {path}", f"File not found: {path}"), file=sys.stderr)
        sys.exit(1)

    n = import_file(path, dry_run=args.dry_run, lang=lang, person=person)
    action = t("würden importiert", "would be imported") if args.dry_run else t("importiert", "imported")
    print(t(f"\n{n} Parameter {action} → medicine.db lab_manual",
            f"\n{n} parameters {action} → medicine.db lab_manual"))
    if not args.dry_run and n > 0:
        print(t(
            "  ℹ Erinnerung: analyse_urine.py läuft nicht automatisch mit — "
            "für einen aktuellen Trendbericht: python3 scripts/analysis/manual/analyse_urine.py --plot",
            "  ℹ Reminder: analyse_urine.py does not run automatically — "
            "for an up-to-date trend report: python3 scripts/analysis/manual/analyse_urine.py --plot"))


if __name__ == "__main__":
    main()
