#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
RENPHO Smart-Maßband → health.db (body_composition)

@tier        infrastructure
@purpose.de  Importiert CSV-Exporte der RENPHO-App (smartes Maßband) in die
             health.db. Speichert alle Körperumfänge (Hals, Schulter, Arm,
             Brust, Taille, Abdomen, Hüfte, Oberschenkel, Wade, Benutzerdefiniert)
             sowie den Taille-Hüfte-Quotienten in body_composition.
@purpose.en  Imports CSV exports from the RENPHO app (smart tape measure) into
             health.db. Stores all body circumferences (neck, shoulder, arm,
             chest, waist, abdomen, hip, thigh, calf, custom) and the waist-to-
             hip ratio in body_composition.
@method.de   Liest CSV-Dateien aus imports/_inbox/ (RENPHO*.csv) oder einem
             expliziten Pfad. Jede Zeile enthält einen Datumsstempel (deutsches
             Format) und Key(unit):value-Paare. Fehlende Werte ('--') werden als
             NULL gespeichert. Neue Umfangs-Spalten werden automatisch zu
             body_composition ergänzt, falls noch nicht vorhanden.
@method.en   Reads CSV files from imports/_inbox/ (RENPHO*.csv) or an explicit
             path. Each row contains a date stamp (German format) and
             Key(unit):value pairs. Missing values ('--') are stored as NULL.
             New circumference columns are added to body_composition
             automatically if not yet present.
@reads       imports/_inbox/RENPHO*.csv
@writes      health.db: body_composition (neck_cm, shoulder_cm, upper_arm_left_cm,
             upper_arm_right_cm, chest_cm, abdomen_cm, thigh_left_cm,
             thigh_right_cm, calf_left_cm, calf_right_cm, custom_1..6,
             waist_to_hip_ratio, waist_cm, hip_cm)
@limits.de   RENPHO-App gibt "Benutzerdefinierter Teil 1" mit Einheit "inch"
             aus (App-Bug); der Wert wird unverändert gespeichert.
             Keine Validierung der Plausibilität einzelner Messwerte.

@relevance.de  Ermöglicht den Import von Gesundheitsdaten, essentiell für die umfassende Datenanalyse
@relevance.en  Enables import of health data, essential for comprehensive data analysis
@limits.en   RENPHO app exports "Custom Part 1" with unit "inch" (app bug);
             the value is stored as-is. No plausibility validation.
@usage
    python3 import_renpho_tape.py
    python3 import_renpho_tape.py --inbox
    python3 import_renpho_tape.py --file "RENPHO Health-Max.csv"
    python3 import_renpho_tape.py --update
"""

import argparse
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
import sys as _sys
from zoneinfo import ZoneInfo

_sys.path.insert(0, str(Path(__file__).parent.parent))
from health_config import Config as _Cfg
from modules.db import open_db
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from modules.base import log_import, resolve_person

_cfg = _Cfg()

INBOX_DIR = _cfg.data_root / "_inbox"
RENPHO_DIR = _cfg.data_root / "renpho"
RENPHO_DIR.mkdir(parents=True, exist_ok=True)

TZ = ZoneInfo(_cfg.home_timezone)

DE_MONTHS = {
    "januar": 1, "februar": 2, "märz": 3, "april": 4,
    "mai": 5, "juni": 6, "juli": 7, "august": 8,
    "september": 9, "oktober": 10, "november": 11, "dezember": 12,
}

# German key → (column_name, type)
_FIELD_MAP = {
    "Hals":                    ("neck_cm",             "REAL"),
    "Schulter":                ("shoulder_cm",          "REAL"),
    "L-Oberarm":               ("upper_arm_left_cm",    "REAL"),
    "R-Oberarm":               ("upper_arm_right_cm",   "REAL"),
    "Brust":                   ("chest_cm",             "REAL"),
    "Taille":                  ("waist_cm",             "REAL"),
    "Abdomen":                 ("abdomen_cm",           "REAL"),
    "Hüfte":                   ("hip_cm",               "REAL"),
    "L-Oberschenkel":          ("thigh_left_cm",        "REAL"),
    "R-Oberschenkel":          ("thigh_right_cm",       "REAL"),
    "L-Wade":                  ("calf_left_cm",         "REAL"),
    "R-Wade":                  ("calf_right_cm",        "REAL"),
    # ── Benutzerdefinierte Felder ──────────────────────────────────────────
    # custom_1: App-Bug — RENPHO exportiert dieses Feld fälschlich mit
    #           Einheit "inch" obwohl der Wert in cm gespeichert ist.
    #           Nicht für eigene Messungen verwenden.
    # custom_2: L-Knöchel (cm) — Umfang auf Malleolenhöhe (Knöchelknochen
    #           links und rechts tastbar), schmalste Stelle zwischen Wade
    #           und Fuß. Im Stehen messen, morgens nüchtern.
    #           Wird für Lipödem-Screening (Wade-Knöchel-Index) verwendet.
    # custom_3: R-Knöchel (cm) — wie custom_2, rechte Seite.
    # custom_4–6: frei für weitere Messungen.
    "Benutzerdefinierter Teil 1": ("custom_1",          "REAL"),
    "Benutzerdefinierter Teil 2": ("custom_2",          "REAL"),
    "Benutzerdefinierter Teil 3": ("custom_3",          "REAL"),
    "Benutzerdefinierter Teil 4": ("custom_4",          "REAL"),
    "Benutzerdefinierter Teil 5": ("custom_5",          "REAL"),
    "Benutzerdefinierter Teil 6": ("custom_6",          "REAL"),
    "Bauch zu Hüfte Umfang":   ("waist_to_hip_ratio",  "REAL"),
}

# Columns that already exist in body_composition (no ALTER needed)
_EXISTING_COLS = {"waist_cm", "hip_cm"}

# New columns to add if missing
_NEW_COLS = {col: typ for key, (col, typ) in _FIELD_MAP.items() if col not in _EXISTING_COLS}


def _ensure_columns(conn) -> None:
    existing = {row[1] for row in conn.execute("PRAGMA table_info(body_composition)")}
    for col, typ in _NEW_COLS.items():
        if col not in existing:
            try:
                conn.execute(f"ALTER TABLE body_composition ADD COLUMN {col} {typ}")
                conn.commit()
            except Exception:
                pass


def _parse_ts(date_str: str) -> tuple[str, str] | None:
    """
    Parst 'DD. Monat YYYY  HH:MM:SS' → (UTC-ISO-Timestamp, lokales Datum).
    Gibt None zurück bei Parsefehler.
    """
    m = re.match(
        r"(\d{1,2})\.\s+(\w+)\s+(\d{4})\s+(\d{2}):(\d{2}):(\d{2})",
        date_str.strip(),
    )
    if not m:
        return None
    day, month_str, year, hh, mm, ss = m.groups()
    month = DE_MONTHS.get(month_str.lower())
    if not month:
        return None
    try:
        local_dt = datetime(int(year), month, int(day), int(hh), int(mm), int(ss), tzinfo=TZ)
    except ValueError:
        return None
    utc_dt = local_dt.astimezone(timezone.utc)
    ts = utc_dt.strftime("%Y-%m-%dT%H:%M:%S")
    date = local_dt.strftime("%Y-%m-%d")
    return ts, date


def _parse_value(raw: str) -> float | None:
    raw = raw.strip()
    if not raw or raw == "--":
        return None
    try:
        return float(raw.replace(",", "."))
    except ValueError:
        return None


def _parse_line(line: str) -> tuple[str, str, dict] | None:
    """
    Parst eine RENPHO-CSV-Zeile.
    Rückgabe: (ts_utc, date_local, {col: value_or_None})
    """
    # Erster Token ist Timestamp, Rest sind Key(unit):value-Paare
    parts = [p.strip() for p in line.split(",") if p.strip()]
    if not parts:
        return None

    result = _parse_ts(parts[0])
    if not result:
        return None
    ts, date = result

    values: dict[str, float | None] = {}
    for token in parts[1:]:
        # Format: "Schlüssel(einheit):wert" oder "Schlüssel:wert" (ohne Einheit)
        m = re.match(r"^(.+?)(?:\([^)]*\))?:(.*)$", token)
        if not m:
            continue
        key = m.group(1).strip()
        val_str = m.group(2).strip()
        if key not in _FIELD_MAP:
            continue
        col, _ = _FIELD_MAP[key]
        values[col] = _parse_value(val_str)

    return ts, date, values


def import_file(conn, filepath: Path, update_from: str | None, person: str) -> int:
    _ensure_columns(conn)
    text = filepath.read_text(encoding="utf-8-sig", errors="replace")
    imported = 0

    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        parsed = _parse_line(line)
        if not parsed:
            continue
        ts, date, values = parsed

        if update_from and date < update_from:
            continue

        cols = ["ts", "date", "device_id", "person", "source"] + list(values.keys())
        placeholders = ", ".join(["?"] * len(cols))
        col_str = ", ".join(cols)
        row = [ts, date, "renpho_tape", person, "renpho_csv"] + list(values.values())

        try:
            conn.execute(
                f"INSERT OR IGNORE INTO body_composition ({col_str}) VALUES ({placeholders})",
                row,
            )
            imported += 1
        except Exception:
            pass

    conn.commit()
    return imported


def list_inbox_csvs() -> list[Path]:
    return sorted(INBOX_DIR.glob("RENPHO*.csv"))


def move_to_processed(csv: Path) -> None:
    processed_dir = INBOX_DIR / "processed"
    processed_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    target = processed_dir / f"{csv.stem}_{stamp}{csv.suffix}"
    shutil.move(str(csv), str(target))
    print(t(f"  → verschoben nach {target.name}", f"  → moved to {target.name}"))


def main() -> None:
    parser = argparse.ArgumentParser(description=t(
        "RENPHO-Maßband-CSV → health.db",
        "RENPHO tape measure CSV → health.db",
    ))
    parser.add_argument("--file", help=t("Expliziter CSV-Pfad", "Explicit CSV path"))
    parser.add_argument("--inbox", action="store_true",
                        help=t("Verarbeite _inbox/RENPHO*.csv", "Process _inbox/RENPHO*.csv"))
    parser.add_argument("--update", action="store_true",
                        help=t("Nur neue Daten importieren", "Import only new data"))
    parser.add_argument("--person", default=None, help="Ziel-Person (Default: OWN_PERSON_ID)")
    add_lang_arg(parser)
    args = parser.parse_args()
    apply_lang_from_args(args)
    person = resolve_person(args.person)

    conn = open_db()

    update_from: str | None = None
    if args.update:
        row = conn.execute(
            "SELECT MAX(date) FROM body_composition WHERE source='renpho_csv'"
        ).fetchone()
        update_from = row[0] if row and row[0] else None
        if update_from:
            print(t(f"  Update-Modus: ab {update_from}", f"  Update mode: from {update_from}"))

    total = 0

    if args.file:
        files = [Path(args.file)]
    elif args.inbox:
        files = list_inbox_csvs()
        if not files:
            print(t("Keine RENPHO*.csv in _inbox/ gefunden.", "No RENPHO*.csv found in _inbox/."))
            return
    else:
        # Fallback: alle CSVs im renpho-Verzeichnis
        files = sorted(RENPHO_DIR.glob("RENPHO*.csv"))
        if not files:
            print(t(
                "Keine CSV-Dateien gefunden. Lege Datei in imports/renpho/ oder nutze --inbox.",
                "No CSV files found. Place file in imports/renpho/ or use --inbox.",
            ))
            return

    for f in files:
        print(t(f"Importiere {f.name} ...", f"Importing {f.name} ..."))
        n = import_file(conn, f, update_from, person)
        total += n
        print(t(f"  {n} Messung(en) importiert.", f"  {n} measurement(s) imported."))
        if args.inbox:
            move_to_processed(f)

    log_import(conn, "import_renpho_tape", str(files[0]) if files else "", total, person=person)
    conn.commit()
    conn.close()

    r = None
    with open_db() as c:
        r = c.execute(
            "SELECT COUNT(*), MIN(date), MAX(date) FROM body_composition WHERE source='renpho_csv'"
        ).fetchone()
    if r and r[0]:
        print(t(
            f"\nGesamt in DB: {r[0]} Messungen | {r[1]} – {r[2]}",
            f"\nTotal in DB: {r[0]} measurements | {r[1]} – {r[2]}",
        ))


if __name__ == "__main__":
    main()
