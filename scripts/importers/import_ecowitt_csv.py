#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Ecowitt CSV-Importer — verarbeitet CSV-Exporte der Ecowitt-App / ecowitt.net

@tier        infrastructure
@purpose.de  Importiert Ecowitt Wetterdaten aus CSV-Exporten
@purpose.en  Imports Ecowitt weather data from CSV exports
@method.de   Verarbeitet CSV-Exporte der Ecowitt-App oder ecowitt.net.
             Vorteile gegenüber Home Assistant Statistics:
             - Stundenwerte oder Minutenwerte statt nur Tages-Aggregate
             - Erlaubt echte Berechnung der Sonnenstunden (solar > SUNSHINE_THRESHOLD W/m2)
             CSV-Format: Spaltentrennzeichen Komma oder Semikolon,
             Zeitstempel in erster Spalte, Einheiten in Spaltenkoepfen oder als separate Zeile.
@method.en   Processes CSV exports from Ecowitt app or ecowitt.net.
             Advantages over Home Assistant Statistics:
             - Hourly or minute values instead of daily aggregates only
             - Allows real calculation of sunshine hours (solar > SUNSHINE_THRESHOLD W/m2)
             CSV format: delimiter comma or semicolon,
             timestamp in first column, units in column headers or as separate line.
@reads       CSV-Dateien (Ecowitt Export)
@writes      weather_ecowitt
@limits.de   Abhaengig von Ecowitt CSV-Exportformat.

@relevance.de  Ermöglicht den Import von Gesundheitsdaten, essentiell für die umfassende Datenanalyse
@relevance.en  Enables import of health data, essential for comprehensive data analysis
@limits.en   Dependent on Ecowitt CSV export format.
@usage
    python importers/import_ecowitt_csv.py /pfad/zur/datei.csv
    python importers/import_ecowitt_csv.py /pfad/zur/datei.csv --dry-run
"""

import argparse
import csv
import io
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from health_config import Config as _Cfg
from modules.db import open_db
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from modules.base import log_import, resolve_person

_cfg = _Cfg()

# Solar radiation threshold for "sunshine" (WMO definition: direct irradiance > 120 W/m²)
SUNSHINE_THRESHOLD_WM2 = 120.0

# ── Column name aliases (Ecowitt uses various names across firmware/regions) ──

_COL_ALIASES: dict[str, list[str]] = {
    "datetime":     ["time", "date", "datetime", "datum", "timestamp",
                     "date/time", "date time"],
    "solar_wm2":    ["solar radiation(w/m²)", "solar radiation(w/m2)",
                     "solar radiation", "solarstrahlung", "solar",
                     "global radiation", "globalstrahlung",
                     "lux(lx)", "illuminance"],          # lux fallback (÷120)
    "uv_index":     ["uv index", "uv-index", "uv", "uvi"],
    "temp_out":     ["outdoor temperature(°c)", "outdoor temperature",
                     "außentemperatur", "temp outside", "temperature",
                     "outdoor temp"],
    "humidity_out": ["outdoor humidity(%)", "outdoor humidity",
                     "außenluftfeuchtigkeit", "humidity outside", "humidity",
                     "outdoor humi"],
    "pressure":     ["relative pressure(hpa)", "relative pressure",
                     "luftdruck", "pressure", "barometer"],
    "wind_speed":   ["wind speed(km/h)", "wind speed", "windgeschwindigkeit",
                     "wind"],
    "wind_gust":    ["wind gust(km/h)", "wind gust", "windböe", "gust"],
    "wind_dir":     ["wind direction", "windrichtung", "wind dir"],
    "rain_rate":    ["rain rate(mm/hr)", "rain rate", "regenrate"],
    "rain_daily":   ["daily rain(mm)", "daily rain", "tagesregen"],
    "dewpoint":     ["dew point(°c)", "dew point", "taupunkt"],
    "feels_like":   ["feels like(°c)", "feels like", "gefühlte temperatur"],
    "temp_in":      ["indoor temperature(°c)", "indoor temperature",
                     "innentemperatur"],
    "humidity_in":  ["indoor humidity(%)", "indoor humidity",
                     "innenluftfeuchtigkeit"],
}


def _map_columns(header: list[str]) -> dict[str, int]:
    """Map standardised field names → column indices, case-insensitive."""
    h = [c.lower().strip() for c in header]
    mapping: dict[str, int] = {}
    for field, aliases in _COL_ALIASES.items():
        for alias in aliases:
            try:
                idx = h.index(alias.lower())
                mapping[field] = idx
                break
            except ValueError:
                continue
    return mapping


def _parse_ts(raw: str) -> datetime | None:
    """Parse timestamp strings in various Ecowitt formats."""
    raw = raw.strip()
    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%d.%m.%Y %H:%M:%S",
        "%d.%m.%Y %H:%M",
        "%Y/%m/%d %H:%M:%S",
        "%Y/%m/%d %H:%M",
        "%m/%d/%Y %H:%M:%S",
        "%m/%d/%Y %H:%M",
    ):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None


def _f(val: str | None) -> float | None:
    if val is None:
        return None
    val = val.strip().replace(",", ".")
    if val in ("", "--", "-", "N/A", "n/a"):
        return None
    try:
        return float(val)
    except ValueError:
        return None


def parse_csv(path: Path) -> list[dict]:
    """Parse an Ecowitt CSV file into a list of row dicts with normalised keys."""
    raw = path.read_bytes()
    # Detect encoding
    for enc in ("utf-8-sig", "utf-8", "latin-1", "cp1252"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        text = raw.decode("latin-1", errors="replace")

    # Detect delimiter
    sample = text[:4096]
    delim = ";" if sample.count(";") > sample.count(",") else ","

    reader = csv.reader(io.StringIO(text), delimiter=delim)
    rows_raw = list(reader)

    # Skip leading comment lines (#) and find header
    header_idx = 0
    for i, row in enumerate(rows_raw):
        if row and not row[0].strip().startswith("#"):
            header_idx = i
            break

    header = rows_raw[header_idx]
    col_map = _map_columns(header)

    if "datetime" not in col_map:
        raise ValueError(t(f"Keine Zeitstempel-Spalte in {path.name} erkannt.",
                           f"No timestamp column found in {path.name}."))

    rows: list[dict] = []
    for raw_row in rows_raw[header_idx + 1:]:
        if not raw_row or not raw_row[0].strip():
            continue
        ts = _parse_ts(raw_row[col_map["datetime"]])
        if ts is None:
            continue

        def g(field: str) -> float | None:
            idx = col_map.get(field)
            if idx is None or idx >= len(raw_row):
                return None
            return _f(raw_row[idx])

        solar = g("solar_wm2")
        # Lux fallback: ~120 lx ≈ 1 W/m² (rough but acceptable)
        if solar is None and "solar_wm2" in col_map:
            lux = g("solar_wm2")   # already mapped from lux alias
            solar = round(lux / 120.0, 1) if lux is not None else None

        rows.append({
            "ts":           ts,
            "date":         ts.strftime("%Y-%m-%d"),
            "solar_wm2":    solar,
            "uv_index":     g("uv_index"),
            "temp_out":     g("temp_out"),
            "humidity_out": g("humidity_out"),
            "pressure":     g("pressure"),
            "wind_speed":   g("wind_speed"),
            "wind_gust":    g("wind_gust"),
            "wind_dir":     g("wind_dir"),
            "rain_rate":    g("rain_rate"),
            "rain_daily":   g("rain_daily"),
            "dewpoint":     g("dewpoint"),
            "feels_like":   g("feels_like"),
            "temp_in":      g("temp_in"),
            "humidity_in":  g("humidity_in"),
        })
    return rows


def aggregate_daily(rows: list[dict]) -> list[dict]:
    """Aggregate per-row (hourly/minutely) data to daily summaries."""
    by_date: dict[str, list[dict]] = {}
    for r in rows:
        by_date.setdefault(r["date"], []).append(r)

    daily = []
    for date, day_rows in sorted(by_date.items()):
        def agg_max(field: str) -> float | None:
            vals = [r[field] for r in day_rows if r[field] is not None]
            return max(vals) if vals else None

        def agg_mean(field: str) -> float | None:
            vals = [r[field] for r in day_rows if r[field] is not None]
            return round(sum(vals) / len(vals), 2) if vals else None

        def agg_min(field: str) -> float | None:
            vals = [r[field] for r in day_rows if r[field] is not None]
            return min(vals) if vals else None

        # Sunshine hours: count intervals where solar > threshold
        # Detect interval length in minutes from timestamps
        ts_list = sorted(r["ts"] for r in day_rows)
        if len(ts_list) >= 2:
            deltas = [(ts_list[i+1] - ts_list[i]).seconds / 60
                      for i in range(min(5, len(ts_list)-1))]
            interval_min = max(1, round(sum(deltas) / len(deltas)))
        else:
            interval_min = 60

        sunshine_intervals = sum(
            1 for r in day_rows
            if r["solar_wm2"] is not None and r["solar_wm2"] >= SUNSHINE_THRESHOLD_WM2
        )
        sunshine_h = round(sunshine_intervals * interval_min / 60, 2)

        daily.append({
            "date":           date,
            "uv_index_max":   agg_max("uv_index"),
            "solar_wm2_max":  agg_max("solar_wm2"),
            "solar_wm2_mean": agg_mean("solar_wm2"),
            "sunshine_h":     sunshine_h if sunshine_h > 0 else None,
            "temp_out_c":     agg_mean("temp_out"),
            "temp_out_min":   agg_min("temp_out"),
            "temp_out_max":   agg_max("temp_out"),
            "humidity_out":   agg_mean("humidity_out"),
            "pressure_hpa":   agg_mean("pressure"),
            "wind_speed_kmh": agg_mean("wind_speed"),
            "wind_gust_max":  agg_max("wind_gust"),
            "wind_dir_deg":   agg_mean("wind_dir"),
            "rain_daily_mm":  agg_max("rain_daily"),   # cumulative → max = total
            "rain_rate_max":  agg_max("rain_rate"),
            "dewpoint_c":     agg_mean("dewpoint"),
            "feels_like_c":   agg_mean("feels_like"),
            "temp_in_c":      agg_mean("temp_in"),
            "humidity_in":    agg_mean("humidity_in"),
            "n_rows":         len(day_rows),
        })
    return daily


def _ensure_columns(conn: sqlite3.Connection) -> None:
    """Add columns to weather_station that the CSV importer provides."""
    existing = {r[1] for r in conn.execute("PRAGMA table_info(weather_station)")}
    extra_cols = [
        ("sunshine_h",      "REAL"),   # Sonnenstunden aus Ecowitt CSV
        ("solar_wm2_mean",  "REAL"),   # Tagesmittel Solarstrahlung W/m²
    ]
    for col, typedef in extra_cols:
        if col not in existing:
            conn.execute(f"ALTER TABLE weather_station ADD COLUMN {col} {typedef}")
    conn.commit()


def import_to_db(conn: sqlite3.Connection, daily: list[dict],
                 lat: float | None = None, lon: float | None = None,
                 person: str | None = None) -> int:
    _person = resolve_person(person)
    _ensure_columns(conn)
    cfg_lat = lat or _cfg.home_lat
    cfg_lon = lon or _cfg.home_lon

    rows = [(
        d["date"],
        "home", cfg_lat, cfg_lon,
        d["temp_out_c"], d["temp_out_min"], d["temp_out_max"],
        d["humidity_out"], d["temp_in_c"], d["humidity_in"],
        d["pressure_hpa"], None, None,
        d["wind_speed_kmh"], d["wind_gust_max"], d["wind_dir_deg"],
        d["rain_daily_mm"], d["rain_rate_max"],
        d["uv_index_max"], d["solar_wm2_max"],
        d["dewpoint_c"], d["feels_like_c"],
        d["sunshine_h"], d["solar_wm2_mean"],
        _person,
    ) for d in daily]

    conn.executemany("""
        INSERT OR IGNORE INTO weather_station
        (date, location, lat, lon,
         temp_out_c, temp_out_min, temp_out_max,
         humidity_out, temp_in_c, humidity_in,
         pressure_hpa, pressure_min, pressure_max,
         wind_speed_kmh, wind_gust_max, wind_dir_deg,
         rain_mm, rain_rate_max, uv_index_max, solar_wm2_max,
         dewpoint_c, feels_like_c,
         sunshine_h, solar_wm2_mean,
         person, source)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,'ecowitt_csv')
    """, rows)
    log_import(conn, 'ecowitt_csv', '', len(rows), person=_person)
    conn.commit()
    return len(rows)


def main():
    parser = argparse.ArgumentParser(
        description=t("Ecowitt CSV → health DB (weather_station)",
                      "Ecowitt CSV → health DB (weather_station)")
    )
    parser.add_argument("csv_file", help=t("Ecowitt CSV-Export", "Ecowitt CSV export"))
    parser.add_argument("--dry-run", action="store_true",
                        help=t("Nur parsen, nicht importieren", "Parse only, do not import"))
    parser.add_argument("--db", default=None, help=t("Pfad zur health DB", "Path to health DB"))
    parser.add_argument("--person", default=None, help="Ziel-Person (Default: OWN_PERSON_ID)")
    add_lang_arg(parser)
    args = parser.parse_args()
    apply_lang_from_args(args)

    path = Path(args.csv_file)
    if not path.exists():
        print(t(f"Datei nicht gefunden: {path}", f"File not found: {path}"), file=sys.stderr)
        sys.exit(1)

    print(t(f"Lese {path.name} ...", f"Reading {path.name} ..."))
    rows = parse_csv(path)
    print(t(f"  {len(rows)} Zeilen gelesen", f"  {len(rows)} rows read"))

    daily = aggregate_daily(rows)
    print(t(f"  {len(daily)} Tage aggregiert\n", f"  {len(daily)} days aggregated\n"))

    for d in daily:
        sh = f"{d['sunshine_h']:.1f}h" if d['sunshine_h'] else "–"
        uv = f"UV {d['uv_index_max']:.0f}" if d['uv_index_max'] else "–"
        sol = f"Sol {d['solar_wm2_max']:.0f} W/m²" if d['solar_wm2_max'] else "–"
        print(t(f"  {d['date']}  Sonne: {sh:>6}  {uv:>5}  {sol}  ({d['n_rows']} Zeilen)",
                f"  {d['date']}  Sun: {sh:>6}  {uv:>5}  {sol}  ({d['n_rows']} rows)"))

    if args.dry_run:
        print(t("\n--dry-run: kein Import.", "\n--dry-run: no import."))
        return

    db_path = args.db or str(_cfg.db_path)
    conn = open_db(db_path)
    n = import_to_db(conn, daily, person=args.person)
    conn.close()
    print(t(f"\n✓ {n} Tage in weather_station importiert (source=ecowitt_csv)",
            f"\n✓ {n} days imported into weather_station (source=ecowitt_csv)"))


if __name__ == "__main__":
    main()
