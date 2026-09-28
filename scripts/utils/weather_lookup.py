#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Wetter-Lookup for beliebige Zeitpunkte and Koordinaten.

@tier        infrastructure
@purpose.de  Ermöglicht Wetterdaten-Abfragen für beliebige Zeitpunkte und Koordinaten
@purpose.en  Enables weather data queries for arbitrary timestamps and coordinates
@method.de   Strategie: Innerhalb HOME_RADIUS_M → lokale Wetterstation; außerhalb → Open-Meteo Archive API mit Caching in weather_remote
@method.en   Strategy: Within HOME_RADIUS_M → local weather station; outside → Open-Meteo Archive API with caching in weather_remote
@limits.de   Genauigkeit abhängig von Open-Meteo-Daten und lokaler Station

@relevance.de  Ermöglicht die Suche und Referenzierung von Daten, essentiell für die Datenintegration
@relevance.en  Enables data lookup and referencing, essential for data integration
@limits.en   Accuracy depends on Open-Meteo data and local station

Strategie:
  1. Innerhalb HOME_RADIUS_M → lokale Weather station (weather_station / home_environment)
  2. Außerhalb → Open-Meteo Archive API, Result wird in weather_remote gecacht

Usage:
  from utils.weather_lookup import get_weather
  w = get_weather(conn, "2024-01-15T18:00:00+01:00", 48.0, 11.0)
  # → {"temp_c": 17.2, "precip_mm": 0.0, "windspeed_kmh": 12.0, ...}

  # Batch for einen Stay:
  from utils.weather_lookup import get_weather_for_stay
  w = get_weather_for_stay(conn, stay_row)

@reads       Externe Wetter-APIs (Open-Meteo, DWD Brightsky)
@writes      Keine Tabellen (gibt Wetterdaten als Dict zurueck)
@usage
    python weather_lookup.py
    python weather_lookup.py --help
    python weather_lookup.py --from 2024-01-01 --to 2024-12-31
"""

import json
import math
import sqlite3
import sys
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from health_config import Config as _Cfg, OWN_PERSON_ID as _OWN_PERSON_ID
from modules.db import open_db

_cfg          = _Cfg()
HOME_LAT      = _cfg.home_lat or 0.0
HOME_LON      = _cfg.home_lon or 0.0
HOME_RADIUS_M = 3000


def _haversine_m(lat1, lon1, lat2, lon2) -> float:
    R = 6_371_000
    φ1, φ2 = math.radians(lat1), math.radians(lat2)
    dφ = math.radians(lat2 - lat1)
    dλ = math.radians(lon2 - lon1)
    a = math.sin(dφ/2)**2 + math.cos(φ1)*math.cos(φ2)*math.sin(dλ/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))


def _parse_ts(s: str) -> datetime:
    s = s.replace("Z", "+00:00")
    return datetime.fromisoformat(s).astimezone(timezone.utc)


def _setup_remote_table(conn: sqlite3.Connection):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS weather_remote (
            ts            TEXT NOT NULL,
            lat           REAL NOT NULL,
            lon           REAL NOT NULL,
            temp_c        REAL,
            precip_mm     REAL,
            windspeed_kmh REAL,
            pressure_hpa  REAL,
            weathercode   INTEGER,
            source        TEXT DEFAULT 'open-meteo',
            person        TEXT NOT NULL DEFAULT 'unknown',
            PRIMARY KEY (ts, lat, lon)
        )
    """)
    conn.commit()


def _round_coords(lat, lon):
    from utils.anonymize import round_coords
    return round_coords(lat, lon)


def _get_home_weather(conn: sqlite3.Connection, dt: datetime) -> dict | None:
    """Liest Wetterdaten der eigenen Station für den Tag von dt.

    Beide Quellen sind TAGESAGGREGATE, keine Stundenwerte — eine Spalte
    ``timestamp`` gibt es in keiner von beiden. Der frühere Code fragte
    ``SELECT temperature, humidity, pressure ... WHERE timestamp >= ?`` ab und
    brach mit "no such column: temperature" ab, sobald er je aufgerufen wurde.
    Die Stundenauflösung der Signatur ist damit nicht erfüllbar; dt wird auf den
    Tag reduziert.
    """
    day = dt.date().isoformat()

    # weather_station (eigene Außenstation, Tageswerte)
    row = conn.execute("""
        SELECT temp_out_c, humidity_out, pressure_hpa
        FROM weather_station
        WHERE date = ?
        LIMIT 1
    """, (day,)).fetchone()

    if row and row[0] is not None:
        return {"temp_c": row[0], "humidity_pct": row[1],
                "pressure_hpa": row[2], "source": "weather_station"}

    # Fallback: home_environment (Innenstation). EAV-Schema — ein Sensortyp
    # je Zeile, Wert in mean_value.
    row = conn.execute("""
        SELECT mean_value
        FROM home_environment
        WHERE date = ? AND sensor_type = 'temperature'
        LIMIT 1
    """, (day,)).fetchone()

    if row and row[0] is not None:
        return {"temp_c": row[0], "source": "home_environment"}

    return None


def _fetch_open_meteo(lat: float, lon: float, date: str) -> list[dict]:
    """
    Holt stündliche Wetterdaten für ein Datum von Open-Meteo Archive API.
    Gibt Liste von stündlichen Dicts zurück.
    """
    url = (
        f"https://archive-api.open-meteo.com/v1/archive"
        f"?latitude={lat}&longitude={lon}"
        f"&start_date={date}&end_date={date}"
        f"&hourly=temperature_2m,precipitation,windspeed_10m,pressure_msl,weathercode"
        f"&timezone=UTC"
    )
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read())
    except Exception as e:
        print(f"[weather_lookup] Open-Meteo error: {e}", file=sys.stderr)
        return []

    hourly = data.get("hourly", {})
    times  = hourly.get("time", [])
    temps  = hourly.get("temperature_2m", [None]*len(times))
    precip = hourly.get("precipitation", [None]*len(times))
    wind   = hourly.get("windspeed_10m", [None]*len(times))
    press  = hourly.get("pressure_msl", [None]*len(times))
    codes  = hourly.get("weathercode", [None]*len(times))

    return [
        {"ts": f"{ts_h}:00+00:00", "temp_c": temps[i], "precip_mm": precip[i],
         "windspeed_kmh": wind[i], "pressure_hpa": press[i], "weathercode": codes[i]}
        for i, ts_h in enumerate(times)
    ]


def _get_remote_weather(conn: sqlite3.Connection, dt: datetime,
                        lat: float, lon: float) -> dict | None:
    """Open-Meteo: erst Cache prüfen, then API."""
    _setup_remote_table(conn)
    rlat, rlon = _round_coords(lat, lon)
    hour_ts = dt.replace(minute=0, second=0, microsecond=0).strftime("%Y-%m-%dT%H:00:00+00:00")

    # Cache prüfen
    row = conn.execute("""
        SELECT temp_c, precip_mm, windspeed_kmh, pressure_hpa, weathercode
        FROM weather_remote WHERE ts=? AND lat=? AND lon=?
    """, (hour_ts, rlat, rlon)).fetchone()

    if row:
        return {"temp_c": row[0], "precip_mm": row[1], "windspeed_kmh": row[2],
                "pressure_hpa": row[3], "weathercode": row[4], "source": "open-meteo-cache"}

    # API holen (ganzen day auf einmal, then cachen)
    date = dt.strftime("%Y-%m-%d")
    hours = _fetch_open_meteo(rlat, rlon, date)
    if not hours:
        return None

    conn.executemany("""
        INSERT OR IGNORE INTO weather_remote
        (ts, lat, lon, temp_c, precip_mm, windspeed_kmh, pressure_hpa, weathercode, person)
        VALUES (?,?,?,?,?,?,?,?,?)
    """, [(h["ts"], rlat, rlon, h["temp_c"], h["precip_mm"],
           h["windspeed_kmh"], h["pressure_hpa"], h["weathercode"], _OWN_PERSON_ID)
          for h in hours])
    conn.commit()

    # Gesuchte Stande zurückgeben
    row = conn.execute("""
        SELECT temp_c, precip_mm, windspeed_kmh, pressure_hpa, weathercode
        FROM weather_remote WHERE ts=? AND lat=? AND lon=?
    """, (hour_ts, rlat, rlon)).fetchone()

    if row:
        return {"temp_c": row[0], "precip_mm": row[1], "windspeed_kmh": row[2],
                "pressure_hpa": row[3], "weathercode": row[4], "source": "open-meteo"}
    return None


def get_weather(conn: sqlite3.Connection,
                ts: str, lat: float, lon: float) -> dict | None:
    """
    Gibt Wetterdaten für Zeitpunkt + Koordinaten zurück.
    Automatisch: Heimwetterstation wenn zuhause, sonst Open-Meteo.
    """
    dt = _parse_ts(ts)
    dist = _haversine_m(lat, lon, HOME_LAT, HOME_LON)

    if dist <= HOME_RADIUS_M:
        result = _get_home_weather(conn, dt)
        if result:
            return result

    return _get_remote_weather(conn, dt, lat, lon)


def get_weather_for_stay(conn: sqlite3.Connection,
                         stay: sqlite3.Row | tuple) -> dict | None:
    """
    Bequemlichkeitsfunktion: Wetter für einen location_stays-Eintrag.
    Nimmt den Mittelpunkt des Aufenthalts als Zeitreferenz.
    stay: (id, start_ts, end_ts, lat, lon, is_home, source)
    """
    if isinstance(stay, tuple):
        start_ts, end_ts, lat, lon = stay[1], stay[2], stay[3], stay[4]
    else:
        start_ts = stay["start_ts"]
        end_ts   = stay["end_ts"]
        lat      = stay["lat"]
        lon      = stay["lon"]

    dt_start = _parse_ts(start_ts)
    dt_end   = _parse_ts(end_ts)
    mid_ts   = (dt_start + (dt_end - dt_start) / 2).isoformat()
    return get_weather(conn, mid_ts, lat, lon)


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 4:
        print("Usage: weather_lookup.py <timestamp> <lat> <lon>")
        sys.exit(1)
    db = open_db()
    result = get_weather(db, sys.argv[1], float(sys.argv[2]), float(sys.argv[3]))
    print(json.dumps(result, indent=2, ensure_ascii=False))
