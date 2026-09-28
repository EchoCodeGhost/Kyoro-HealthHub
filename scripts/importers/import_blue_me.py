#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
import_blue_me.py — blue-ME JSON-Export → health.db (symptoms, sessions)

@tier        infrastructure
@purpose.de  Importiert JSON-Exporte der Symptom-Tracking-App blue-ME in die
             gemeinsamen Tabellen symptoms (Bereich "tracking": tägliche
             Symptom-/Belastungs-/Achtsamkeitswerte) und sessions/
             session_metrics (Bereich "activity": einzelne Aktivitäten mit
             Dauer, Belastungsart und -stärke).
@purpose.en  Imports JSON exports from the blue-ME symptom-tracking app into
             the shared symptoms table ("tracking" section: daily symptom/
             exertion/mindfulness values) and sessions/session_metrics
             ("activity" section: individual activities with duration,
             exertion type and level).
@method.de   Liest eine blue-ME-Exportdatei (Schlüssel "tracking"[] und
             "activity"[]). Jedes tracking-Objekt wird feldweise in
             symptoms zerlegt (ein Feld = ein Symptom-Datensatz, EAV-Muster);
             numerische Felder → value_num, nichtleere String-Felder →
             value_text, die Supplement-Liste wird zu einem kommagetrennten
             Text zusammengefasst. Jedes activity-Objekt wird zu einer
             sessions-Zeile (type='activity') mit Dauer/Belastung/
             Beschreibung/Aufzeichnungsart als session_metrics. Zeitstempel
             sind im Export naive lokale Zeit ohne Offset — werden über
             resolve_timezone() interpretiert und nach UTC konvertiert.
@method.en   Reads a blue-ME export file (keys "tracking"[] and
             "activity"[]). Each tracking object is split field-by-field
             into symptoms (one field = one symptom record, EAV pattern);
             numeric fields → value_num, non-empty string fields →
             value_text, the supplement list is joined into a comma-
             separated text. Each activity object becomes one sessions row
             (type='activity') with duration/exertion/description/record
             type as session_metrics. Timestamps in the export are naive
             local time without offset — interpreted via resolve_timezone()
             and converted to UTC.
@reads       blue_me_data_export_*.json (blue-ME app export)
@writes      symptoms, sessions, session_metrics
@limits.de   Feldnamen werden 1:1 aus dem Export als symptom-Bezeichner
             übernommen (kein festes Mapping auf eine kontrollierte
             Symptom-Taxonomie) — neue Felder der App tauchen automatisch
             als neue Symptom-Namen auf, ohne Code-Änderung, aber auch ohne
             Validierung gegen Tippfehler/Umbenennungen seitens der App.
             Die "average*"-Felder sind von der App selbst berechnete
             Werte, keine Rohmessung — werden mit category='berechnet'
             gekennzeichnet. Nur JSON-Exporte werden unterstützt, kein CSV.
             Jede:r Nutzer:in kann in blue-ME eigene Activities anlegen —
             "exertionType" und "description" im activity-Bereich sind
             deshalb freier, nutzerdefinierter Text, keine feste, aus der
             App bekannte Werteliste. Der Importer validiert/filtert diese
             Felder daher bewusst nicht gegen eine Enum (reine value_text-
             Übernahme in session_metrics) — jede künftige Auswertung
             dieser Felder (aktuell liest kein Skript sessions type=
             'activity') muss ebenfalls offenes Vokabular annehmen statt
             eine feste Kategorienliste (z.B. "Körperlich"/"Geistig"/
             "Emotional"/"Sozial") vorauszusetzen.

@relevance.de  Bietet Gesundheitsdatenfunktionen, essentiell für die medizinische Datenverarbeitung
@relevance.en  Provides health data functions, essential for medical data processing
@limits.en   Field names are taken verbatim from the export as symptom
             identifiers (no fixed mapping onto a controlled symptom
             taxonomy) — new app fields automatically appear as new symptom
             names without a code change, but also without validation
             against typos/renames on the app's side. The "average*"
             fields are values computed by the app itself, not a raw
             measurement — tagged with category='berechnet'. Only JSON
             exports are supported, not CSV. Any blue-ME user can define
             their own activities — "exertionType" and "description" in
             the activity section are therefore free, user-defined text,
             not a fixed value list known to the app. The importer
             deliberately does not validate/filter these fields against
             an enum (plain value_text pass-through into session_metrics)
             — any future analysis of these fields (currently no script
             reads sessions type='activity') must likewise assume open
             vocabulary instead of a fixed category list (e.g. "Körperlich"/
             "Geistig"/"Emotional"/"Sozial").
@usage
    python3 scripts/importers/import_blue_me.py blue_me_export.json
    python3 scripts/importers/import_blue_me.py blue_me_export.json --person oma
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).parent.parent))
from modules.base import ImportResult, log_import, resolve_person, resolve_timezone
from modules.db import open_db
from modules.i18n import t, add_lang_arg, apply_lang_from_args

SOURCE = "blue_me"

_TRACKING_SKIP_KEYS = {"uid", "id", "timeStamp", "trackingType"}
_SUPPLEMENT_KEY = "nahrungsergaenzungsmittel"


def _classify(key: str) -> str:
    """Ordnet ein blue-ME-Feld einer groben Anzeige-Kategorie zu."""
    if key.startswith("achtsamkeit"):
        return "achtsamkeit"
    if key in ("averageBelastungen", "averageSymptome"):
        return "berechnet"
    if key.endswith("Belastungen"):
        return "belastung"
    if key in ("schlaf", "healthSchlafTief", "healthSchlafGesamt", "healthSchlafWach"):
        return "schlaf"
    if key in ("healthSchritte", "behandlungen"):
        return "sonstiges"
    return "symptom"


def _local_to_utc(ts_str: str, tz_name: str) -> tuple[str, str]:
    """Naive lokale Zeitangabe (kein Offset im Export) -> (lokales Datum, UTC-ISO-Timestamp)."""
    dt_local = datetime.fromisoformat(ts_str)
    date = dt_local.date().isoformat()
    dt_utc = dt_local.replace(tzinfo=ZoneInfo(tz_name)).astimezone(ZoneInfo("UTC"))
    return date, dt_utc.isoformat()


def _extend_symptoms(conn) -> None:
    """Fügt ts/notes zu symptoms hinzu, falls die Tabelle aus einer älteren Schema-Version stammt."""
    existing = {row[1] for row in conn.execute("PRAGMA table_info(symptoms)").fetchall()}
    for col, typedef in [("ts", "TEXT"), ("notes", "TEXT")]:
        if col not in existing:
            conn.execute(f"ALTER TABLE symptoms ADD COLUMN {col} {typedef}")


def _insert_symptom(conn, date, symptom, value_num, value_text, category, person, ts) -> bool:
    conn.execute(
        """
        INSERT OR IGNORE INTO symptoms
            (date, symptom, value_num, value_text, category, person, source, ts, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL)
        """,
        (date, symptom, value_num, value_text, category, person, SOURCE, ts),
    )
    return bool(conn.execute("SELECT changes()").fetchone()[0])


def _import_tracking(conn, entries, person, tz_name, result: ImportResult) -> None:
    for e in entries:
        ts_raw = e.get("timeStamp")
        if not ts_raw:
            result.rows_skipped += 1
            continue
        date, ts_utc = _local_to_utc(ts_raw, tz_name)

        for key, value in e.items():
            if key in _TRACKING_SKIP_KEYS:
                continue
            category = _classify(key)

            if key == _SUPPLEMENT_KEY:
                taken = [s for s in (value or []) if s]
                if not taken:
                    continue
                inserted = _insert_symptom(conn, date, key, None, ", ".join(taken), category, person, ts_utc)
            elif isinstance(value, (int, float)):
                inserted = _insert_symptom(conn, date, key, float(value), None, category, person, ts_utc)
            elif isinstance(value, str):
                if not value:
                    continue
                inserted = _insert_symptom(conn, date, key, None, value, category, person, ts_utc)
            else:
                continue

            if inserted:
                result.rows_inserted += 1
            else:
                result.rows_skipped += 1


def _import_activity(conn, entries, person, tz_name, result: ImportResult) -> None:
    for e in entries:
        entry_id = e.get("id")
        ts_raw = e.get("timestamp")
        if not entry_id or not ts_raw:
            result.rows_skipped += 1
            continue
        date, ts_utc = _local_to_utc(ts_raw, tz_name)
        sid = f"blue_me_{entry_id}"

        conn.execute(
            "INSERT OR IGNORE INTO sessions"
            " (id, type, ts_start, date, device_id, person, source_app)"
            " VALUES (?, 'activity', ?, ?, NULL, ?, ?)",
            (sid, ts_utc, date, person, SOURCE),
        )
        if not conn.execute("SELECT changes()").fetchone()[0]:
            result.rows_skipped += 1
            continue
        result.rows_inserted += 1

        metrics = [
            ("duration_min", e.get("duration"), None, "min"),
            ("exertion", e.get("exertion"), None, None),
            ("exertion_type", None, e.get("exertionType"), None),
            ("description", None, e.get("description"), None),
            ("record_type", None, e.get("recordType"), None),
        ]
        for metric, value, value_text, unit in metrics:
            if value is None and not value_text:
                continue
            conn.execute(
                "INSERT OR IGNORE INTO session_metrics"
                " (session_id, metric, value, value_text, unit)"
                " VALUES (?, ?, ?, ?, ?)",
                (sid, metric, value, value_text, unit),
            )


def run(conn, data_path: str | Path, lang: str = "de", person: str | None = None) -> ImportResult:
    """
    Import a blue-ME JSON export into health.db.

    Args:
        conn: Open SQLite connection to health.db
        data_path: Path to blue_me_data_export_*.json
        lang: Display language ('de' or 'en')
        person: Person ID; falls back to OWN_PERSON_ID if None

    Returns:
        ImportResult with rows_inserted / rows_skipped counts
    """
    result = ImportResult(source=SOURCE)
    person_id = resolve_person(person)
    path = Path(data_path)

    if not path.exists():
        result.errors.append(t(f"Datei nicht gefunden: {path}", f"File not found: {path}"))
        return result

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        result.errors.append(str(exc))
        return result

    tracking = data.get("tracking", [])
    activity = data.get("activity", [])
    if not isinstance(tracking, list) or not isinstance(activity, list):
        result.errors.append(t("tracking/activity sind keine Listen", "tracking/activity are not lists"))
        return result

    tz_name = resolve_timezone(conn, person_id)
    _extend_symptoms(conn)

    try:
        _import_tracking(conn, tracking, person_id, tz_name, result)
        _import_activity(conn, activity, person_id, tz_name, result)
    except Exception as exc:
        result.errors.append(str(exc))

    log_import(conn, SOURCE, str(path.name), result.rows_inserted, result.rows_skipped, person=person_id)
    conn.commit()
    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description=t(
            "blue-ME JSON-Export → health.db importieren",
            "Import blue-ME JSON export → health.db",
        )
    )
    add_lang_arg(parser)
    parser.add_argument("file", help=t("Pfad zur JSON-Exportdatei", "Path to JSON export file"))
    parser.add_argument(
        "--person",
        default=None,
        help=t("Person-ID (Standard: OWN_PERSON_ID)", "Person ID (default: OWN_PERSON_ID)"),
    )
    args = parser.parse_args()
    apply_lang_from_args(args)

    conn = open_db()
    try:
        result = run(conn, args.file, lang=args.lang, person=args.person)
        print(t(
            f"{result.rows_inserted} Einträge importiert, {result.rows_skipped} übersprungen",
            f"{result.rows_inserted} entries imported, {result.rows_skipped} skipped",
        ))
        for err in result.errors:
            print(t(f"Fehler: {err}", f"Error: {err}"), file=sys.stderr)
        if result.errors:
            sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
