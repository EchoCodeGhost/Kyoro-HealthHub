#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
CameraHRV → health.db

@tier        infrastructure
@purpose.de  Importiert CSV-Exporte der CameraHRV-App
@purpose.en  Imports CSV exports from CameraHRV app
@method.de   Importiert CSV-Exporte der CameraHRV-App (iOS).
             Datei-Routing:
               All_Features*.csv → camera_hrv_resting (HRV-Session-Aggregate)
                                   + measurements (hrv_rmssd, heart_rate, breathing_rate)
               All_RR*.csv → ppi_raw (Beat-zu-Beat-RR-Intervalle, ms-Praezision)
               All_HR*.csv → measurements (sekundliche heart_rate-Zeitreihe, UTC-Timestamps)
               Standard-Export → camera_hrv_resting
@method.en   Imports CSV exports from CameraHRV app (iOS).
             File routing:
               All_Features*.csv → camera_hrv_resting (HRV session aggregates)
                                   + measurements (hrv_rmssd, heart_rate, breathing_rate)
               All_RR*.csv → ppi_raw (beat-to-beat RR intervals, ms precision)
               All_HR*.csv → measurements (per-second heart_rate time series, UTC timestamps)
               Standard export → camera_hrv_resting
@reads       CSV-Dateien aus imports/camerahRV/
@writes      camera_hrv_resting, measurements, ppi_raw
@limits.de   Abhaengig von CameraHRV App-Exportformat. --person war frueher in
             run() deklariert aber ungenutzt (alle Schreibpfade fest auf
             OWN_PERSON_ID) und in main() gar nicht vorhanden — jetzt in beiden
             Pfaden bis zu allen drei Schreibfunktionen durchgereicht.
             lf_power/hf_power: Einheit ist app-versionsabhaengig, wird
             unveraendert aus der Quelle uebernommen. Verifiziert gegen einen
             echten All_Features.csv-Export: dort tragen LF/HF ueberhaupt
             keine Einheitenangabe in der Kopfzeile, und die Werte sind
             rechnerisch normalisierte Anteile (ihr Verhaeltnis ergibt exakt
             die gemeldete LF/HF-Spalte), keine absolute ms²-Rohleistung wie
             frueher in Spaltennamen/Vorlage behauptet. Andere App-Versionen
             koennten echte ms²-Werte liefern — ohne Einheitenangabe in der
             Quelle ist das nicht unterscheidbar, daher claimt der
             Spaltenname bewusst keine Einheit mehr.

@relevance.de  Ermöglicht den Import von Gesundheitsdaten, essentiell für die umfassende Datenanalyse
@relevance.en  Enables import of health data, essential for comprehensive data analysis
@limits.en   Dependent on CameraHRV app export format. --person used to be
             declared in run() but unused (all write paths hardcoded to
             OWN_PERSON_ID) and absent from main() entirely — now threaded
             through to all three write functions in both paths.
             lf_power/hf_power: unit is app-version-dependent, carried over
             unchanged from the source. Verified against a real
             All_Features.csv export: LF/HF carry no unit label in the
             header at all, and the values are arithmetically normalised
             proportions (their ratio equals the reported LF/HF column
             exactly), not absolute ms² power as the column names/template
             previously claimed. Other app versions might genuinely export
             ms² -- without a unit label in the source this can't be told
             apart, so the column name deliberately no longer claims one.
@usage
    python import_camerahRV.py                    # scannt imports/camerahRV/ (Default)
    python import_camerahRV.py --file export.csv
    python import_camerahRV.py --dir ~/Downloads/camerahRV/
    python import_camerahRV.py --template         # zeigt erwartetes CSV-Format
    python import_camerahRV.py --dry-run
    python import_camerahRV.py --file export.csv --person PER-xxxxxxxx
"""

import argparse
import csv
import io
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from health_config import Config as _Cfg
from modules.base import resolve_person
from modules.db import open_db
from modules.i18n import t, add_lang_arg, apply_lang_from_args

_cfg = _Cfg()
DB_PATH = _cfg.db_path

CSV_TEMPLATE = """\
# CameraHRV Export – Vorlage / Template
# Trennzeichen: Komma oder Semikolon
# Date + Time: separate Spalten ODER kombiniert als "Timestamp" (ISO 8601)
# LF/HF: Einheit ist app-versionsabhängig (ms² power ODER normalisierte
# Anteile, deren Verhältnis der LF/HF-Spalte entspricht) — wird unverändert
# uebernommen, s. @limits.
#
Date,Time,HR (bpm),RMSSD (ms),SDNN (ms),pNN50 (%),LF,HF,LF/HF,Stress Index,Readiness (%)
2026-06-01,09:15:00,68,45.2,38.1,42.3,850.2,1240.5,0.69,35.1,72
"""

# Flexible Spaltennamen-Zuordnung (alle Kleinbuchstaben, Leerzeichen normiert)
FIELD_MAP: dict[str, str] = {
    # Datum / Zeit
    "date":                "date",
    "datum":               "date",
    "time":                "time",
    "uhrzeit":             "time",
    "timestamp":           "timestamp",
    "date time":           "timestamp",
    "datetime":            "timestamp",
    # HR
    "hr":                  "hr_bpm",
    "hr (bpm)":            "hr_bpm",
    "heart rate":          "hr_bpm",
    "heart rate (bpm)":    "hr_bpm",
    "herzfrequenz":        "hr_bpm",
    "herzfrequenz (bpm)":  "hr_bpm",
    # RMSSD
    "rmssd":               "rmssd_ms",
    "rmssd (ms)":          "rmssd_ms",
    "hrv":                 "rmssd_ms",
    "hrv (ms)":            "rmssd_ms",
    # SDNN
    "sdnn":                "sdnn_ms",
    "sdnn (ms)":           "sdnn_ms",
    # Mean RR
    "mean rr":             "mean_rr_ms",
    "mean rr (ms)":        "mean_rr_ms",
    "mittleres rr":        "mean_rr_ms",
    "rr":                  "mean_rr_ms",
    "avnn":                "mean_rr_ms",    # All_Features.csv
    # pNN50
    "pnn50":               "pnn50_pct",
    "pnn50 (%)":           "pnn50_pct",
    "pnn50(%)":            "pnn50_pct",
    # LF (Einheit app-versionsabhängig, s. @limits -- Spaltenname claimt daher
    # keine spezifische Einheit)
    "lf":                  "lf_power",
    "lf (ms²)":            "lf_power",
    "lf (ms2)":            "lf_power",
    "lf power":            "lf_power",
    # HF (dito)
    "hf":                  "hf_power",
    "hf (ms²)":            "hf_power",
    "hf (ms2)":            "hf_power",
    "hf power":            "hf_power",
    # LF/HF
    "lf/hf":               "lf_hf_ratio",
    "lf/hf ratio":         "lf_hf_ratio",
    "lf hf":               "lf_hf_ratio",
    "lf hf ratio":         "lf_hf_ratio",
    "lfhf":                "lf_hf_ratio",   # All_Features.csv
    # Stress
    "stress index":        "stress_index",
    "stress":              "stress_index",
    "stressindex":         "stress_index",
    "si":                  "stress_index",
    # Readiness
    "readiness":           "readiness_pct",
    "readiness (%)":       "readiness_pct",
    "bereitschaft":        "readiness_pct",
    # Messdauer
    "duration":            "measurement_s",
    "duration (s)":        "measurement_s",
    "messdauer":           "measurement_s",
    "messdauer (s)":       "measurement_s",
    # Signalqualität / Atemfrequenz (All_Features.csv)
    "signal quality":      "signal_quality",
    "signalqualität":      "signal_quality",
    "breathing rate":      "breathing_rate",
    "atemfrequenz":        "breathing_rate",
    "resp rate":           "breathing_rate",
}


def _norm(name: str) -> str:
    return re.sub(r"[\s_\-]+", " ", name.strip().lower())


def _to_float(val: str | None) -> float | None:
    if val is None:
        return None
    s = val.strip().replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def _to_iso(date_str: str, time_str: str | None = None) -> str | None:
    """Kombiniert Datum + (optionale) Uhrzeit zu ISO-8601-String."""
    date_str = date_str.strip()
    # Bereits ISO kombiniert? (mit oder ohne Timezone)
    if "T" in date_str or (len(date_str) > 10 and " " in date_str):
        # "2026-06-22 23:34:20 +0000" → erster Leerzeichen-Ersatz, Timezone abschneiden
        candidate = re.sub(r"\s+[+-]\d{2}:?\d{2}$", "", date_str)  # Timezone entfernen
        candidate = candidate.replace(" ", "T", 1)                   # erstes Leerzeichen → T
        try:
            dt = datetime.fromisoformat(candidate)
            return dt.strftime("%Y-%m-%dT%H:%M:%S")
        except ValueError:
            pass
    # DD.MM.YYYY
    m = re.match(r"(\d{1,2})\.(\d{2})\.(\d{4})", date_str)
    if m:
        d, mo, y = m.groups()
        date_str = f"{y}-{mo}-{d.zfill(2)}"
    # MM/DD/YYYY
    m = re.match(r"(\d{1,2})/(\d{2})/(\d{4})", date_str)
    if m:
        mo, d, y = m.groups()
        date_str = f"{y}-{mo.zfill(2)}-{d.zfill(2)}"
    time_part = (time_str or "00:00:00").strip()
    if len(time_part) == 5:
        time_part += ":00"
    try:
        dt = datetime.fromisoformat(f"{date_str}T{time_part}")
        return dt.strftime("%Y-%m-%dT%H:%M:%S")
    except ValueError:
        return None


def _date_from_filename(path: Path) -> str | None:
    m = re.search(r"(\d{4}-\d{2}-\d{2})", path.stem)
    if m:
        return f"{m.group(1)}T00:00:00"
    m = re.search(r"(\d{2})\.(\d{2})\.(\d{4})", path.stem)
    if m:
        d, mo, y = m.groups()
        return f"{y}-{mo}-{d.zfill(2)}T00:00:00"
    return None


def _detect_delimiter(first_line: str) -> str:
    return ";" if first_line.count(";") > first_line.count(",") else ","


def parse_csv(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    lines = [l for l in text.splitlines() if l.strip() and not l.strip().startswith("#")]
    if not lines:
        return []

    delim = _detect_delimiter(lines[0])
    reader = csv.DictReader(io.StringIO("\n".join(lines)), delimiter=delim)

    col_map: dict[str, str] = {}
    records = []

    for raw_row in reader:
        # Spaltenzuordnung beim ersten Datensatz aufbauen
        if not col_map:
            for raw_col in raw_row:
                mapped = FIELD_MAP.get(_norm(raw_col))
                if mapped:
                    col_map[raw_col] = mapped

        row = {mapped: raw_row[raw] for raw, mapped in col_map.items()}

        # Timestamp zusammenbauen — Fallback-Kette: timestamp → date → Dateiname
        dt_str = None
        if "timestamp" in row:
            dt_str = _to_iso(row["timestamp"])
        if not dt_str and "date" in row:
            dt_str = _to_iso(row["date"], row.get("time"))
        if not dt_str:
            dt_str = _date_from_filename(path)

        if not dt_str:
            print(t("  ⚠ Kein Datum für Zeile — übersprungen",
                    "  ⚠ No date for row — skipped"))
            continue

        hr_bpm   = _to_float(row.get("hr_bpm"))
        mean_rr  = _to_float(row.get("mean_rr_ms"))
        if hr_bpm is None and mean_rr:
            hr_bpm = round(60000.0 / mean_rr, 1)

        records.append({
            "datetime":      dt_str,
            "hr_bpm":        hr_bpm,
            "rmssd_ms":      _to_float(row.get("rmssd_ms")),
            "mean_rr_ms":    mean_rr,
            "sdnn_ms":       _to_float(row.get("sdnn_ms")),
            "pnn50_pct":     _to_float(row.get("pnn50_pct")),
            "lf_power":      _to_float(row.get("lf_power")),
            "hf_power":      _to_float(row.get("hf_power")),
            "lf_hf_ratio":   _to_float(row.get("lf_hf_ratio")),
            "stress_index":  _to_float(row.get("stress_index")),
            "readiness_pct": _to_float(row.get("readiness_pct")),
            "measurement_s": _to_float(row.get("measurement_s")),
            "signal_quality": _to_float(row.get("signal_quality")),
            "breathing_rate": _to_float(row.get("breathing_rate")),
        })

    return records


def _ensure_table(conn) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS camera_hrv_resting (
            datetime         TEXT NOT NULL,
            hr_bpm           REAL,
            rmssd_ms         REAL,
            mean_rr_ms       REAL,
            sdnn_ms          REAL,
            pnn50_pct        REAL,
            lf_power         REAL,
            hf_power         REAL,
            lf_hf_ratio      REAL,
            stress_index     REAL,
            readiness_pct    INTEGER,
            measurement_s    INTEGER,
            signal_quality   REAL,
            breathing_rate   REAL,
            person           TEXT NOT NULL DEFAULT 'unknown',
            source_app       TEXT DEFAULT 'camerahRV',
            PRIMARY KEY (datetime, person)
        )
    """)
    # Migration: neue Spalten in bestehende Tabellen einfügen
    for col, typedef in [("signal_quality", "REAL"), ("breathing_rate", "REAL")]:
        try:
            conn.execute(f"ALTER TABLE camera_hrv_resting ADD COLUMN {col} {typedef}")
        except Exception:
            pass
    conn.commit()


def _save(conn, records: list[dict], person: str, dry_run: bool) -> int:
    neu = 0
    for r in records:
        if dry_run:
            print(t(
                f"  [dry] {r['datetime']}  HR={r['hr_bpm']}  RMSSD={r['rmssd_ms']}ms",
                f"  [dry] {r['datetime']}  HR={r['hr_bpm']}  RMSSD={r['rmssd_ms']}ms",
            ))
            neu += 1
            continue

        cur = conn.execute(
            """INSERT OR IGNORE INTO camera_hrv_resting
               (datetime, hr_bpm, rmssd_ms, mean_rr_ms, sdnn_ms, pnn50_pct,
                lf_power, hf_power, lf_hf_ratio, stress_index, readiness_pct,
                measurement_s, signal_quality, breathing_rate, person, source_app)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,'camerahRV')""",
            (
                r["datetime"], r["hr_bpm"], r["rmssd_ms"], r["mean_rr_ms"],
                r["sdnn_ms"], r["pnn50_pct"], r["lf_power"], r["hf_power"],
                r["lf_hf_ratio"], r["stress_index"],
                int(r["readiness_pct"]) if r["readiness_pct"] is not None else None,
                int(r["measurement_s"]) if r["measurement_s"] is not None else None,
                r["signal_quality"], r["breathing_rate"],
                person,
            ),
        )
        if cur.rowcount:
            neu += 1
            # Schlüsselmetriken in measurements spiegeln
            date_part = r["datetime"][:10]
            for metric, val, unit in [
                ("hrv_rmssd",     r["rmssd_ms"],      "ms"),
                ("heart_rate",    r["hr_bpm"],         "bpm"),
                ("breathing_rate", r["breathing_rate"], "breaths/min"),
            ]:
                if val is not None:
                    conn.execute(
                        """INSERT OR IGNORE INTO measurements
                           (ts, date, metric, value, unit, device_id, person, source_app)
                           VALUES (?,?,?,?,?,'camerahRV',?,'camerahRV')""",
                        (r["datetime"], date_part, metric, val, unit, person),
                    )
    conn.commit()
    return neu


def _log_import(conn, path: Path, n: int) -> None:
    conn.execute(
        "INSERT INTO import_log (ts_run, source, data_path, rows_inserted) "
        "VALUES (datetime('now'), 'camerahRV', ?, ?)",
        (str(path), n),
    )
    conn.commit()


def parse_hr_csv(path: Path) -> list[tuple[str, float]]:
    """
    Liest All_HR.csv → [(datetime_utc, hr_bpm)].
    `date`-Spalte enthält direkt den sekundengenauen UTC-Timestamp pro Messung.
    """
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    lines = [l for l in text.replace("\r\n", "\n").replace("\r", "\n").splitlines()
             if l.strip() and not l.strip().startswith("#")]
    if not lines:
        return []

    delim = _detect_delimiter(lines[0])
    reader = csv.DictReader(io.StringIO("\n".join(lines)), delimiter=delim)

    results: list[tuple[str, float]] = []
    for raw_row in reader:
        row = {k.strip().lower(): (v.strip() if v else "") for k, v in raw_row.items() if k}
        date_str = row.get("date", "")
        hr_str   = row.get("heart_rate", "")
        if not date_str or not hr_str:
            continue
        dt_str = _to_iso(date_str)
        if not dt_str:
            continue
        try:
            hr = float(hr_str)
        except ValueError:
            continue
        results.append((dt_str, hr))
    return results


def _save_hr_to_measurements(conn, hr_rows: list[tuple[str, float]], person: str, dry_run: bool) -> int:
    """Schreibt sekündliche HR-Werte aus All_HR.csv in measurements."""
    neu = 0
    date_part_cache: dict[str, str] = {}
    for dt_str, hr in hr_rows:
        date_part = date_part_cache.setdefault(dt_str[:10], dt_str[:10])
        if dry_run:
            print(f"  [dry-hr] {dt_str}  HR={hr:.0f} bpm")
            neu += 1
            continue
        cur = conn.execute(
            """INSERT OR IGNORE INTO measurements
               (ts, date, metric, value, unit, device_id, person, source_app)
               VALUES (?, ?, 'heart_rate', ?, 'bpm', 'camerahRV', ?, 'camerahRV')""",
            (dt_str, date_part, hr, person),
        )
        if cur.rowcount:
            neu += 1
    conn.commit()
    return neu


def _is_rr_file(path: Path) -> bool:
    return path.name.lower().startswith("all_rr")


def _is_hr_timeseries_file(path: Path) -> bool:
    return path.name.lower().startswith("all_hr")


def parse_rr_csv(path: Path) -> list[tuple[str, int]]:
    """
    Liest All_RR.csv → [(datetime_ms_precision, rr_ms)].

    Eine Datei kann mehrere Recordings enthalten (Spalte `recording_name`).
    `since_start` ist kumulativ in ms ab Recording-Start pro Gruppe.
    Recording-Start pro Gruppe = erste_date_dt - erste_since_ms.
    `date` enthält den UTC-Datetime des 10-Sekunden-Fensters ("2026-06-22 23:33:40 +0000").
    """
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    lines = [l for l in text.replace("\r\n", "\n").replace("\r", "\n").splitlines()
             if l.strip() and not l.strip().startswith("#")]
    if not lines:
        return []

    delim = _detect_delimiter(lines[0])
    reader = csv.DictReader(io.StringIO("\n".join(lines)), delimiter=delim)

    # Zeilen nach recording_name gruppieren (Reihenfolge erhalten)
    groups: dict[str, list[tuple[str, int, int]]] = {}
    for raw_row in reader:
        row = {k.strip().lower(): (v.strip() if v else "") for k, v in raw_row.items() if k}
        rec_name     = row.get("recording_name", "__single__")
        date_str     = row.get("date", "")
        since_ms_str = row.get("since_start", "")
        rr_str       = row.get("rr", "")
        if not date_str or not since_ms_str or not rr_str:
            continue
        try:
            rr_ms    = int(float(rr_str))
            since_ms = int(float(since_ms_str))
        except ValueError:
            continue
        groups.setdefault(rec_name, []).append((date_str, since_ms, rr_ms))

    def _parse_utc(s: str) -> datetime | None:
        candidate = re.sub(r"\s+[+-]\d{2}:?\d{2}$", "", s).replace(" ", "T", 1)
        try:
            return datetime.fromisoformat(candidate).replace(tzinfo=timezone.utc)
        except ValueError:
            return None

    results: list[tuple[str, int]] = []
    for rows_raw in groups.values():
        first_date_str, first_since_ms, _ = rows_raw[0]
        first_dt = _parse_utc(first_date_str)
        if first_dt is None:
            continue
        recording_start = first_dt - timedelta(milliseconds=first_since_ms)
        for _, since_ms, rr_ms in rows_raw:
            beat_dt  = recording_start + timedelta(milliseconds=since_ms)
            ms_part  = beat_dt.microsecond // 1000
            beat_str = beat_dt.strftime("%Y-%m-%dT%H:%M:%S") + f".{ms_part:03d}"
            results.append((beat_str, rr_ms))

    return results


def _save_rr(conn, rr_rows: list[tuple[str, int]], person: str, dry_run: bool) -> int:
    """Schreibt beat-to-beat RR-Intervalle in ppi_raw."""
    neu = 0
    for dt_str, rr_ms in rr_rows:
        if dry_run:
            print(f"  [dry-rr] {dt_str}  RR={rr_ms}ms")
            neu += 1
            continue
        cur = conn.execute(
            "INSERT OR IGNORE INTO ppi_raw (datetime, pulse_ms, device, source, person) "
            "VALUES (?, ?, 'camerahRV', 'camerahRV', ?)",
            (dt_str, rr_ms, person),
        )
        if cur.rowcount:
            neu += 1
    conn.commit()
    return neu


def run(conn, _data_path=None, lang: str = "de", person: str | None = None):
    """Modul-Interface für import_all.py."""
    from modules.base import ImportResult
    apply_lang_from_args(type("A", (), {"lang": lang})())
    person = resolve_person(person)
    _ensure_table(conn)
    result = ImportResult(source="camerahRV")

    d = _cfg.camerahRV_dir
    csv_files = sorted(d.glob("*.csv")) + sorted(d.glob("*.CSV"))

    for p in csv_files:
        if _is_rr_file(p):
            rr_rows = parse_rr_csv(p)
            n = _save_rr(conn, rr_rows, person, dry_run=False)
            result.rows_inserted += n
            _log_import(conn, p, n)
        elif _is_hr_timeseries_file(p):
            hr_rows = parse_hr_csv(p)
            n = _save_hr_to_measurements(conn, hr_rows, person, dry_run=False)
            result.rows_inserted += n
            _log_import(conn, p, n)
        else:
            records = parse_csv(p)
            n = _save(conn, records, person, dry_run=False)
            result.rows_inserted += n
            if n:
                _log_import(conn, p, n)

    return result


def main():
    parser = argparse.ArgumentParser(
        description=t("CameraHRV CSV-Export importieren", "Import CameraHRV CSV export"))
    group = parser.add_mutually_exclusive_group(required=False)
    group.add_argument("--file", metavar="CSV",
                       help=t("Einzelne CSV-Datei", "Single CSV file"))
    group.add_argument("--dir", metavar="ORDNER",
                       help=t("Ordner mit CSV-Dateien (Default: imports/camerahRV/)",
                              "Folder with CSV files (default: imports/camerahRV/)"))
    group.add_argument("--template", action="store_true",
                       help=t("Erwartetes CSV-Format ausgeben", "Print expected CSV format"))
    parser.add_argument("--update", action="store_true",
                        help=t("Nur neue Daten (INSERT OR IGNORE)", "Only new data (INSERT OR IGNORE)"))
    parser.add_argument("--dry-run", action="store_true",
                        help=t("Vorschau ohne DB-Schreibzugriff", "Preview without DB writes"))
    parser.add_argument("--person", default=None, metavar="PERSON_ID",
                        help=t("Person-ID (Standard: eigene Person aus Config)",
                               "Person ID (default: own person from config)"))
    add_lang_arg(parser)

    args = parser.parse_args()
    apply_lang_from_args(args)
    person = resolve_person(args.person)

    if args.template:
        print(CSV_TEMPLATE)
        return

    conn = open_db()
    _ensure_table(conn)

    if args.file:
        csv_files = [Path(args.file)]
    else:
        d = Path(args.dir) if args.dir else _cfg.camerahRV_dir
        csv_files = sorted(d.glob("*.csv")) + sorted(d.glob("*.CSV"))
        print(t(f"Ordner: {d}  |  Gefundene CSVs: {len(csv_files)}",
                f"Folder: {d}  |  CSVs found: {len(csv_files)}"))

    total_new = 0
    for p in csv_files:
        print(t(f"\n→ {p.name}", f"\n→ {p.name}"))

        if _is_rr_file(p):
            rr_rows = parse_rr_csv(p)
            if not rr_rows:
                print(t("  Keine RR-Intervalle gefunden.", "  No RR intervals found."))
                continue
            print(t(f"  {len(rr_rows)} RR-Intervall(e) geparst → ppi_raw",
                    f"  {len(rr_rows)} RR interval(s) parsed → ppi_raw"))
            n = _save_rr(conn, rr_rows, person, args.dry_run)
            if not args.dry_run:
                _log_import(conn, p, n)
            print(t(f"  → {n} neu importiert", f"  → {n} newly imported"))
            total_new += n
            continue

        if _is_hr_timeseries_file(p):
            hr_rows = parse_hr_csv(p)
            if not hr_rows:
                print(t("  Keine HR-Werte gefunden.", "  No HR values found."))
                continue
            print(t(f"  {len(hr_rows)} sekündliche HR-Werte geparst → measurements",
                    f"  {len(hr_rows)} per-second HR values parsed → measurements"))
            n = _save_hr_to_measurements(conn, hr_rows, person, args.dry_run)
            if not args.dry_run:
                _log_import(conn, p, n)
            print(t(f"  → {n} neu importiert", f"  → {n} newly imported"))
            total_new += n
            continue

        # Normaler HRV-Session-Pfad (All_Features*.csv, Standard-Export)
        records = parse_csv(p)
        if not records:
            print(t("  Keine verwertbaren Zeilen gefunden.", "  No usable rows found."))
            continue
        print(t(f"  {len(records)} Messung(en) geparst", f"  {len(records)} measurement(s) parsed"))
        n = _save(conn, records, person, args.dry_run)
        if not args.dry_run:
            _log_import(conn, p, n)
        print(t(f"  → {n} neu importiert", f"  → {n} newly imported"))
        total_new += n

    conn.close()

    if args.dry_run:
        print(t(f"\nDRY-RUN: {total_new} Einträge würden importiert.",
                f"\nDRY-RUN: {total_new} entries would be imported."))
    else:
        print(t(f"\nGesamt: {total_new} neue Einträge importiert.",
                f"\nTotal: {total_new} new entries imported."))
        if total_new > 0:
            print(t("Verlauf: python analyse/analyse_hrv_multisource.py --plot",
                    "History: python analyse/analyse_hrv_multisource.py --plot"))


if __name__ == "__main__":
    main()
