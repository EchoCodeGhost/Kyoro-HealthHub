#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
import_shotsy.py — Shotsy-Export → health.db

@tier        infrastructure
@purpose.de  Importiert Injektions-Daten aus Shotsy-App Exports in die health.db
@purpose.en  Imports injection data from Shotsy app exports into health.db
@method.de   Unterstützt JSON- und CSV-Exportformate von Shotsy. Timestamps werden von lokaler Zeit in UTC konvertiert.
             Daten werden in die Tabellen geschrieben mit Feldern: ts, date, id, drug_name,
             dose_value, dose_unit, route, injection_site, is_skipped, notes, person, source.
             Zusätzlich werden Nebenwirkungen und Notizen gespeichert.
             Unterstützt auch das .shotsyjson-Format mit Tagesstruktur und Nebenwirkungs-Tracking.
             Nebenwirkungen (symptoms, source='shotsy') werden nach dem Import per
             attribute_side_effects_to_medication() mit dem Namen der zeitlich zuletzt
             vorangegangenen Injektion verknüpft (symptoms.value_text) — Shotsy loggt
             Nebenwirkungen tagesweise, nicht pro Injektion, daher best-effort statt
             exakter Zuordnung.
@method.en   Supports JSON and CSV export formats from Shotsy. Timestamps are converted from local time to UTC.
             Data is written to tables with fields: ts, date, id, drug_name,
             dose_value, dose_unit, route, injection_site, is_skipped, notes, person, source.
             Side effects and notes are additionally stored.
             Also supports .shotsyjson format with daily structure and side effect tracking.
             After import, side effects (symptoms, source='shotsy') are linked via
             attribute_side_effects_to_medication() to the name of the most recent
             preceding injection (symptoms.value_text) — Shotsy logs side effects per
             day, not per injection, so this is best-effort rather than exact
             attribution.
@reads       Shotsy JSON/CSV/.shotsyjson Dateien aus imports/shotsy/ Verzeichnis
@writes      Tabellen: Injektionsdaten, Nebenwirkungen (inkl. Medikamenten-Zuordnung), Notizen, import_log
@limits.de   Abhaengig von Shotsy Export-Format. Zeitumrechnung erfordert korrekte Zeitzonen-Konfiguration.
             Keine medizinische Validierung der Dosierungen.

@relevance.de  Ermöglicht den Import von Gesundheitsdaten, essentiell für die umfassende Datenanalyse
@relevance.en  Enables import of health data, essential for comprehensive data analysis
@limits.en   Depends on Shotsy export format. Timezone conversion requires correct timezone configuration.
             No medical validation of dosages.
@usage
    python3 import_shotsy.py
    python3 import_shotsy.py --update
    python3 import_shotsy.py --file export.json
    python3 import_shotsy.py --file export.csv --lang en
    python3 import_shotsy.py --dir /pfad/zu/exports
"""

import argparse
import csv
import io
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
import sys as _sys

_sys.path.insert(0, str(Path(__file__).parent.parent))
from health_config import Config as _Cfg
from modules.db import open_db
from modules.base import ImportResult, log_import, resolve_person, resolve_timezone
from modules.i18n import t, add_lang_arg, apply_lang_from_args

_cfg = _Cfg()
DB_PATH    = _cfg.db_path
SHOTSY_DIR = _cfg.data_root / "shotsy"
SHOTSY_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# JSON field name variants Shotsy has used across app versions
# ---------------------------------------------------------------------------
_TS_KEYS    = ("timestamp", "date", "scheduledDate", "takenAt", "injectionDate",
               "injection_date", "taken_at")
_NAME_KEYS  = ("medicationName", "medication", "name", "drug", "drugName",
               "medication_name", "drug_name")
_DOSE_KEYS  = ("dose", "amount", "doseAmount", "dose_amount")
_UNIT_KEYS  = ("unit", "doseUnit", "dose_unit", "dosageUnit")
_SITE_KEYS  = ("injectionSite", "site", "injection_site", "bodyLocation",
               "body_location", "location")
_SKIP_KEYS  = ("skipped", "isSkipped", "is_skipped", "missed")
_NOTE_KEYS  = ("notes", "note", "comment", "comments")
_ID_KEYS    = ("id", "uuid", "injectionId", "injection_id")


def _first(d: dict, keys: tuple, default=None):
    for k in keys:
        if k in d:
            return d[k]
    return default


def _to_float(v) -> float | None:
    if v is None:
        return None
    try:
        return float(str(v).replace(",", ".").strip())
    except (ValueError, TypeError):
        return None


def _to_bool_int(v) -> int:
    if v is None:
        return 0
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, int):
        return int(bool(v))
    return 1 if str(v).lower() in ("true", "1", "yes", "ja") else 0


def _local_to_utc(ts_str: str, tz_name: str) -> str:
    """Konvertiert lokalen Timestamp-String → UTC ISO 8601 mit +00:00."""
    ts_str = ts_str.strip()
    # Versuche verschiedene Formate
    for fmt in (
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%d.%m.%Y %H:%M:%S",
        "%d.%m.%Y %H:%M",
        "%m/%d/%Y %H:%M:%S",
        "%m/%d/%Y %H:%M",
        "%Y-%m-%d",
    ):
        try:
            dt_local = datetime.strptime(ts_str, fmt)
            break
        except ValueError:
            continue
    else:
        raise ValueError(f"Unbekanntes Timestamp-Format: {ts_str!r}")

    try:
        import zoneinfo
        tz = zoneinfo.ZoneInfo(tz_name)
        dt_aware = dt_local.replace(tzinfo=tz)
    except Exception:
        # Fallback: einfache UTC-Offset-Schätzung via pytz wenn verfügbar
        try:
            import pytz
            tz = pytz.timezone(tz_name)
            dt_aware = tz.localize(dt_local)
        except Exception:
            dt_aware = dt_local.replace(tzinfo=timezone.utc)

    dt_utc = dt_aware.astimezone(timezone.utc)
    return dt_utc.strftime("%Y-%m-%dT%H:%M:%S+00:00")


# ---------------------------------------------------------------------------
# Normalisierung eines einzelnen Eintrags (dict) → DB-Tupel
# ---------------------------------------------------------------------------
def _norm_entry(entry: dict, tz_name: str) -> dict | None:
    ts_raw = _first(entry, _TS_KEYS)
    if not ts_raw:
        return None

    try:
        ts_utc = _local_to_utc(str(ts_raw), tz_name)
    except ValueError:
        return None

    date_str = ts_utc[:10]

    return {
        "ts":             ts_utc,
        "date":           date_str,
        "medication_id":  str(_first(entry, _ID_KEYS) or ""),
        "drug_name":      str(_first(entry, _NAME_KEYS) or "").strip() or None,
        "dose_value":     _to_float(_first(entry, _DOSE_KEYS)),
        "dose_unit":      str(_first(entry, _UNIT_KEYS) or "").strip() or None,
        "route":          "subcutaneous",
        "injection_site": str(_first(entry, _SITE_KEYS) or "").strip() or None,
        "is_skipped":     _to_bool_int(_first(entry, _SKIP_KEYS)),
        "notes":          str(_first(entry, _NOTE_KEYS) or "").strip() or None,
    }


# ---------------------------------------------------------------------------
# CSV-Parsing
# ---------------------------------------------------------------------------
_CSV_COL_MAP = {
    # Timestamp
    "date":             _TS_KEYS,
    "time":             (),          # wird separat kombiniert
    "timestamp":        _TS_KEYS,
    # Medication
    "medication":       _NAME_KEYS,
    "medicationname":   _NAME_KEYS,
    "drug":             _NAME_KEYS,
    # Dose
    "dose":             _DOSE_KEYS,
    "amount":           _DOSE_KEYS,
    # Unit
    "unit":             _UNIT_KEYS,
    # Site
    "injectionsite":    _SITE_KEYS,
    "site":             _SITE_KEYS,
    # Skipped
    "skipped":          _SKIP_KEYS,
    # Notes
    "notes":            _NOTE_KEYS,
    "note":             _NOTE_KEYS,
    # ID
    "id":               _ID_KEYS,
}


def _csv_row_to_dict(row: dict) -> dict:
    """Normalisiert einen CSV-Row (Header-Keys variieren je nach App-Version)."""
    norm = {}
    # Spalten nach normalisierten Schlüsseln mappen
    for raw_key, value in row.items():
        k = raw_key.strip().lower().replace(" ", "").replace("_", "")
        if k in ("date", "datum"):
            norm.setdefault("_date_part", value.strip())
        elif k in ("time", "zeit", "uhrzeit"):
            norm.setdefault("_time_part", value.strip())
        elif k in ("timestamp", "datetime", "injectiondate", "injectiondatetime"):
            norm.setdefault("timestamp", value.strip())
        elif k in ("medication", "medicationname", "medikament", "name", "drug"):
            norm.setdefault("medicationName", value.strip())
        elif k in ("dose", "dosis", "amount", "doseamount"):
            norm.setdefault("dose", value.strip())
        elif k in ("unit", "einheit", "doseunit"):
            norm.setdefault("unit", value.strip())
        elif k in ("injectionsite", "site", "stelle", "bodylocation", "location"):
            norm.setdefault("injectionSite", value.strip())
        elif k in ("skipped", "isskipped", "missed", "uebersprungen"):
            norm.setdefault("skipped", value.strip())
        elif k in ("notes", "note", "notizen", "kommentar", "comment"):
            norm.setdefault("notes", value.strip())
        elif k in ("id", "uuid"):
            norm.setdefault("id", value.strip())

    # Date + Time separat → timestamp zusammensetzen
    if "timestamp" not in norm and "_date_part" in norm:
        date_part = norm.pop("_date_part")
        time_part = norm.pop("_time_part", "00:00")
        norm["timestamp"] = f"{date_part} {time_part}"
    else:
        norm.pop("_date_part", None)
        norm.pop("_time_part", None)

    return norm


def _parse_csv(path: Path) -> list[dict]:
    raw = path.read_bytes()
    # UTF-8 mit/ohne BOM
    text = raw.decode("utf-8-sig")
    # Auto-detect Trennzeichen
    first_line = text.split("\n", 1)[0]
    delimiter = ";" if first_line.count(";") >= first_line.count(",") else ","
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    return [_csv_row_to_dict(row) for row in reader]


def _parse_json(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    # Shotsy exportiert entweder ein Array oder {"injections": [...]}
    if isinstance(data, list):
        return data
    for key in ("injections", "entries", "shots", "data", "records"):
        if isinstance(data.get(key), list):
            return data[key]
    raise ValueError(f"Unbekannte JSON-Struktur in {path.name}: kein Array gefunden")


# ---------------------------------------------------------------------------
# .shotsyjson parser  (neueres Exportformat mit days-Struktur)
# ---------------------------------------------------------------------------

def _parse_shotsyjson(path: Path) -> tuple[list[dict], list[dict]]:
    """Parst .shotsyjson-Format.
    Gibt (shot_entries, side_effect_rows) zurück.
    Health-Metriken (Weight, Exercise, …) werden ignoriert — bereits via
    Apple Health in der DB.
    """
    data = json.loads(path.read_text(encoding="utf-8"))
    shots_out: list[dict] = []
    se_out: list[dict] = []

    for day_dict in data.get("days", []):
        for epoch_str, entries in day_dict.items():
            day_dt = datetime.fromtimestamp(int(epoch_str), tz=timezone.utc)
            day_date = day_dt.strftime("%Y-%m-%d")

            for shot in entries.get("shots", []):
                ts_unix = shot.get("timestamp")
                if not ts_unix:
                    continue
                ts_dt = datetime.fromtimestamp(int(ts_unix), tz=timezone.utc)

                note_raw = _first(shot, _NOTE_KEYS)
                pain = shot.get("painLevel")
                note_parts = []
                if note_raw:
                    note_parts.append(str(note_raw).strip())
                if pain is not None and pain > 0:
                    note_parts.append(f"Schmerz: {pain}/10")

                shots_out.append({
                    "ts":             ts_dt.strftime("%Y-%m-%dT%H:%M:%S+00:00"),
                    "date":           ts_dt.strftime("%Y-%m-%d"),
                    "medication_id":  shot.get("schedule", {}).get("scheduleID") or "",
                    "drug_name":      shot.get("medicationName") or None,
                    "dose_value":     _to_float(shot.get("dosageStrength")),
                    "dose_unit":      "mg",
                    "route":          shot.get("deliveryMethod") or "injection",
                    "injection_site": shot.get("injectionSite") or None,
                    "is_skipped":     0 if shot.get("taken", True) else 1,
                    "notes":          " | ".join(note_parts) or None,
                })

            se_dict = entries.get("sideEffects")
            if isinstance(se_dict, dict):
                for name, severity in se_dict.items():
                    se_out.append({
                        "date":      day_date,
                        "symptom":   name,
                        "value_num": float(severity),
                    })

    return shots_out, se_out


# ---------------------------------------------------------------------------
# DB-Insert
# ---------------------------------------------------------------------------
_INSERT_MED_SQL = """
INSERT OR IGNORE INTO medications
    (ts, date, medication_id, drug_name, dose_value, dose_unit,
     route, injection_site, is_skipped, notes, person, source)
VALUES
    (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'shotsy')
"""

_INSERT_SQL = _INSERT_MED_SQL  # Rückwärtskompatibilität


def _insert(cur: sqlite3.Cursor, entry: dict, person: str) -> bool:
    mid = entry["medication_id"] or None
    cur.execute(_INSERT_MED_SQL, (
        entry["ts"], entry["date"], mid,
        entry["drug_name"], entry["dose_value"], entry["dose_unit"],
        entry["route"], entry["injection_site"],
        entry["is_skipped"], entry["notes"],
        person,
    ))
    return cur.rowcount > 0


def _insert_side_effects(cur: sqlite3.Cursor, se_rows: list[dict], person: str) -> int:
    n = 0
    for row in se_rows:
        cur.execute(
            "INSERT OR IGNORE INTO symptoms (date, symptom, value_num, category, person, source) "
            "VALUES (?, ?, ?, 'side_effect', ?, 'shotsy')",
            (row["date"], row["symptom"], row["value_num"], person),
        )
        if cur.rowcount > 0:
            n += 1
    return n


def attribute_side_effects_to_medication(cur: sqlite3.Cursor, person: str) -> int:
    """Traegt in symptoms.value_text nach, welches Medikament am wahrscheinlichsten
    fuer eine Shotsy-Nebenwirkung verantwortlich ist.

    Side effects werden in Shotsy tagesweise geloggt, nicht pro Injektion —
    eine Nebenwirkung am Tag X kann von einer frueheren Injektion stammen
    (Nebenwirkungen einer wöchentlichen Injektionsmedikation zeigen sich oft
    mit 1-3 Tagen Verzögerung, nicht am Injektionstag selbst). value_text
    bleibt daher der Name
    der zeitlich naechsten VORANGEGANGENEN (oder gleichtaegigen) Injektion,
    keine exakte Kausalitaet — best-effort Zuordnung, kein Beweis.
    """
    cur.execute("""
        UPDATE symptoms
        SET value_text = (
            SELECT m.drug_name FROM medications m
            WHERE m.person = symptoms.person AND m.source = 'shotsy'
              AND m.date <= symptoms.date AND m.drug_name IS NOT NULL
            ORDER BY m.date DESC LIMIT 1
        )
        WHERE symptoms.source = 'shotsy' AND symptoms.person = ?
          AND symptoms.value_text IS NULL
    """, (person,))
    return cur.rowcount


def _insert_notes_context(cur: sqlite3.Cursor, entries: list[dict], person: str) -> None:
    for e in entries:
        if not e.get("notes"):
            continue
        cur.execute(
            "INSERT OR IGNORE INTO user_context "
            "(id, date, ts_start, ts_end, person, source, source_app, tag, note) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (f"shotsy:{e['ts']}", e["date"], e["ts"], None,
             person, "shotsy", "shotsy", e["drug_name"], e["notes"]),
        )


# ---------------------------------------------------------------------------
# Haupt-Importfunktion
# ---------------------------------------------------------------------------
def run(conn: sqlite3.Connection,
        shotsy_dir: Path = SHOTSY_DIR,
        file: Path | None = None,
        update_only: bool = False,
        person: str | None = None,
        lang: str = "de") -> ImportResult:

    result = ImportResult(source="shotsy")
    person = resolve_person(person)
    tz_name = resolve_timezone(conn, person)

    files: list[Path] = []
    if file:
        files = [file]
    else:
        files = (sorted(shotsy_dir.glob("*.shotsyjson"))
                 + sorted(shotsy_dir.glob("*.json"))
                 + sorted(shotsy_dir.glob("*.csv")))

    if not files:
        print(t(
            f"  Keine Shotsy-Dateien in {shotsy_dir}",
            f"  No Shotsy files in {shotsy_dir}",
        ))
        return result

    cur = conn.cursor()

    for path in files:
        suffix = path.suffix.lower()
        try:
            if suffix == ".shotsyjson":
                shot_entries, se_rows = _parse_shotsyjson(path)
                file_inserted = file_skipped = 0

                for entry in shot_entries:
                    if update_only:
                        exists = cur.execute(
                            "SELECT 1 FROM medications WHERE ts=? AND person=? AND source='shotsy'",
                            (entry["ts"], person),
                        ).fetchone()
                        if exists:
                            file_skipped += 1
                            continue
                    if _insert(cur, entry, person):
                        file_inserted += 1
                    else:
                        file_skipped += 1

                se_inserted = _insert_side_effects(cur, se_rows, person)
                attribute_side_effects_to_medication(cur, person)
                _insert_notes_context(cur, shot_entries, person)

                result.rows_inserted += file_inserted
                result.rows_skipped  += file_skipped
                print(t(
                    f"  {path.name}: {file_inserted} Injektionen, "
                    f"{se_inserted} Nebenwirkungen, {file_skipped} übersprungen",
                    f"  {path.name}: {file_inserted} injections, "
                    f"{se_inserted} side effects, {file_skipped} skipped",
                ))
                continue

            elif suffix == ".json":
                raw_entries = _parse_json(path)
            elif suffix == ".csv":
                raw_entries = _parse_csv(path)
            else:
                print(t(f"  Überspringe {path.name} (unbekanntes Format)",
                        f"  Skipping {path.name} (unknown format)"))
                continue
        except Exception as exc:
            msg = t(f"  Fehler beim Lesen von {path.name}: {exc}",
                    f"  Error reading {path.name}: {exc}")
            print(msg)
            result.errors.append(str(exc))
            continue

        file_inserted = file_skipped = 0
        for raw in raw_entries:
            if not raw:
                continue
            try:
                entry = _norm_entry(raw, tz_name)
            except Exception as exc:
                result.errors.append(f"{path.name}: {exc}")
                continue

            if entry is None:
                result.errors.append(f"{path.name}: kein Timestamp in Eintrag {raw!r:.80}")
                continue

            if update_only:
                exists = cur.execute(
                    "SELECT 1 FROM medications WHERE ts=? AND person=? AND source='shotsy'",
                    (entry["ts"], person),
                ).fetchone()
                if exists:
                    file_skipped += 1
                    continue

            if _insert(cur, entry, person):
                file_inserted += 1
            else:
                file_skipped += 1

        result.rows_inserted += file_inserted
        result.rows_skipped  += file_skipped
        print(t(
            f"  {path.name}: {file_inserted} neu, {file_skipped} übersprungen",
            f"  {path.name}: {file_inserted} new, {file_skipped} skipped",
        ))

    log_import(conn, "shotsy", str(file or shotsy_dir), result.rows_inserted, result.rows_skipped,
              person=person)
    conn.commit()

    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(
        description=t("Shotsy-Export → health.db (medications)",
                      "Shotsy export → health.db (medications)"),
    )
    parser.add_argument("--file", metavar="FILE", default=None,
                        help=t("Einzelne JSON- oder CSV-Datei",
                               "Single JSON or CSV file"))
    parser.add_argument("--dir", metavar="DIR", default=None,
                        help=t("Verzeichnis mit Shotsy-Exports (Standard: imports/shotsy/)",
                               "Directory with Shotsy exports (default: imports/shotsy/)"))
    parser.add_argument("--update", action="store_true",
                        help=t("Nur neue Einträge ergänzen, keine Duplikate",
                               "Only add new entries, skip duplicates"))
    parser.add_argument("--person", metavar="ID", default=None)
    add_lang_arg(parser)

    args = parser.parse_args()
    apply_lang_from_args(args)

    shotsy_dir = Path(args.dir) if args.dir else SHOTSY_DIR
    file_path  = Path(args.file) if args.file else None

    conn = open_db()
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")

    print(t(
        "\n── Shotsy ─────────────────────────────────────────────",
        "\n── Shotsy ─────────────────────────────────────────────",
    ))

    result = run(conn, shotsy_dir=shotsy_dir, file=file_path,
                 update_only=args.update, person=args.person)

    total = conn.execute(
        "SELECT COUNT(*), MIN(date), MAX(date) FROM medications WHERE source='shotsy'"
    ).fetchone()
    print(t(
        f"  Gesamt in DB: {total[0]} | {total[1]}–{total[2]}",
        f"  Total in DB:  {total[0]} | {total[1]}–{total[2]}",
    ))
    print(t(f"  {result}", f"  {result}"))

    conn.close()


if __name__ == "__main__":
    main()
