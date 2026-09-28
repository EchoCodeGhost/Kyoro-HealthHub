#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
import_saliva_ph.py — Speichel-pH-Messungen importieren

@tier        infrastructure
@purpose.de  Importiert Speichel-pH-Heimmonitoring-Daten aus CSV-Templates in die medicine.db.
             Referenzbereiche werden kontextabhängig aus ~/.config/kyoro/saliva_ph_ranges.json geladen —
             individuelle Schwellen (z. B. MCAS-spezifisch) dort anpassen, nicht im Skript.
@purpose.en  Imports saliva pH home-monitoring data from CSV templates into medicine.db.
             Reference ranges are loaded context-dependently from ~/.config/kyoro/saliva_ph_ranges.json —
             adjust individual thresholds (e.g. MCAS-specific) there, not in the script.
@method.de   Liest CSV (Template: templates/saliva_ph_template.csv) und schreibt jeden Messwert
             als eigene Zeile in lab_manual (parameter="Speichel-pH").
             Der Kontext (fasting_morning, post_meal_1h …) wird in kommentar gespeichert,
             ref_min/ref_max kommen aus der JSON-Konfiguration.
@method.en   Reads CSV (template: templates/saliva_ph_template.csv) and writes each measurement
             as a row in lab_manual (parameter="Speichel-pH").
             Context (fasting_morning, post_meal_1h …) is stored in kommentar,
             ref_min/ref_max come from the JSON configuration.
@reads       CSV-Datei (Template-Format), ~/.config/kyoro/saliva_ph_ranges.json
@writes      lab_manual, import_log
@limits.de   pH-Streifen haben typisch ±0,5 Genauigkeit; Wert als gemessen gespeichert.
             Unbekannte Kontext-Schlüssel werden als "unbekannt" importiert (keine Referenzwerte).

@relevance.de  Ermöglicht den Import von Gesundheitsdaten, essentiell für die umfassende Datenanalyse
@relevance.en  Enables import of health data, essential for comprehensive data analysis
@limits.en   pH strips are typically ±0.5 accurate; value stored as measured.
             Unknown context keys are imported as "unknown" (no reference values).
@usage
    python3 scripts/importers/import_saliva_ph.py datei.csv
    python3 scripts/importers/import_saliva_ph.py templates/saliva_ph_template.csv --dry-run

    # Direkteingabe (ohne CSV):
    python3 scripts/importers/import_saliva_ph.py --ph 6.5 --context post_meal_1h
    python3 scripts/importers/import_saliva_ph.py --ph 7.0 --context fasting_morning --time 07:30
    python3 scripts/importers/import_saliva_ph.py --ph 5.5 --context suspected_flare --symptome "Flushing,Tachykardie" --dry-run
    python3 scripts/importers/import_saliva_ph.py --ph 6.0 --context post_meal_1h --date 2026-07-08 --methode pH-Meter
"""

import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from health_config import Config, KYORO_CONFIG_DIR
from modules.base import log_import, resolve_person
from modules.db import open_medicine_db
from modules.i18n import t, add_lang_arg, apply_lang_from_args

_cfg = Config()

_RANGES_PATH = KYORO_CONFIG_DIR / "saliva_ph_ranges.json"


def _load_ranges() -> dict:
    if not _RANGES_PATH.exists():
        print(t(
            f"Warnung: {_RANGES_PATH} nicht gefunden — keine kontextspezifischen Referenzwerte.",
            f"Warning: {_RANGES_PATH} not found — no context-specific reference values."
        ), file=sys.stderr)
        return {}
    with open(_RANGES_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def _context_refs(ranges: dict, context: str) -> tuple[float | None, float | None, str, str]:
    """Gibt (ref_min, ref_max, label_de, label_en) für einen Kontext zurück."""
    ctx = ranges.get("contexts", {}).get(context, {})
    ref_min   = ctx.get("ph_min")
    ref_max   = ctx.get("ph_max")
    label_de  = ctx.get("label_de", context)
    label_en  = ctx.get("label_en", context)
    return ref_min, ref_max, label_de, label_en


def _status(ph: float, ref_min: float | None, ref_max: float | None) -> str:
    if ref_max is not None and ph > ref_max:
        return "high"
    if ref_min is not None and ph < ref_min:
        return "low"
    return "normal"


def _parse_ph(raw: str, label: str) -> float | None:
    try:
        ph = float(raw.replace(",", "."))
    except ValueError:
        print(t(f"  Übersprungen: {label} — pH '{raw}' nicht numerisch",
                f"  Skipped: {label} — pH '{raw}' not numeric"), file=sys.stderr)
        return None
    if not (0.0 <= ph <= 14.0):
        print(t(f"  Übersprungen: {label} — pH {ph} außerhalb 0–14",
                f"  Skipped: {label} — pH {ph} outside 0–14"), file=sys.stderr)
        return None
    return ph


def _build_note(label_de: str, label_en: str, methode: str,
                symptome: str, kommentar: str, lang: str) -> str:
    note_parts = [f"Kontext: {label_de if lang == 'de' else label_en}"]
    if methode:
        note_parts.append(f"Methode: {methode}")
    if symptome:
        note_parts.append(f"Symptome: {symptome}")
    if kommentar:
        note_parts.append(kommentar)
    return " | ".join(note_parts)


def _print_dry(datum: str, ph_num: float, context: str,
               ref_min: float | None, ref_max: float | None, status: str) -> None:
    flag = f" [{status}]" if status and status != "normal" else ""
    if ref_min is not None and ref_max is not None:
        ref_str = f"  (Ref: {ref_min}–{ref_max})"
    elif ref_min is not None:
        ref_str = f"  (Ref: ≥{ref_min})"
    elif ref_max is not None:
        ref_str = f"  (Ref: ≤{ref_max})"
    else:
        ref_str = ""
    print(f"  [DRY] {datum}  Speichel-pH: {ph_num:.2f}{flag}  [{context}]{ref_str}")


def _db_insert(conn, datum: str, ph_raw: str, ph_num: float,
               ref_min: float | None, ref_max: float | None,
               status: str, note: str, person: str) -> None:
    conn.execute("""
        INSERT OR IGNORE INTO lab_manual
          (date, parameter, kategorie, wert, wert_num, einheit,
           ref_min, ref_max, labor, status, kommentar, person, source)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (datum, "Speichel-pH", "Speichel", ph_raw, ph_num, "",
          ref_min, ref_max, "Selbsttest", status, note, person, "import_saliva_ph"))


def import_file(path: Path, dry_run: bool, lang: str, person: str | None = None) -> int:
    person   = resolve_person(person)
    ranges   = _load_ranges()
    conn     = open_medicine_db()
    inserted = 0

    with open(path, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            datum = row.get("Datum", "").strip()
            if not datum or datum.startswith("#"):
                continue

            uhrzeit   = row.get("Uhrzeit",     "").strip()
            context   = row.get("Kontext",      "unbekannt").strip() or "unbekannt"
            ph_raw    = row.get("pH",           "").strip()
            methode   = row.get("Messmethode",  "").strip()
            symptome  = row.get("Symptome",     "").strip()
            kommentar = row.get("Kommentar",    "").strip()

            if not ph_raw or ph_raw.startswith("#"):
                continue

            ph_num = _parse_ph(ph_raw, datum)
            if ph_num is None:
                continue

            ref_min, ref_max, label_de, label_en = _context_refs(ranges, context)
            status = _status(ph_num, ref_min, ref_max)
            note   = _build_note(label_de, label_en, methode, symptome, kommentar, lang)

            if dry_run:
                _print_dry(datum, ph_num, context, ref_min, ref_max, status)
            else:
                _db_insert(conn, datum, ph_raw, ph_num, ref_min, ref_max, status, note, person)
            inserted += 1

    if not dry_run:
        log_import(conn, "import_saliva_ph", str(path), inserted, person=person)
        conn.commit()
    conn.close()
    return inserted


def import_inline(ph_raw: str, context: str, datum: str, uhrzeit: str,
                  methode: str, symptome: str, kommentar: str,
                  dry_run: bool, lang: str, person: str | None = None) -> int:
    ph_num = _parse_ph(ph_raw, datum)
    if ph_num is None:
        return 0

    ranges = _load_ranges()
    ref_min, ref_max, label_de, label_en = _context_refs(ranges, context)
    status = _status(ph_num, ref_min, ref_max)
    note   = _build_note(label_de, label_en, methode, symptome, kommentar, lang)

    if dry_run:
        _print_dry(datum, ph_num, context, ref_min, ref_max, status)
        return 1

    person = resolve_person(person)
    conn = open_medicine_db()
    _db_insert(conn, datum, ph_raw, ph_num, ref_min, ref_max, status, note, person)
    log_import(conn, "import_saliva_ph", f"inline:{datum}", 1, person=person)
    conn.commit()
    conn.close()
    return 1


def main() -> None:
    ap = argparse.ArgumentParser(
        description=t("Speichel-pH-Messungen → medicine.db",
                      "Saliva pH measurements → medicine.db"),
        epilog=t(
            "Direkteingabe (ohne CSV): --ph und --context angeben.\n"
            "  --date / --time erlauben Nachtragen vergangener Messungen.\n"
            "  Beispiel: --ph 6.5 --context post_meal_1h --date 2026-07-08 --time 14:30",
            "Inline entry (without CSV): provide --ph and --context.\n"
            "  --date / --time allow retroactive entry of past measurements.\n"
            "  Example: --ph 6.5 --context post_meal_1h --date 2026-07-08 --time 14:30",
        ),
    )

    # CSV-Modus
    ap.add_argument("file", nargs="?", default=None,
                    help=t("CSV-Datei (Template-Format); weglassen für Direkteingabe",
                           "CSV file (template format); omit for inline entry"))

    # Direkteingabe
    ap.add_argument("--ph", metavar="WERT",
                    help=t("pH-Wert (z. B. 6.5 oder 7.0)", "pH value (e.g. 6.5 or 7.0)"))
    ap.add_argument("--context", metavar="SCHLÜSSEL", default="fasting_morning",
                    help=t("Kontext-Schlüssel aus saliva_ph_ranges.json "
                           "(Standard: fasting_morning)",
                           "Context key from saliva_ph_ranges.json "
                           "(default: fasting_morning)"))
    ap.add_argument("--date", metavar="YYYY-MM-DD", default=None,
                    help=t("Datum der Messung (Standard: heute) — für Nachtragen",
                           "Date of measurement (default: today) — for retroactive entry"))
    ap.add_argument("--time", metavar="HH:MM", default=None,
                    help=t("Uhrzeit der Messung (Standard: leer)",
                           "Time of measurement (default: empty)"))
    ap.add_argument("--methode", metavar="NAME", default="",
                    help=t("Messmethode (z. B. Streifen_4.5-9.0, pH-Meter)",
                           "Measurement method (e.g. Streifen_4.5-9.0, pH-Meter)"))
    ap.add_argument("--symptome", metavar="TEXT", default="",
                    help=t("Begleit-Symptome als Freitext (z. B. 'Flushing,Tachykardie')",
                           "Accompanying symptoms as free text (e.g. 'flushing,tachycardia')"))
    ap.add_argument("--kommentar", metavar="TEXT", default="",
                    help=t("Freitext-Kommentar", "Free-text comment"))

    ap.add_argument("--dry-run", action="store_true",
                    help=t("Zeigt was importiert würde, schreibt nichts",
                           "Show what would be imported, write nothing"))
    ap.add_argument("--person", default=None, help="Ziel-Person (Default: OWN_PERSON_ID)")
    add_lang_arg(ap)
    args = ap.parse_args()
    apply_lang_from_args(args)
    lang = getattr(args, "lang", "de")
    person = resolve_person(args.person)

    # ── Modus entscheiden ─────────────────────────────────────────────────────
    if args.file:
        path = Path(args.file)
        if not path.exists():
            print(t(f"Datei nicht gefunden: {path}", f"File not found: {path}"), file=sys.stderr)
            sys.exit(1)
        n = import_file(path, dry_run=args.dry_run, lang=lang, person=person)
    elif args.ph:
        from datetime import date as _date
        datum = args.date or _date.today().isoformat()
        # Datum validieren
        try:
            _date.fromisoformat(datum)
        except ValueError:
            print(t(f"Ungültiges Datum: {datum}  (Format: YYYY-MM-DD)",
                    f"Invalid date: {datum}  (format: YYYY-MM-DD)"), file=sys.stderr)
            sys.exit(1)
        n = import_inline(
            ph_raw=args.ph,
            context=args.context,
            datum=datum,
            uhrzeit=args.time or "",
            methode=args.methode,
            symptome=args.symptome,
            kommentar=args.kommentar,
            dry_run=args.dry_run,
            lang=lang,
            person=person,
        )
    else:
        ap.print_help()
        sys.exit(1)

    action = (t("würden importiert", "would be imported") if args.dry_run
              else t("importiert", "imported"))
    print(t(f"\n{n} Messung(en) {action} → medicine.db lab_manual",
            f"\n{n} measurement(s) {action} → medicine.db lab_manual"))


if __name__ == "__main__":
    main()
