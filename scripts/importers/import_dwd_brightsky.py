#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
DWD Stationsdaten via Brightsky API → weather_dwd_station

@tier        infrastructure
@purpose.de  Importiert DWD-Stationsdaten via Brightsky API
@purpose.en  Imports DWD station data via Brightsky API
@method.de   Brightsky (https://api.brightsky.dev) ist ein kostenloses JSON-Frontend
             fuer DWD-Stationsdaten. Kein API-Key, keine Registrierung noetig.
             Stationsauswahl erfolgt automatisch anhand von Koordinaten.
             Koordinaten kommen aus fetch_daily.py (Config oder Travel-Log).
@method.en   Brightsky (https://api.brightsky.dev) is a free JSON frontend
             for DWD station data. No API key, no registration required.
             Station selection is automatic based on coordinates.
             Coordinates come from fetch_daily.py (Config or Travel-Log).
@reads       Brightsky API (online)
@writes      weather_dwd_station
@limits.de   Abhaengig von DWD/Brightsky API-Verfuegbarkeit.

@relevance.de  Ermöglicht den Import von Gesundheitsdaten, essentiell für die umfassende Datenanalyse
@relevance.en  Enables import of health data, essential for comprehensive data analysis
@limits.en   Dependent on DWD/Brightsky API availability.
@usage
    python3 import_dwd_brightsky.py
    python3 import_dwd_brightsky.py --date 2026-01-01
"""

import argparse
import json
import sqlite3
import urllib.request
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from health_config import Config as _Cfg
from modules.db import open_db
from utils.anonymize import round_coords
from modules.base import ImportResult, log_import
from modules.i18n import t, add_lang_arg, apply_lang_from_args

_cfg = _Cfg()

BRIGHTSKY_URL = "https://api.brightsky.dev/weather"

# Brightsky liefert Stundenwerte. Eine Anfrage über die volle Historie
# (2020→heute = ~57.000 Stunden) läuft in den Timeout, während 90 Tage in ~1,5 s
# beantwortet werden. Gleiche Chunk-Größe wie import_airquality.py.
CHUNK_DAYS = 90


def _fetch_window(lat: float, lon: float, date_from: str, date_to: str) -> dict | None:
    url = (f"{BRIGHTSKY_URL}?lat={lat}&lon={lon}"
           f"&date={date_from}T00%3A00%3A00"
           f"&last_date={date_to}T23%3A59%3A59")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Kyoro-HealthHub/1.0"})
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read())
    except Exception as exc:
        # Nicht stumm schlucken: ein Timeout wegen zu großer Spanne sah vorher
        # exakt aus wie "API nicht erreichbar" und führte die Diagnose in die Irre.
        print(t(f"  Brightsky {date_from}→{date_to} fehlgeschlagen: {type(exc).__name__}: {exc}",
                f"  Brightsky {date_from}→{date_to} failed: {type(exc).__name__}: {exc}"))
        return None


def fetch_brightsky(lat: float, lon: float, date_from: str, date_to: str) -> dict | None:
    """Holt den Zeitraum in CHUNK_DAYS-Fenstern und fügt die Antworten zusammen.

    Rückgabe hat dieselbe Form wie eine einzelne API-Antwort ({sources, weather}),
    damit import_brightsky_from_raw() unverändert damit arbeiten kann.
    Teil-Erfolg zählt: schlägt ein Fenster fehl, werden die übrigen trotzdem
    geliefert; None nur, wenn kein einziges Fenster durchkam.
    """
    lat, lon = round_coords(lat, lon)
    start, end = date.fromisoformat(date_from), date.fromisoformat(date_to)

    merged: dict = {"sources": [], "weather": []}
    ok = False
    cur = start
    while cur <= end:
        stop = min(cur + timedelta(days=CHUNK_DAYS - 1), end)
        data = _fetch_window(lat, lon, cur.isoformat(), stop.isoformat())
        if data:
            ok = True
            if not merged["sources"]:
                merged["sources"] = data.get("sources", [])
            merged["weather"].extend(data.get("weather", []))
        cur = stop + timedelta(days=1)

    return merged if ok else None


def import_brightsky_from_raw(conn: sqlite3.Connection, data: dict) -> int:
    from importers.import_aemet import _setup_table
    _setup_table(conn)

    sources      = data.get("sources", [])
    station_id   = sources[0].get("dwd_station_id", "") if sources else ""
    station_name = sources[0].get("station_name", "") if sources else ""

    by_date: dict[str, list] = defaultdict(list)
    for h in data.get("weather", []):
        ts = h.get("timestamp", "")
        if ts:
            by_date[ts[:10]].append(h)

    def _vals(hours, key):
        return [h[key] for h in hours if h.get(key) is not None]

    def _mean(v):
        return round(sum(v) / len(v), 2) if v else None

    def _sum(v):
        return round(sum(v), 2) if v else None

    rows = []
    for day, hours in sorted(by_date.items()):
        # Brightsky gibt wind in m/s → km/h umrechnen
        def _kmh(v):
            return [round(x * 3.6, 1) for x in v]

        temps      = _vals(hours, "temperature")
        humidity   = _vals(hours, "relative_humidity")
        dewpoint   = _vals(hours, "dew_point")
        pressure   = _vals(hours, "pressure_msl")
        wind_ms    = _vals(hours, "wind_speed")
        gust_ms    = _vals(hours, "wind_gust_speed")
        wind_dir   = _vals(hours, "wind_direction")
        precip     = _vals(hours, "precipitation")
        sunshine_s = _vals(hours, "sunshine")
        cloud      = _vals(hours, "cloud_cover")
        solar      = _vals(hours, "solar")

        wind_kmh = _kmh(wind_ms)
        gust_kmh = _kmh(gust_ms)

        sunshine_sum = _sum(sunshine_s)
        sunshine_h   = round(sunshine_sum / 3600, 2) if sunshine_sum is not None else None

        rows.append((
            day, station_id, station_name,
            None,                              # uv_index (nicht in Brightsky)
            max(solar) if solar else None,     # solar_wm2 (Peak)
            _mean(solar),                      # solar_wm2_mean
            sunshine_h,
            _mean(cloud),                      # cloud_pct
            _mean(temps),                      # temp_c
            min(temps) if temps else None,     # temp_min
            max(temps) if temps else None,     # temp_max
            _mean(dewpoint),                   # dewpoint_c
            _mean(humidity),                   # humidity
            min(humidity) if humidity else None,  # humidity_min
            max(humidity) if humidity else None,  # humidity_max
            _mean(pressure),                   # pressure_hpa
            min(pressure) if pressure else None,  # pressure_min
            max(pressure) if pressure else None,  # pressure_max
            _mean(wind_kmh),                   # wind_speed_kmh
            max(gust_kmh) if gust_kmh else None,  # wind_gust_max
            _mean(wind_dir),                   # wind_dir_deg
            _sum(precip),                      # rain_mm
            None,                              # snow_cm (nicht in Brightsky)
            None,                              # evap_mm (nicht in Brightsky)
        ))

    conn.executemany("""
        INSERT OR IGNORE INTO weather_dwd_station
        (date, station_id, station_name,
         uv_index, solar_wm2, solar_wm2_mean, sunshine_h, cloud_pct,
         temp_c, temp_min, temp_max, dewpoint_c,
         humidity, humidity_min, humidity_max,
         pressure_hpa, pressure_min, pressure_max,
         wind_speed_kmh, wind_gust_max, wind_dir_deg,
         rain_mm, snow_cm, evap_mm,
         source)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,'brightsky')
    """, rows)
    log_import(conn, 'dwd_brightsky', '', len(rows))
    conn.commit()
    return len(rows)


def _last_date(conn: sqlite3.Connection) -> str | None:
    row = conn.execute(
        "SELECT MAX(date) FROM weather_dwd_station WHERE source='brightsky'"
    ).fetchone()
    return row[0] if row and row[0] else None


# Ab wann Wetter überhaupt sinnvoll ist: ab dem ersten Tag mit Gesundheitsdaten.
# Ein fester Boden (früher: 2020-01-01) schneidet still Jahre ab — und weil der
# Importer danach nur noch ab MAX(date)+1 nachlädt, also ausschließlich vorwärts,
# wird ein zu spät gesetzter Boden NIE wieder aufgeholt. Brightsky liefert DWD-
# Historie mindestens zurück bis 2010.
_FALLBACK_START = "2020-01-01"


def _default_start(conn: sqlite3.Connection) -> str:
    row = conn.execute("SELECT MIN(date) FROM measurements").fetchone()
    return row[0] if row and row[0] else _FALLBACK_START


def run(conn: sqlite3.Connection, _data_path=None,
        lang: str = "de", person=None) -> ImportResult:
    apply_lang_from_args(type("A", (), {"lang": lang})())
    result = ImportResult(source="dwd_brightsky")

    lat = _cfg.home_lat
    lon = _cfg.home_lon
    if lat is None or lon is None:
        print(t("DWD Brightsky: kein Standort in Config (location.lat/lon) — übersprungen",
                "DWD Brightsky: no location in config (location.lat/lon) — skipped"))
        return result

    last = _last_date(conn)
    date_from = (
        (date.fromisoformat(last) + timedelta(days=1)).isoformat()
        if last else _default_start(conn)
    )
    date_to = date.today().isoformat()

    if date_from > date_to:
        return result

    data = fetch_brightsky(lat, lon, date_from, date_to)
    if data is None:
        print(t("DWD Brightsky: API nicht erreichbar.", "DWD Brightsky: API not reachable."))
        return result

    n = import_brightsky_from_raw(conn, data)
    result.rows_inserted = n
    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description=t("DWD Wetterdaten via Brightsky API importieren",
                      "Import DWD weather data via Brightsky API"))
    parser.add_argument("--from", dest="date_from", metavar="YYYY-MM-DD",
                        help=t("Startdatum", "Start date"))
    parser.add_argument("--to", dest="date_to", metavar="YYYY-MM-DD",
                        help=t("Enddatum (default: heute)", "End date (default: today)"))
    parser.add_argument("--update", action="store_true",
                        help=t("Nur neue Daten ab letztem Import", "Only new data since last import"))
    add_lang_arg(parser)
    args = parser.parse_args()
    apply_lang_from_args(args)

    lat = _cfg.home_lat
    lon = _cfg.home_lon
    if lat is None or lon is None:
        print(t("Kein Standort in Config (location.lat/lon) — Abbruch.",
                "No location in config (location.lat/lon) — aborting."))
        sys.exit(1)

    conn = open_db()

    date_to = args.date_to or date.today().isoformat()
    if args.update or not args.date_from:
        last = _last_date(conn)
        date_from = (
            (date.fromisoformat(last) + timedelta(days=1)).isoformat()
            if last else _default_start(conn)
        )
    else:
        date_from = args.date_from

    if date_from > date_to:
        print(t("Daten bereits aktuell.", "Data already up to date."))
        conn.close()
        return

    print(t(f"Lade DWD-Daten {date_from} → {date_to} für {lat},{lon} …",
            f"Fetching DWD data {date_from} → {date_to} for {lat},{lon} …"))
    data = fetch_brightsky(lat, lon, date_from, date_to)
    if data is None:
        print(t("API nicht erreichbar.", "API not reachable."))
        sys.exit(1)

    n = import_brightsky_from_raw(conn, data)
    conn.close()
    print(t(f"{n} Wetter-Tage importiert.", f"{n} weather days imported."))


if __name__ == "__main__":
    main()
