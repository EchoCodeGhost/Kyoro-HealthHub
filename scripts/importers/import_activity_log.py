#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Subjektives Aktivitätsprotokoll → health.db (activity_log)

@tier        infrastructure
@purpose.de  Importiert subjektive Aktivitäts- und Belastungsdaten
@purpose.en  Imports subjective activity and load data
@method.de   Liest taegliche YAML-Dateien mit subjektiven Belastungsscores (1-10) aus
             imports/activity_log/ und schreibt sie in die Tabelle activity_log.
             YAML-Format unterstuetzt Einzeltage oder Mehrtageslisten.
             Felder: date, sensory_load, cognitive_load, social_effort, triggers, notes.
@method.en   Reads daily YAML files with subjective load scores (1-10) from
             imports/activity_log/ and writes them to the activity_log table.
             YAML format supports single days or multi-day lists.
             Fields: date, sensory_load, cognitive_load, social_effort, triggers, notes.
@reads       YAML-Dateien aus imports/activity_log/
@writes      activity_log
@limits.de   Subjektive Daten. Qualitaet abhaengig von manueller Eingabe.
             run() reichte person schon vorher korrekt durch; main() hatte aber
             kein --person-Flag — jetzt ergaenzt.

@relevance.de  Ermöglicht den Import von Gesundheitsdaten, essentiell für die umfassende Datenanalyse
@relevance.en  Enables import of health data, essential for comprehensive data analysis
@limits.en   Subjective data. Quality depends on manual input.
             run() already threaded person through correctly, but main() had no
             --person flag — now added.
@usage
    python3 import_activity_log.py           # alle YAML-Dateien
    python3 import_activity_log.py --update  # nur neue Daten
    python3 import_activity_log.py --template  # Beispiel-YAML ausgeben
    python3 import_activity_log.py --person PER-xxxxxxxx
"""

import argparse
import sqlite3
from datetime import date
from pathlib import Path
import sys as _sys

try:
    import yaml as _yaml
    _YAML = True
except ImportError:
    _YAML = False

_sys.path.insert(0, str(Path(__file__).parent.parent))
from health_config import Config as _Cfg, OWN_PERSON_ID
from modules.db import open_db
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from modules.base import log_import, ImportResult
_cfg = _Cfg()

ACTIVITY_LOG_DIR = Path(_cfg._cfg.get("paths", {}).get(
    "activity_log_dir",
    str(Path.home() / "Kyoro-HealthHub" / "imports" / "activity_log"),
))
ACTIVITY_LOG_DIR.mkdir(parents=True, exist_ok=True)

_TEMPLATE = """\
# Aktivitätsprotokoll — subjektive Belastungsscores (0–10)
# 0 = gar nicht, 5 = moderat, 10 = maximal
date: {date}
sensory_load: 0        # Sensorische Last (Lärm, Licht, Gerüche, Reizüberflutung)
cognitive_load: 0      # Kognitive Last (Konzentration, Entscheidungen, Problemlösung)
social_effort: 0       # Soziale Anstrengung (Masking, Kommunikation, Auftritte)
triggers: []           # Aktive Trigger-Kategorien: laerm, licht, geruch, menschenmenge
notes: ""              # Freitext (optional)
"""


def _ensure_table(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS activity_log (
            date              TEXT NOT NULL,
            person            TEXT NOT NULL,
            sensory_load      REAL,
            cognitive_load    REAL,
            social_effort     REAL,
            sensory_triggers  TEXT,
            notes             TEXT,
            source            TEXT DEFAULT 'manual_yaml',
            PRIMARY KEY (date, person)
        );
    """)
    # Migration: sensory_triggers sowie physical_load_subjective/emotional_load
    # (s. compute_gesamtpensum.py) für bestehende DBs
    cols = {r[1] for r in conn.execute("PRAGMA table_info(activity_log)").fetchall()}
    if "sensory_triggers" not in cols:
        conn.execute("ALTER TABLE activity_log ADD COLUMN sensory_triggers TEXT")
    for col in ("physical_load_subjective", "emotional_load"):
        if col not in cols:
            conn.execute(f"ALTER TABLE activity_log ADD COLUMN {col} REAL")
    conn.commit()


def _parse_yaml(path: Path) -> list[dict]:
    if not _YAML:
        raise ImportError("PyYAML nicht installiert. Bitte: pip install pyyaml")
    content = path.read_text(encoding="utf-8")
    data = _yaml.safe_load(content)
    if data is None:
        return []
    if isinstance(data, list):
        return data
    if "entries" in data and isinstance(data["entries"], list):
        return data["entries"]
    if "date" in data:
        return [data]
    return []


def _parse_triggers(raw) -> str | None:
    """Normalize YAML triggers field → lowercase comma-separated string or None."""
    if raw is None:
        return None
    if isinstance(raw, list):
        items = [str(x).strip().lower() for x in raw if str(x).strip()]
    elif isinstance(raw, str):
        items = [x.strip().lower() for x in raw.split(",") if x.strip()]
    else:
        return None
    return ",".join(items) if items else None


def _validate_score(val, field: str) -> float | None:
    if val is None:
        return None
    try:
        v = float(val)
        if not (0 <= v <= 10):
            raise ValueError(f"{field}={val} außerhalb 0–10")
        return v
    except (TypeError, ValueError) as e:
        raise ValueError(f"Ungültiger Wert für {field}: {val}") from e


def _import_entries(conn: sqlite3.Connection, entries: list[dict],
                    person: str, update_only: bool) -> tuple[int, int]:
    """Returns (inserted, skipped)."""
    inserted = 0
    skipped = 0
    for entry in entries:
        raw_date = entry.get("date")
        if not raw_date:
            continue
        d = str(raw_date).strip()
        sensory   = _validate_score(entry.get("sensory_load"),   "sensory_load")
        cognitive = _validate_score(entry.get("cognitive_load"), "cognitive_load")
        social    = _validate_score(entry.get("social_effort"),  "social_effort")
        triggers  = _parse_triggers(entry.get("triggers"))
        notes     = entry.get("notes") or None

        if update_only:
            row = conn.execute(
                "SELECT 1 FROM activity_log WHERE date=? AND person=?", (d, person)
            ).fetchone()
            if row:
                skipped += 1
                continue

        conn.execute(
            "INSERT OR IGNORE INTO activity_log"
            "(date, person, sensory_load, cognitive_load, social_effort,"
            " sensory_triggers, notes, source)"
            " VALUES (?,?,?,?,?,?,?,'manual_yaml')",
            (d, person, sensory, cognitive, social, triggers, notes),
        )
        inserted += 1
    return inserted, skipped


def run(conn: sqlite3.Connection, data_path: Path | None = None,
        lang: str = "de", person: str | None = None, update: bool = False) -> ImportResult:
    _ensure_table(conn)
    person = person or OWN_PERSON_ID
    search_dir = data_path or ACTIVITY_LOG_DIR
    yaml_files = sorted(Path(search_dir).glob("*.yaml")) + sorted(Path(search_dir).glob("*.yml"))
    if not yaml_files:
        msg = t(f"Keine YAML-Dateien in {search_dir}", f"No YAML files in {search_dir}")
        print(msg)
        return ImportResult(source="activity_log", rows_inserted=0)

    total_inserted = total_skipped = total_errors = 0
    for path in yaml_files:
        try:
            entries = _parse_yaml(path)
            ins, skip = _import_entries(conn, entries, person, update)
            total_inserted += ins
            total_skipped  += skip
        except Exception as e:
            total_errors += 1
            print(t(f"  Fehler in {path.name}: {e}", f"  Error in {path.name}: {e}"),
                  file=_sys.stderr)

    log_import(conn, "activity_log", str(search_dir), total_inserted, total_skipped)
    conn.commit()
    msg = t(
        f"{total_inserted} Einträge importiert, {total_skipped} übersprungen, {total_errors} Fehler",
        f"{total_inserted} entries imported, {total_skipped} skipped, {total_errors} errors",
    )
    print(msg)
    return ImportResult(source="activity_log", rows_inserted=total_inserted)


def _print_template() -> None:
    print(_TEMPLATE.format(date=date.today().isoformat()))


def main() -> None:
    parser = argparse.ArgumentParser(description=t(
        "Aktivitätsprotokoll (subjektive Belastungsscores) importieren",
        "Import activity log (subjective load scores)",
    ))
    parser.add_argument("--update", action="store_true",
                        help=t("Nur neue Einträge (bereits vorhandene Daten überspringen)",
                               "Import only new entries (skip existing dates)"))
    parser.add_argument("--template", action="store_true",
                        help=t("Beispiel-YAML ausgeben", "Print template YAML"))
    parser.add_argument("--dir", type=Path,
                        help=t("Verzeichnis mit YAML-Dateien", "Directory with YAML files"))
    parser.add_argument("--person", default=None, metavar="PERSON_ID",
                        help=t("Person-ID (Standard: eigene Person aus Config)",
                               "Person ID (default: own person from config)"))
    add_lang_arg(parser)
    args = parser.parse_args()
    apply_lang_from_args(args)

    if args.template:
        _print_template()
        return

    conn = open_db()
    try:
        run(conn, data_path=args.dir, person=args.person, update=args.update)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
