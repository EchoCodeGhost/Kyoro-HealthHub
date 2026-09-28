#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
AEMET-Importer — Agencia Estatal de Meteorología

@tier        infrastructure
@purpose.de  Importiert tägliche Klimadaten von AEMET-Messstationen
@purpose.en  Imports daily climate data from AEMET weather stations
@method.de   Holt tägliche Klimadaten (inkl. Sonnenstunden, Strahlung) von der
             nächstgelegenen AEMET-Messstation.
             API-Key: Kostenlose Registrierung unter https://opendata.aemet.es/
             In health_config.json: { "apis": { "aemet_api_key": "eyJ..." } }
@method.en   Fetches daily climate data (including sunshine hours, radiation) from the
             nearest AEMET weather station.
             API-Key: Free registration at https://opendata.aemet.es/
             In health_config.json: { "apis": { "aemet_api_key": "eyJ..." } }
@reads       AEMET API (online, spanische Wetterdaten)
@writes      health.db (Tabelle weather_aemet)
@limits.de   Nur für Aufenthalte in Spanien. Benötigt API-Key.

@relevance.de  Ermöglicht den Import von Gesundheitsdaten, essentiell für die umfassende Datenanalyse
@relevance.en  Enables import of health data, essential for comprehensive data analysis
@limits.en   Only for stays in Spain. Requires API key.
@usage
    python importers/import_aemet.py --lat 40.4 --lon -3.7 --date-from 2026-06-01 --date-to 2026-06-05
    python importers/import_aemet.py --discover --lat 40.4 --lon -3.7
"""

import argparse
import json
import math
import sqlite3
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from health_config import Config as _Cfg, KYORO_CONFIG_DIR
from modules.db import open_db
from utils.anonymize import round_coords
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from modules.base import log_import, resolve_person

_cfg = _Cfg()

AEMET_BASE   = "https://opendata.aemet.es/opendata/api"
_STATION_CACHE = Path.home() / ".cache" / "kyoro_aemet_stations.json"
_CACHE_MAX_AGE = 30 * 86400  # 30 days


def _is_spain(lat: float, lon: float) -> bool:
    """Rough bounding-box check for Spain (mainland + Canary Islands)."""
    mainland = 36.0 <= lat <= 43.8 and -9.3 <= lon <= 4.3
    canaries = 27.0 <= lat <= 29.5 and -18.2 <= lon <= -13.4
    balearics = 38.6 <= lat <= 40.1 and 1.1 <= lon <= 4.4
    return mainland or canaries or balearics


def _get_api_key(api_key: str | None = None) -> str | None:
    if api_key:
        return api_key
    key = None
    cfg_path = KYORO_CONFIG_DIR / "health_config.json"
    if cfg_path.exists():
        try:
            raw = json.loads(cfg_path.read_text())
            key = raw.get("apis", {}).get("aemet_api_key") or raw.get("aemet_api_key")
        except Exception:
            pass
    return key


def _aemet_get(endpoint: str, api_key: str) -> dict | list | None:
    """AEMET two-step fetch: first call returns datos URL, second fetches actual data."""
    url = f"{AEMET_BASE}/{endpoint.lstrip('/')}"
    headers = {"api_key": api_key, "Accept": "application/json"}
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as r:
            meta = json.loads(r.read())
    except Exception as e:
        print(t(f"[aemet] Fehler bei {url}: {e}", f"[aemet] Error at {url}: {e}"), file=sys.stderr)
        return None

    estado = meta.get("estado", 0)
    if estado != 200:
        desc = meta.get("descripcion", "?")
        print(t(f"[aemet] API-Status {estado}: {desc}", f"[aemet] API status {estado}: {desc}"), file=sys.stderr)
        return None

    datos_url = meta.get("datos")
    if not datos_url:
        return meta

    # Second request: actual data
    try:
        time.sleep(0.3)   # be polite to AEMET API
        req2 = urllib.request.Request(datos_url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req2, timeout=15) as r2:
            return json.loads(r2.read())
    except Exception as e:
        print(t(f"[aemet] Datenfehler {datos_url}: {e}", f"[aemet] Data error {datos_url}: {e}"), file=sys.stderr)
        return None


def _load_station_cache() -> list[dict] | None:
    if not _STATION_CACHE.exists():
        return None
    age = time.time() - _STATION_CACHE.stat().st_mtime
    if age > _CACHE_MAX_AGE:
        return None
    try:
        return json.loads(_STATION_CACHE.read_text())
    except Exception:
        return None


def _save_station_cache(stations: list[dict]) -> None:
    _STATION_CACHE.parent.mkdir(parents=True, exist_ok=True)
    _STATION_CACHE.write_text(json.dumps(stations, ensure_ascii=False))


def fetch_stations(api_key: str) -> list[dict] | None:
    """Fetch all AEMET stations (with caching)."""
    cached = _load_station_cache()
    if cached:
        return cached
    data = _aemet_get("/valores/climatologicos/inventarioestaciones/todasestaciones/", api_key)
    if not data or not isinstance(data, list):
        return None
    _save_station_cache(data)
    return data


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distance in km between two lat/lon points."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    return R * 2 * math.asin(math.sqrt(a))


def nearest_station(stations: list[dict], lat: float, lon: float,
                    max_km: float = 50.0) -> dict | None:
    """Find the nearest AEMET station within max_km that has climate data."""
    best, best_d = None, float("inf")
    for s in stations:
        try:
            slat = float(str(s.get("latitud", "")).replace(",", ".").replace("N","").replace("S","-").strip())
            slon = float(str(s.get("longitud", "")).replace(",", ".").replace("E","").replace("O","-").replace("W","-").strip())
        except (ValueError, AttributeError):
            continue
        d = _haversine(lat, lon, slat, slon)
        if d < best_d and d <= max_km:
            best_d, best = d, s
    if best:
        best["_distance_km"] = round(best_d, 1)
    return best


def fetch_daily(api_key: str, station_id: str, date_from: str, date_to: str) -> list[dict] | None:
    """Fetch daily climate data for a station and date range."""
    # AEMET date format: YYYY-MM-DDTHH:MM:SSUTC
    start = f"{date_from}T00:00:00UTC"
    end   = f"{date_to}T23:59:59UTC"
    ep = (f"/valores/climatologicos/diarios/datos/"
          f"fechaini/{start}/fechafin/{end}/estacion/{station_id}/")
    return _aemet_get(ep, api_key)


def _f(val) -> float | None:
    if val is None:
        return None
    try:
        return float(str(val).replace(",", ".").strip())
    except (ValueError, TypeError):
        return None


def _setup_table(conn: sqlite3.Connection) -> None:
    """Create / migrate weather_dwd_station to full schema (DWD + AEMET compatible)."""
    row = conn.execute("SELECT type FROM sqlite_master WHERE name='weather_dwd_station'").fetchone()
    if row and row[0] == "view":
        conn.execute("DROP VIEW weather_dwd_station")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS weather_dwd_station (
            date              TEXT NOT NULL PRIMARY KEY,
            station_id        TEXT,
            station_name      TEXT,
            -- Solar / UV (DWD only; AEMET has no UV/radiation sensors)
            uv_index          REAL,
            solar_wm2         REAL,
            solar_wm2_mean    REAL,
            sunshine_h        REAL,   -- Sonnenscheindauer h (AEMET: sol; DWD: sonnenscheindauer/3600)
            cloud_pct         REAL,   -- Bewölkungsgrad % (DWD only)
            -- Temperature
            temp_c            REAL,   -- Mitteltemperatur °C (AEMET: tmed)
            temp_min          REAL,   -- Minimum °C        (AEMET: tmin)
            temp_max          REAL,   -- Maximum °C        (AEMET: tmax)
            dewpoint_c        REAL,   -- Taupunkt °C (DWD only)
            -- Humidity
            humidity          REAL,   -- Mittel %  (AEMET: hrMedia)
            humidity_min      REAL,   -- Minimum % (AEMET: hrMin)
            humidity_max      REAL,   -- Maximum % (AEMET: hrMax)
            -- Pressure (AEMET has no mean → average of min+max stored in pressure_hpa)
            pressure_hpa      REAL,   -- Mittel hPa (DWD: presmed; AEMET: (presMax+presMin)/2)
            pressure_min      REAL,   -- Minimum hPa (AEMET: presMin)
            pressure_max      REAL,   -- Maximum hPa (AEMET: presMax)
            -- Wind
            wind_speed_kmh    REAL,   -- Mittel km/h (AEMET: velmedia)
            wind_gust_max     REAL,   -- Max. Böe km/h (AEMET: racha)
            wind_dir_deg      REAL,   -- Richtung ° (AEMET: dir × 10)
            -- Precipitation
            rain_mm           REAL,   -- Niederschlag mm (AEMET: prec)
            snow_cm           REAL,   -- Schneehöhe cm (AEMET: nieve)
            evap_mm           REAL,   -- Verdunstung mm (AEMET: evap)
            source            TEXT DEFAULT 'dwd_station',
            person            TEXT NOT NULL DEFAULT 'unknown'
        )
    """)
    # Migrate existing tables that may be missing newer columns
    existing = {r[1] for r in conn.execute("PRAGMA table_info(weather_dwd_station)")}
    new_cols = [
        ("temp_min",       "REAL"), ("temp_max",       "REAL"),
        ("humidity_min",   "REAL"), ("humidity_max",   "REAL"),
        ("pressure_min",   "REAL"), ("pressure_max",   "REAL"),
        ("wind_speed_kmh", "REAL"), ("wind_gust_max",  "REAL"),
        ("wind_dir_deg",   "REAL"), ("rain_mm",        "REAL"),
        ("snow_cm",        "REAL"), ("evap_mm",        "REAL"),
        ("solar_wm2_mean", "REAL"),
        ("person",         "TEXT NOT NULL DEFAULT 'unknown'"),
    ]
    for col, typedef in new_cols:
        if col not in existing:
            conn.execute(f"ALTER TABLE weather_dwd_station ADD COLUMN {col} {typedef}")
    conn.commit()


def import_to_db(conn: sqlite3.Connection, records: list[dict],
                 station_id: str, station_name: str,
                 person: str | None = None) -> int:
    """Import AEMET daily records into weather_dwd_station (all available fields)."""
    _person = resolve_person(person)
    _setup_table(conn)
    rows = []
    for r in records:
        date = r.get("fecha", "")[:10]
        if not date:
            continue

        pres_max = _f(r.get("presMax"))
        pres_min = _f(r.get("presMin"))
        # AEMET has no mean pressure — estimate as midpoint
        pres_mean = round((pres_max + pres_min) / 2, 1) if pres_max and pres_min else (pres_max or pres_min)

        # Wind direction: AEMET gives tens-of-degrees (e.g. 23 = 230°)
        dir_raw = _f(r.get("dir"))
        wind_dir = round(dir_raw * 10) if dir_raw is not None else None

        rows.append((
            date, station_id, station_name,
            None,                       # uv_index   — AEMET doesn't measure UV
            None,                       # solar_wm2  — AEMET doesn't measure radiation
            None,                       # solar_wm2_mean
            _f(r.get("sol")),           # sunshine_h ✅
            None,                       # cloud_pct  — not in AEMET daily
            _f(r.get("tmed")),          # temp_c     ✅
            _f(r.get("tmin")),          # temp_min   ✅
            _f(r.get("tmax")),          # temp_max   ✅
            None,                       # dewpoint_c — not in AEMET daily
            _f(r.get("hrMedia")),       # humidity   ✅
            _f(r.get("hrMin")),         # humidity_min ✅
            _f(r.get("hrMax")),         # humidity_max ✅
            pres_mean,                  # pressure_hpa ✅ (approx)
            pres_min,                   # pressure_min ✅
            pres_max,                   # pressure_max ✅
            _f(r.get("velmedia")),      # wind_speed_kmh ✅
            _f(r.get("racha")),         # wind_gust_max  ✅
            wind_dir,                   # wind_dir_deg   ✅
            _f(r.get("prec")),          # rain_mm        ✅
            _f(r.get("nieve")),         # snow_cm        ✅
            _f(r.get("evap")),          # evap_mm        ✅
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
         source, person)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,'aemet',?)
    """, [r + (_person,) for r in rows])
    log_import(conn, 'aemet', '', len(rows), person=_person)
    conn.commit()
    return len(rows)


def fetch_and_import(conn: sqlite3.Connection,
                     lat: float, lon: float,
                     date_from: str, date_to: str,
                     api_key: str | None = None,
                     verbose: bool = True,
                     person: str | None = None) -> int:
    """Full pipeline: find nearest station, fetch data, import to DB."""
    api_key = _get_api_key(api_key)
    if not api_key:
        if verbose:
            print(t("[aemet] Kein API-Key — bitte 'apis.aemet_api_key' in health_config.json eintragen",
                    "[aemet] No API key — please set 'apis.aemet_api_key' in health_config.json"),
                  file=sys.stderr)
        return 0

    lat, lon = round_coords(lat, lon)
    if verbose:
        print(t("[aemet] Lade Stationsinventar ...", "[aemet] Loading station inventory ..."))
    stations = fetch_stations(api_key)
    if not stations:
        return 0

    station = nearest_station(stations, lat, lon)
    if not station:
        if verbose:
            print(t(f"[aemet] Keine Station innerhalb 50 km von {lat:.2f},{lon:.2f}",
                    f"[aemet] No station within 50 km of {lat:.2f},{lon:.2f}"),
                  file=sys.stderr)
        return 0

    sid   = station.get("indicativo", "?")
    sname = station.get("nombre", sid)
    dist  = station.get("_distance_km", "?")
    if verbose:
        print(t(f"[aemet] Nächste Station: {sname} ({sid}), {dist} km",
                f"[aemet] Nearest station: {sname} ({sid}), {dist} km"))

    records = fetch_daily(api_key, sid, date_from, date_to)
    if not records:
        if verbose:
            print(t(f"[aemet] Keine Daten für {sid} {date_from}–{date_to}",
                    f"[aemet] No data for {sid} {date_from}–{date_to}"), file=sys.stderr)
        return 0

    n = import_to_db(conn, records, sid, sname, person=person)
    if verbose:
        print(t(f"[aemet] {n} Tage importiert (station={sid})",
                f"[aemet] {n} days imported (station={sid})"))
    return n


def main():
    parser = argparse.ArgumentParser(
        description=t("AEMET-Daten für Spanien-Aufenthalte holen und importieren",
                      "Fetch and import AEMET data for stays in Spain")
    )
    parser.add_argument("--lat", type=float, required=True)
    parser.add_argument("--lon", type=float, required=True)
    parser.add_argument("--date-from", default=None)
    parser.add_argument("--date-to",   default=None)
    parser.add_argument("--api-key",   default=None)
    parser.add_argument("--discover",  action="store_true",
                        help=t("Nur nächste Station anzeigen, nicht importieren",
                               "Only show nearest station, do not import"))
    parser.add_argument("--db", default=None)
    parser.add_argument("--person", default=None, help="Ziel-Person (Default: OWN_PERSON_ID)")
    add_lang_arg(parser)
    args = parser.parse_args()
    apply_lang_from_args(args)

    if not _is_spain(args.lat, args.lon):
        print(t(f"Koordinaten {args.lat},{args.lon} liegen nicht in Spanien.",
                f"Coordinates {args.lat},{args.lon} are not in Spain."), file=sys.stderr)
        sys.exit(1)

    api_key = _get_api_key(args.api_key)
    if not api_key:
        print(t("Kein AEMET API-Key. Bitte 'apis.aemet_api_key' in ~/.config/kyoro/health_config.json.",
                "No AEMET API key. Please set 'apis.aemet_api_key' in ~/.config/kyoro/health_config.json."),
              file=sys.stderr)
        sys.exit(1)

    stations = fetch_stations(api_key)
    if not stations:
        sys.exit(1)

    station = nearest_station(stations, args.lat, args.lon)
    if not station:
        print(t("Keine AEMET-Station innerhalb 50 km.", "No AEMET station within 50 km."), file=sys.stderr)
        sys.exit(1)

    sid   = station.get("indicativo", "?")
    sname = station.get("nombre", sid)
    dist  = station.get("_distance_km", "?")
    alt   = station.get("altitud", "?")
    print(t(f"Nächste Station: {sname} ({sid}), {dist} km, {alt} m ü.M.",
            f"Nearest station: {sname} ({sid}), {dist} km, {alt} m a.s.l."))

    if args.discover:
        return

    if not args.date_from:
        print(t("--date-from erforderlich.", "--date-from required."), file=sys.stderr)
        sys.exit(1)

    date_to = args.date_to or args.date_from
    records = fetch_daily(api_key, sid, args.date_from, date_to)
    if not records:
        print(t("Keine Daten zurückgegeben.", "No data returned."), file=sys.stderr)
        sys.exit(1)

    print(t(f"\nDaten ({len(records)} Tage):", f"\nData ({len(records)} days):"))
    for r in records:
        sol = r.get("sol", "–")
        tmed = r.get("tmed", "–")
        prec = r.get("prec", "–")
        print(t(f"  {r.get('fecha','?')[:10]}  Sonne: {sol}h  Temp: {tmed}°C  Regen: {prec}mm",
                f"  {r.get('fecha','?')[:10]}  Sun: {sol}h  Temp: {tmed}°C  Rain: {prec}mm"))

    db_path = args.db or str(_cfg.db_path)
    conn = open_db(db_path)
    n = import_to_db(conn, records, sid, sname, person=args.person)
    conn.close()
    print(t(f"\n✓ {n} Tage in weather_dwd_station importiert (source=aemet)",
            f"\n✓ {n} days imported into weather_dwd_station (source=aemet)"))


if __name__ == "__main__":
    main()
