#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Home Assistant → health.db Import

@tier        infrastructure
@purpose.de  Holt Sensordaten von Home Assistant-Geräten und speichert sie als
             Tagesmittel/-min/-max in die health.db. Unterstützt Philips Somneo
             (Schlafzimmer-Umgebung), EcoWitt-Wetterstationen, DWD-Stationen und
             Luftreiniger (Dyson, VeSync).
@purpose.en  Fetches sensor data from Home Assistant devices and stores it as
             daily mean/min/max in health.db. Supports Philips Somneo (bedroom
             environment), EcoWitt weather stations, DWD stations, and air
             purifiers (Dyson, VeSync).
@method.de   Nutzt die Home Assistant Statistics API. Konfiguration über
             ~/.config/kyoro/ha_config.json mit URL, Token und Entitäten.
             Unterstützt: Temperatur, Luftfeuchtigkeit, Licht, Geräuschpegel,
             Wetterdaten, Luftqualität. Daten werden als Tagesaggregate gespeichert.
@method.en   Uses the Home Assistant Statistics API. Configuration via
             ~/.config/kyoro/ha_config.json with URL, token, and entities.
             Supports: temperature, humidity, light, noise level, weather data,
             air quality. Data is stored as daily aggregates.
@reads       Home Assistant Statistics API (http://homeassistant.local:8123)
@writes      health.db (weather_station, indoor_air_quality, etc.)
@limits.de   Abhängig von der Verfügbarkeit der Home Assistant API und der
             Konfiguration. Keine medizinische Interpretation.

@relevance.de  Ermöglicht den Import von Gesundheitsdaten, essentiell für die umfassende Datenanalyse
@relevance.en  Enables import of health data, essential for comprehensive data analysis
@limits.en   Dependent on the availability of the Home Assistant API and
             configuration. No medical interpretation.
@usage
    python import_homeassistant.py --setup
    python import_homeassistant.py --discover
    python import_homeassistant.py
    python import_homeassistant.py --update
    python import_homeassistant.py --from 2024-01-01 --to 2025-12-31
    python import_homeassistant.py --discover-airpurifiers
    python import_homeassistant.py --add-airpurifier sensor.dyson_pm25
"""

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys as _sys
_sys.path.insert(0, str(Path(__file__).parent.parent))
from health_config import Config as _Cfg, load as _load_cfg, KYORO_CONFIG_DIR
from modules.db import open_db
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from modules.secure_io import write_private_text
from utils.anonymize import round_coords
from modules.base import tz_from_coords, log_import, resolve_person
_cfg = _Cfg()

try:
    import requests
except ImportError:
    print(t("requests fehlt: pip3 install requests", "requests missing: pip3 install requests"))
    sys.exit(1)

DB_PATH      = _cfg.db_path
CONFIG_PATH  = KYORO_CONFIG_DIR / "ha_config.json"
TRAVEL_LOG   = KYORO_CONFIG_DIR / "travel_log.json"

# Homeatstandort (aus health_config — lat/lon/name)
# Auf 2 dec gerundet (~1.1 km Grid) bevor weitergegeben: gleiche Auflösung wie
# alle anderen Stay-/Weather-Koords, kein Hauseingang-Leak in DB/API.
HOME_LAT, HOME_LON = (
    round_coords(_cfg.home_lat, _cfg.home_lon)
    if _cfg.home_lat is not None and _cfg.home_lon is not None
    else (_cfg.home_lat, _cfg.home_lon)
)
HOME_NAME = _cfg.home_name

# Bekannte Somneo-Sensor-Schlüsselwörter for Auto-Discovery
SOMNEO_KEYWORDS = [
    "somneo", "philips", "wake", "wakeup", "sleep_light",
    "schlafzimmer", "bedroom"
]

# FTMS Walking Pad — MAC address configurable via health_config.json ("devices.ftms_mac")
FTMS_DEVICE_MAC = _load_cfg().get("devices", {}).get("ftms_mac", "")

# Sensoren die uns interessieren (Schlüssel → Einheit)
SENSOR_TYPES = {
    "temperature":  "°C",
    "humidity":     "%",
    "light":        "lx",
    "noise":        "dB",
    "illuminance":  "lx",
    "sound":        "dB",
}

def _load_ha_cfg() -> dict:
    if not CONFIG_PATH.exists():
        print(f"Fehler: HA-Konfiguration fehlt: {CONFIG_PATH}", file=sys.stderr)
        print("Bitte ha_config.json anlegen (Vorlage: health_config.example.json).", file=sys.stderr)
        sys.exit(1)
    try:
        return json.loads(CONFIG_PATH.read_text())
    except Exception as e:
        print(f"Fehler beim Lesen von {CONFIG_PATH}: {e}", file=sys.stderr)
        sys.exit(1)

def _require(cfg: dict, key: str):
    if key not in cfg:
        print(f"Fehler: '{key}' fehlt in {CONFIG_PATH}", file=sys.stderr)
        sys.exit(1)
    return cfg[key]

_ha_raw                = _load_ha_cfg()
ECOWITT_ENTITIES       = _require(_ha_raw, "ecowitt_entities")
FTMS_SENSOR_CANDIDATES = _require(_ha_raw, "treadmill_entities")
PRESENCE_TRACKERS      = _require(_ha_raw, "device_trackers")
# Fallback-Startdatum, wenn weder --date-from noch eine vorherige Import-
# Historie vorliegt -- wann die jeweilige Quelle eingerichtet wurde, ist
# personenspezifisch und gehoert daher in die lokale Config, nicht als
# Konstante in den Code. Generischer Fallback, falls nicht konfiguriert.
_DEFAULT_START_FALLBACK = "2020-01-01"
ECOWITT_DEFAULT_START = _ha_raw.get("ecowitt_default_start_date", _DEFAULT_START_FALLBACK)
HA_DEFAULT_START       = _ha_raw.get("default_start_date", _DEFAULT_START_FALLBACK)

# DWD station — nearby official weather station.
# Station ID/name and the per-metric HA sensor entity-IDs live in
# health_config.json under "home_assistant.dwd_station" so the open-source
# tree carries no residence-revealing identifiers.
_ha_cfg = _load_cfg().get("home_assistant", {}).get("dwd_station", {})
DWD_STATION_ID    = _ha_cfg.get("id")
DWD_STATION_NAME  = _ha_cfg.get("name")
DWD_STATION_ENTITIES: dict[str, str] = _ha_cfg.get("entities", {})

# Keywords for Dyson + VeSync air purifier discovery. Brand/product-line
# names only, no specific model numbers -- Home Assistant entity_ids for
# these integrations reliably embed the brand/product-line name itself,
# so exact model numbers aren't needed for detection.
AIRPURIFIER_KEYWORDS = [
    "dyson", "vesync", "levoit", "purifier", "air_purifier", "airpurifier",
]
DYSON_KEYWORDS  = ["dyson"]
VESYNC_KEYWORDS = ["vesync", "levoit", "core", "vital"]


def _airpurifier_brand(entity_id: str) -> str:
    eid = entity_id.lower()
    if any(kw in eid for kw in DYSON_KEYWORDS):  return "dyson"
    if any(kw in eid for kw in VESYNC_KEYWORDS): return "vesync"
    return "other"


# ── Configuration ─────────────────────────────────────────────────────────────
def load_config() -> dict:
    if not CONFIG_PATH.exists():
        print(t(f"Keine Konfiguration gefunden: {CONFIG_PATH}",
                f"No configuration found: {CONFIG_PATH}"))
        print(t("Bitte --setup ausführen.", "Please run --setup."))
        sys.exit(1)
    return json.loads(CONFIG_PATH.read_text())


def get_token_via_password(url: str, username: str, password: str) -> str:
    """Holt Bearer-Token via Username/Passwort (HA OAuth2 Password Flow)."""
    resp = requests.post(
        f"{url}/auth/token",
        data={
            "grant_type": "password",
            "username":   username,
            "password":   password,
            "client_id":  url + "/",
        },
        timeout=15,
    )
    if resp.status_code != 200:
        print(t(f"Login fehlgeschlagen ({resp.status_code}): {resp.text[:200]}",
                f"Login failed ({resp.status_code}): {resp.text[:200]}"))
        sys.exit(1)
    return resp.json()["access_token"]


def setup_config():
    """Interaktive Einrichtung der HA-Verbindung."""
    print(t("=== Home Assistant Konfiguration ===\n", "=== Home Assistant Configuration ===\n"))
    print(t("Authentifizierung wählen:", "Choose authentication method:"))
    print(t("  1) Username + Passwort", "  1) Username + Password"))
    print(t("  2) Long-Lived Access Token (HA → Profil → Sicherheit → Token erstellen)",
            "  2) Long-Lived Access Token (HA → Profile → Security → Create token)"))
    methode = input("\nAuswahl (1/2): ").strip()

    url = input("HA URL (z.B. http://192.168.1.x:8123): ").strip().rstrip("/")

    if methode == "1":
        username = input("Benutzername: ").strip()
        import getpass
        password = getpass.getpass("Passwort: ")
        print(t("Verbinde ...", "Connecting ..."))
        token = get_token_via_password(url, username, password)
        print(t("✅ Anmeldung erfolgreich — Token erhalten.", "✅ Login successful — token received."))
    else:
        token = input("Long-Lived Access Token: ").strip()

    config = {"url": url, "token": token, "entities": {}}
    write_private_text(CONFIG_PATH, json.dumps(config, indent=2))
    print(t(f"\nGespeichert: {CONFIG_PATH}", f"\nSaved: {CONFIG_PATH}"))
    print(t("Jetzt --discover ausführen um Somneo-Entitäten zu finden.",
            "Now run --discover to find Somneo entities."))


# ── HA API ────────────────────────────────────────────────────────────────────
def ha_get(config: dict, endpoint: str, params: dict = None) -> dict | list:
    headers = {
        "Authorization": f"Bearer {config['token']}",
        "Content-Type":  "application/json",
    }
    url = f"{config['url']}/{endpoint.lstrip('/')}"
    r   = requests.get(url, headers=headers, params=params, timeout=30)
    r.raise_for_status()
    return r.json()


def ha_post(config: dict, endpoint: str, body: dict) -> dict | list:
    headers = {
        "Authorization": f"Bearer {config['token']}",
        "Content-Type":  "application/json",
    }
    url = f"{config['url']}/{endpoint.lstrip('/')}"
    r   = requests.post(url, headers=headers, json=body, timeout=60)
    r.raise_for_status()
    return r.json()


# ── Entitäts-Discovery ────────────────────────────────────────────────────────
def discover_entities(config: dict) -> dict:
    """Findet all Somneo/Philips/Schlafzimmer-Sensoren in HA."""
    print(t("Verbinde mit Home Assistant ...", "Connecting to Home Assistant ..."))
    try:
        states = ha_get(config, "/api/states")
    except Exception as e:
        print(t(f"Verbindungsfehler: {e}", f"Connection error: {e}"))
        sys.exit(1)

    print(t(f"  {len(states)} Entitäten gefunden. Suche Somneo-Sensoren ...\n",
            f"  {len(states)} entities found. Searching for Somneo sensors ...\n"))
    found = {}

    for state in states:
        entity_id = state.get("entity_id", "")
        if not entity_id.startswith("sensor."):
            continue

        entity_lower = entity_id.lower()
        friendly     = state.get("attributes", {}).get("friendly_name", "").lower()

        # Prüfe ob Somneo/Schlafzimmer-Keyword enthalten
        is_relevant = any(kw in entity_lower or kw in friendly
                         for kw in SOMNEO_KEYWORDS)
        if not is_relevant:
            continue

        unit  = state.get("attributes", {}).get("unit_of_measurement", "")
        value = state.get("state", "unavailable")
        fname = state.get("attributes", {}).get("friendly_name", entity_id)

        found[entity_id] = {
            "friendly_name": fname,
            "unit":          unit,
            "current_value": value,
        }

    return found


# ── Statistiken abrufen ───────────────────────────────────────────────────────
def ha_utc_to_local_str(ts: str) -> str:
    """Konvertiert HA UTC-Timestamp in lokale Zeitstring (Europe/Berlin)."""
    if not ts or len(ts) < 16:
        return ""
    try:
        ts_clean = ts.replace("Z", "+00:00")
        dt_utc   = datetime.fromisoformat(ts_clean)
        if dt_utc.tzinfo is None:
            dt_utc = dt_utc.replace(tzinfo=timezone.utc)
        dt_naive = dt_utc.utctimetuple()
        dt_naive = datetime(*dt_naive[:6])
        y = dt_naive.year
        mar = datetime(y,3,31) - timedelta(days=datetime(y,3,31).weekday()+1)
        oct = datetime(y,10,31) - timedelta(days=datetime(y,10,31).weekday()+1)
        offset = 2 if mar <= dt_naive < oct else 1
        return (dt_naive + timedelta(hours=offset)).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return ts[:19]


def fetch_timeseries(config: dict, entity_ids: list[str],
                     start: datetime, end: datetime) -> dict:
    """Holt minütliche Zeitreihen via HA History API (UTC→Lokalzeit)."""
    import urllib.parse
    result = {}  # entity_id → list of (datetime_local, value)

    current = start
    while current < end:
        block_end = min(current + timedelta(days=7), end)
        params = {
            "filter_entity_id": ",".join(entity_ids),
            "end_time":         block_end.isoformat(),
            "minimal_response": "false",
            "no_attributes":    "true",
        }
        try:
            history = ha_get(config,
                f"/api/history/period/{urllib.parse.quote(current.isoformat())}",
                params=params)
            for entity_history in history:
                if not entity_history:
                    continue
                eid = entity_history[0].get("entity_id", "")
                if eid not in result:
                    result[eid] = []
                for state in entity_history:
                    ts  = state.get("last_updated") or state.get("last_changed") or ""
                    val = state.get("state", "")
                    dt_local = ha_utc_to_local_str(ts)
                    if dt_local and val not in ("unavailable", "unknown", ""):
                        try:
                            result[eid].append((dt_local, float(val)))
                        except ValueError:
                            pass
        except Exception as e:
            print(t(f"  Zeitreihe Fehler: {e}", f"  Time series error: {e}"))
        current = block_end

    return result


def import_timeseries_to_db(conn: sqlite3.Connection,
                             timeseries: dict,
                             entity_meta: dict) -> int:
    rows = []
    for entity_id, points in timeseries.items():
        meta  = entity_meta.get(entity_id, {})
        stype = infer_sensor_type(entity_id, meta.get("unit", ""))
        for dt_local, val in points:
            rows.append((dt_local, stype, val, entity_id))

    conn.executemany("""INSERT OR IGNORE INTO home_environment_ts
        (datetime, sensor_type, value, entity_id)
        VALUES (?,?,?,?)""", rows)
    conn.commit()
    return len(rows)


def fetch_statistics(config: dict, entity_ids: list[str],
                     start: datetime, end: datetime) -> dict:
    """
    Holt Sensor-Historie via HA History API (in 7-days-Blöcken).
    Die Statistics REST API ist in HA 2024+ only still via WebSocket available.
    Tipp: In configuration.yaml recorder.purge_keep_days: 730 setzen!
    """
    import urllib.parse
    from collections import defaultdict

    result = defaultdict(lambda: defaultdict(list))  # entity_id → date → [values]

    # In 7-days-Blöcken abrufen (History API Liwith)
    current = start
    while current < end:
        block_end = min(current + timedelta(days=7), end)
        params = {
            "filter_entity_id": ",".join(entity_ids),
            "end_time":         block_end.isoformat(),
            "minimal_response": "true",
            "no_attributes":    "true",
        }
        try:
            history = ha_get(config,
                f"/api/history/period/{urllib.parse.quote(current.isoformat())}",
                params=params)
        except Exception as e:
            print(t(f"  History API Fehler: {e}", f"  History API error: {e}"))
            current = block_end
            continue

        for entity_history in history:
            if not entity_history:
                continue
            entity_id = entity_history[0].get("entity_id", "")
            for state in entity_history:
                try:
                    val  = float(state.get("state", "nan"))
                    date = (state.get("last_updated") or state.get("last_changed") or "")[:10]
                    if date and not __import__('math').isnan(val):
                        result[entity_id][date].append(val)
                except (ValueError, TypeError):
                    pass

        current = block_end

    # Aggregiere zu Tagesmittel/-min/-max
    aggregated = {}
    for entity_id, daily in result.items():
        aggregated[entity_id] = [
            {
                "date": date,
                "mean": round(sum(vals) / len(vals), 2),
                "min":  round(min(vals), 2),
                "max":  round(max(vals), 2),
            }
            for date, vals in sorted(daily.items()) if vals
        ]
    return aggregated


def fetch_history_fallback(config: dict, entity_ids: list[str],
                           start: datetime, end: datetime) -> dict:
    """Fallback: History API for kürzere Zeiträume."""
    params = {
        "filter_entity_id": ",".join(entity_ids),
        "end_time": end.isoformat(),
    }
    try:
        history = ha_get(config, f"/api/history/period/{start.isoformat()}", params)
    except Exception as e:
        print(t(f"  History API auch fehlgeschlagen: {e}", f"  History API also failed: {e}"))
        return {}

    result = {}
    for entity_history in history:
        if not entity_history:
            continue
        entity_id = entity_history[0].get("entity_id")
        daily = {}
        for state in entity_history:
            try:
                val  = float(state.get("state", "nan"))
                ts   = state.get("last_updated", "")[:10]
                if ts and ts not in daily:
                    daily[ts] = []
                if ts:
                    daily[ts].append(val)
            except (ValueError, TypeError):
                pass
        result[entity_id] = [
            {"date": d, "mean": round(sum(v)/len(v),2),
             "min": round(min(v),2), "max": round(max(v),2)}
            for d, v in sorted(daily.items()) if v
        ]
    return result


# ── Database ─────────────────────────────────────────────────────────────────
def setup_db(conn: sqlite3.Connection):
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS home_environment (
        date            TEXT,
        entity_id       TEXT,
        sensor_type     TEXT,
        mean_value      REAL,
        min_value       REAL,
        max_value       REAL,
        unit            TEXT,
        source          TEXT DEFAULT 'homeassistant',
        PRIMARY KEY (date, entity_id)
    );
    CREATE INDEX IF NOT EXISTS idx_home_env_date ON home_environment(date);
    CREATE INDEX IF NOT EXISTS idx_home_env_type ON home_environment(sensor_type);

    CREATE TABLE IF NOT EXISTS weather_station (
        date            TEXT PRIMARY KEY,
        location        TEXT,   -- 'home' / Stadtname / Koordinaten
        lat             REAL,   -- Breitengrad
        lon             REAL,   -- Längengrad
        temp_out_c      REAL,   -- Außentemperatur Tagesmittel °C
        temp_out_min    REAL,   -- Außentemperatur Minimum °C
        temp_out_max    REAL,   -- Außentemperatur Maximum °C
        humidity_out    REAL,   -- Außenluftfeuchtigkeit % Mittel
        temp_in_c       REAL,   -- Innentemperatur °C
        humidity_in     REAL,   -- Innenluftfeuchtigkeit %
        pressure_hpa    REAL,   -- Relativer Luftdruck hPa Mittel
        pressure_min    REAL,
        pressure_max    REAL,
        wind_speed_kmh  REAL,   -- Windgeschwindigkeit Mittel km/h
        wind_gust_max   REAL,   -- Max. Windböe km/h
        wind_dir_deg    REAL,   -- Mittlere Windrichtung °
        rain_mm         REAL,   -- Tagesniederschlag mm
        rain_rate_max   REAL,   -- Max. Regenrate mm/h
        uv_index_max    REAL,   -- UV-Index Maximum
        solar_wm2_max   REAL,   -- Max. Solarstrahlung W/m²
        dewpoint_c      REAL,   -- Taupunkt °C Mittel
        feels_like_c    REAL,   -- Gefühlte Temperatur °C Mittel
        source          TEXT    -- 'ecowitt' / 'open_meteo'
    );
    CREATE INDEX IF NOT EXISTS idx_weather_date ON weather_station(date);
    """)
    # columns nachträglich hinzufügen falls Table already without sie existiert
    existing_cols = {r[1] for r in conn.execute("PRAGMA table_info(weather_station)")}
    for col, typedef in [
        ("location", "TEXT"),
        ("lat",      "REAL"),
        ("lon",      "REAL"),
        ("source",   "TEXT"),
    ]:
        if col not in existing_cols:
            conn.execute(f"ALTER TABLE weather_station ADD COLUMN {col} {typedef}")
    conn.commit()


def get_last_import_date(conn: sqlite3.Connection) -> str | None:
    r = conn.execute("SELECT MAX(date) FROM home_environment").fetchone()
    return r[0] if r and r[0] else None


def infer_sensor_type(entity_id: str, unit: str) -> str:
    eid = entity_id.lower()
    if "pm2_5" in eid or "pm25" in eid or "particulate_matter_2_5" in eid: return "pm25"
    if "pm10" in eid or "particulate_matter_10" in eid:                     return "pm10"
    if "hcho" in eid or "formaldehyde" in eid:                              return "hcho"
    if "voc" in eid or "volatile_organic" in eid:                           return "voc"
    if "nitrogen_dioxide" in eid or ("no2" in eid and "no2" != eid.split(".")[-1]): return "no2"
    if ("air_quality_index" in eid or "luftqualitatsindex" in eid
            or eid.endswith("_aqi") or eid.endswith(".aqi")):               return "aqi"
    if "co2" in eid or "carbon_dioxide" in eid:                             return "co2"
    if "filter" in eid:                                                      return "filter_life"
    if "temp" in eid:                                                        return "temperature"
    if "humid" in eid:                                                       return "humidity"
    if "sound_pressure" in eid or "sound" in eid:                           return "noise"
    if "noise" in eid or unit.lower() == "db":                              return "noise"
    if "illumin" in eid or unit == "lx":                                    return "light"
    if "light" in eid:                                                       return "light"
    return "other"


def import_to_db(conn: sqlite3.Connection, statistics: dict,
                 entity_meta: dict) -> int:
    rows  = []
    for entity_id, daily_data in statistics.items():
        meta  = entity_meta.get(entity_id, {})
        unit  = meta.get("unit", "")
        stype = infer_sensor_type(entity_id, unit)
        for day in daily_data:
            rows.append((
                day["date"], entity_id, stype,
                day.get("mean"), day.get("min"), day.get("max"),
                unit
            ))

    conn.executemany("""
        INSERT OR IGNORE INTO home_environment
        (date, entity_id, sensor_type, mean_value, min_value, max_value, unit)
        VALUES (?,?,?,?,?,?,?)""", rows)
    conn.commit()
    return len(rows)


# ── Air Purifier (Dyson / VeSync) ─────────────────────────────────────────────

def _setup_iaq_table(conn: sqlite3.Connection):
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS indoor_air_quality (
        date        TEXT NOT NULL,
        entity_id   TEXT NOT NULL,
        device      TEXT,
        sensor_type TEXT,
        mean_value  REAL,
        min_value   REAL,
        max_value   REAL,
        unit        TEXT,
        source      TEXT DEFAULT 'homeassistant',
        person      TEXT NOT NULL DEFAULT 'unknown',
        PRIMARY KEY (date, entity_id)
    );
    CREATE INDEX IF NOT EXISTS idx_iaq_date   ON indoor_air_quality(date);
    CREATE INDEX IF NOT EXISTS idx_iaq_type   ON indoor_air_quality(sensor_type);
    CREATE INDEX IF NOT EXISTS idx_iaq_device ON indoor_air_quality(device);
    """)
    conn.commit()


def discover_airpurifiers(config: dict) -> dict:
    """Findet alle Dyson/VeSync/Luftreiniger-Sensoren in HA."""
    print(t("Verbinde mit Home Assistant ...", "Connecting to Home Assistant ..."))
    try:
        states = ha_get(config, "/api/states")
    except Exception as e:
        print(t(f"Verbindungsfehler: {e}", f"Connection error: {e}"))
        sys.exit(1)

    print(t(f"  {len(states)} Entitäten gefunden. Suche Luftreiniger ...\n",
            f"  {len(states)} entities found. Searching for air purifiers ...\n"))
    found = {}
    for state in states:
        entity_id = state.get("entity_id", "")
        if not entity_id.startswith("sensor."):
            continue
        eid_lower = entity_id.lower()
        friendly  = state.get("attributes", {}).get("friendly_name", "").lower()
        if not any(kw in eid_lower or kw in friendly for kw in AIRPURIFIER_KEYWORDS):
            continue
        unit  = state.get("attributes", {}).get("unit_of_measurement", "")
        value = state.get("state", "unavailable")
        fname = state.get("attributes", {}).get("friendly_name", entity_id)
        found[entity_id] = {"friendly_name": fname, "unit": unit, "current_value": value}
    return found


def import_airpurifier_to_db(conn: sqlite3.Connection, statistics: dict,
                              entity_meta: dict, person: str | None = None) -> int:
    person = resolve_person(person)
    _setup_iaq_table(conn)
    rows = []
    for entity_id, daily_data in statistics.items():
        meta   = entity_meta.get(entity_id, {})
        unit   = meta.get("unit", "")
        stype  = infer_sensor_type(entity_id, unit)
        device = _airpurifier_brand(entity_id)
        for day in daily_data:
            rows.append((
                day["date"], entity_id, device, stype,
                day.get("mean"), day.get("min"), day.get("max"),
                unit, person
            ))
    conn.executemany("""
        INSERT OR IGNORE INTO indoor_air_quality
        (date, entity_id, device, sensor_type, mean_value, min_value, max_value, unit, person)
        VALUES (?,?,?,?,?,?,?,?,?)""", rows)
    conn.commit()
    return len(rows)


# ── Hauptprogramm ─────────────────────────────────────────────────────────────
def fetch_presence(config: dict, start: datetime, end: datetime) -> list[dict]:
    """
    Holt Anwesenheitsdaten aus HA History API.
    Sourcen: ha_config.json["device_trackers"] (person, iphone, car).
    Gibt dayssliste zurück: {date, at_home, iphone_home, car_home, away_hours}
    """
    import urllib.parse
    from collections import defaultdict

    ENTITIES = {
        "person": PRESENCE_TRACKERS.get("person", ""),
        "iphone": PRESENCE_TRACKERS.get("iphone", ""),
        "car":    PRESENCE_TRACKERS.get("car", ""),
    }

    # In 7-days-Blöcken abrufen
    raw = defaultdict(lambda: defaultdict(list))  # key → date → [states]
    current = start
    while current < end:
        block_end = min(current + timedelta(days=7), end)
        params = {
            "filter_entity_id": ",".join(ENTITIES.values()),
            "end_time":         block_end.isoformat(),
            "minimal_response": "true",
            "no_attributes":    "true",
        }
        try:
            history = ha_get(config,
                f"/api/history/period/{urllib.parse.quote(current.isoformat())}",
                params=params)
            for entity_history in history:
                if not entity_history:
                    continue
                eid  = entity_history[0].get("entity_id", "")
                key  = next((k for k, v in ENTITIES.items() if v == eid), None)
                if not key:
                    continue
                for state in entity_history:
                    date = (state.get("last_updated") or "")[:10]
                    val  = state.get("state", "")
                    if date and val not in ("unavailable", "unknown", ""):
                        raw[key][date].append(val)
        except Exception as e:
            print(t(f"  Presence API Fehler: {e}", f"  Presence API error: {e}"))
        current = block_end

    # Aggregiere pro Tag: home wenn >50 % der Meldungen "home"
    # Schlafdatum N = Nacht N-1 23:45 → N 06:00.
    # Strategie: letzten bekannten State vor/bei 23:45 des Vortags ermitteln
    # (point-in-time), danach prüfen ob zwischen 00:00–06:00 zuhause.

    # Alle States mit exakten Timestamps sammeln
    raw_states = defaultdict(list)  # key → [(datetime_lokal, state)]

    def ha_utc_to_local(ts: str) -> datetime | None:
        """HA liefert UTC (+00:00) — konvertiert in Lokalzeit Europe/Berlin."""
        if not ts or len(ts) < 16:
            return None
        try:
            dt_utc = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            if dt_utc.tzinfo is None:
                # No Offset angegeben → als UTC behandeln
                from datetime import timezone as tz
                dt_utc = dt_utc.replace(tzinfo=tz.utc)
            dt_naive = dt_utc.utctimetuple()
            dt_naive = datetime(*dt_naive[:6])  # UTC ohne Offset
            y = dt_naive.year
            mar = datetime(y,3,31) - timedelta(days=datetime(y,3,31).weekday()+1)
            oct = datetime(y,10,31) - timedelta(days=datetime(y,10,31).weekday()+1)
            offset = 2 if mar <= dt_naive < oct else 1
            return dt_naive + timedelta(hours=offset)
        except Exception:
            return None

    current = start - timedelta(days=1)  # einen Tag früher für 23:45-Check
    while current < end:
        block_end = min(current + timedelta(days=7), end)
        params = {
            "filter_entity_id": ",".join(ENTITIES.values()),
            "end_time":         block_end.isoformat(),
            "minimal_response": "false",
        }
        try:
            history = ha_get(config,
                f"/api/history/period/{urllib.parse.quote(current.isoformat())}",
                params=params)
            for entity_history in history:
                if not entity_history:
                    continue
                eid = entity_history[0].get("entity_id", "")
                key = next((k for k, v in ENTITIES.items() if v == eid), None)
                if not key:
                    continue
                for state in entity_history:
                    ts  = state.get("last_updated") or state.get("last_changed") or ""
                    val = state.get("state", "")
                    if val not in ("unavailable", "unknown", ""):
                        dt_local = ha_utc_to_local(ts)
                        if dt_local:
                            raw_states[key].append((dt_local, val))
        except Exception:
            pass
        current = block_end

    # States sortieren
    for key in raw_states:
        raw_states[key].sort(key=lambda x: x[0])

    def state_at(key: str, dt: datetime) -> str | None:
        """Letzter bekannter State zum Zeitpunkt dt (or kurz davor)."""
        states = raw_states[key]
        result_state = None
        for ts, val in states:
            if ts <= dt:
                result_state = val
            else:
                break
        return result_state

    def home_at(key: str, dt: datetime) -> bool | None:
        s = state_at(key, dt)
        if s is None:
            return None
        return s == "home"

    # Alle Schlafdaten-Tage aus den vorhandenen States ableiten
    all_dates = sorted(set(
        ts.strftime("%Y-%m-%d")
        for key_states in raw_states.values()
        for ts, _ in key_states
    ))

    result = []
    for date in all_dates:
        try:
            d = datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            continue
        prev = d - timedelta(days=1)

        # Prüfzeitpunkte: 23:45 Vortag + 03:00 dieses days
        t_2345 = prev.replace(hour=23, minute=45)
        t_0300 = d.replace(hour=3, minute=0)

        h_2345 = home_at("person", t_2345)
        h_0300 = home_at("person", t_0300)
        h_iphone = home_at("iphone", t_0300)
        h_car    = home_at("car",    d.replace(hour=12))  # Mittag für Auto

        # Zuhause geschlafen: 23:45 home UND 03:00 home (or Fallback iPhone)
        if h_2345 is not None and h_0300 is not None:
            slept_home = h_2345 and h_0300
        elif h_2345 is not None:
            slept_home = h_2345
        elif h_0300 is not None:
            slept_home = h_0300
        else:
            slept_home = None

        # iPhone als Fallback
        if slept_home is None:
            slept_home = h_iphone

        # hours weg: Anteil der Prüfpunkte with not_home
        check_points = [home_at("person", d.replace(hour=h)) for h in range(6, 23)]
        valid = [v for v in check_points if v is not None]
        away_hours = round(sum(0 if v else 1 for v in valid) / len(valid) * 17, 1) if valid else None

        result.append({
            "date":        date,
            "at_home":     1 if slept_home else (0 if slept_home is not None else None),
            "iphone_home": 1 if h_iphone else (0 if h_iphone is not None else None),
            "car_home":    1 if h_car else (0 if h_car is not None else None),
            "away_hours":  away_hours,
        })

    return result


def import_presence_to_db(conn: sqlite3.Connection, presence: list[dict]) -> int:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS home_presence (
            date        TEXT PRIMARY KEY,
            at_home     INTEGER,   -- 1=zuhause, 0=weg, NULL=unbekannt
            iphone_home INTEGER,
            car_home    INTEGER,
            away_hours  REAL,      -- geschätzte Stunden weg
            source      TEXT DEFAULT 'homeassistant'
        );
    """)
    rows = [(p["date"], p["at_home"], p["iphone_home"],
             p["car_home"], p["away_hours"]) for p in presence]
    conn.executemany("""
        INSERT OR IGNORE INTO home_presence
        (date, at_home, iphone_home, car_home, away_hours)
        VALUES (?,?,?,?,?)""", rows)
    conn.commit()
    return len(rows)


def import_weather_to_db(conn: sqlite3.Connection, stats: dict, person: str | None = None) -> int:
    """Aggregiert Ecowitt-Rohdaten zu daysszeilen in weather_station."""
    person = resolve_person(person)
    by_date: dict[str, dict] = {}
    field_map = {v: k for k, v in ECOWITT_ENTITIES.items()}

    for entity_id, daily_data in stats.items():
        field = field_map.get(entity_id)
        if not field:
            continue
        for day in daily_data:
            d = day["date"]
            if d not in by_date:
                by_date[d] = {}
            by_date[d][field] = day

    rows = []
    for date, f in sorted(by_date.items()):
        g = lambda k, agg: f[k][agg] if k in f else None
        rows.append((
            date, HOME_NAME, HOME_LAT, HOME_LON,
            g("temp_out","mean"), g("temp_out","min"),  g("temp_out","max"),
            g("humidity_out","mean"),
            g("temp_in","mean"),  g("humidity_in","mean"),
            g("pressure","mean"), g("pressure","min"),   g("pressure","max"),
            g("wind_speed","mean"),
            g("wind_gust","max") or g("wind_gust_max","max"),
            g("wind_dir","mean"),
            g("rain_daily","max"),   # laufende Tagessumme → MAX = Tagesregen
            g("rain_rate","max"),
            g("uv_index","max"),
            g("solar_wm2","max"),
            g("dewpoint","mean"),
            g("feels_like","mean"),
            person,
        ))

    conn.executemany("""
        INSERT OR IGNORE INTO weather_station
        (date, location, lat, lon,
         temp_out_c, temp_out_min, temp_out_max,
         humidity_out, temp_in_c, humidity_in,
         pressure_hpa, pressure_min, pressure_max,
         wind_speed_kmh, wind_gust_max, wind_dir_deg,
         rain_mm, rain_rate_max, uv_index_max, solar_wm2_max,
         dewpoint_c, feels_like_c, person, source)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,'ecowitt')""", rows)
    conn.commit()
    return len(rows)


# ── DWD Station (configurable via health_config.home_assistant.dwd_station) ──

def _setup_dwd_station_table(conn: sqlite3.Connection) -> None:
    """Delegates to AEMET module's _setup_table to keep schema in one place."""
    from importers.import_aemet import _setup_table as _aemet_setup
    _aemet_setup(conn)


def import_dwd_station_to_db(conn: sqlite3.Connection, stats: dict) -> int:
    """Aggregate DWD station data (id/name from health_config) into weather_dwd_station."""
    if not DWD_STATION_ID or not DWD_STATION_ENTITIES:
        return 0
    _setup_dwd_station_table(conn)

    by_date: dict[str, dict] = {}
    field_map = {v: k for k, v in DWD_STATION_ENTITIES.items()}

    for entity_id, daily_data in stats.items():
        field = field_map.get(entity_id)
        if not field:
            continue
        for day in daily_data:
            d = day["date"]
            by_date.setdefault(d, {})[field] = day

    rows = []
    for date, f in sorted(by_date.items()):
        g = lambda k, agg: f[k][agg] if k in f else None
        sunshine_s = g("sunshine_s", "max")
        sunshine_h = round(sunshine_s / 3600, 2) if sunshine_s is not None else None
        rows.append((
            date, DWD_STATION_ID, DWD_STATION_NAME,
            g("uv_index",     "max"),
            g("solar_wm2",    "max"),
            g("solar_wm2",    "mean"),
            sunshine_h,
            g("cloud_pct",    "mean"),
            g("temp_c",       "mean"),
            g("temp_c",       "min"),
            g("temp_c",       "max"),
            g("dewpoint_c",   "mean"),
            g("humidity",     "mean"),
            None, None,               # humidity_min, humidity_max (not tracked via HA)
            g("pressure_hpa", "mean"),
            g("pressure_hpa", "min"),
            g("pressure_hpa", "max"),
            None, None, None,         # wind_speed, gust, dir (not in DWD_STATION_ENTITIES)
            None, None, None,         # rain, snow, evap
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
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,'dwd_station')
    """, rows)
    conn.commit()
    return len(rows)


# ── Open-Meteo (Reisewetter) ──────────────────────────────────────────────────
def load_travel_log() -> dict:
    """
    Loads ~/.config/travel_log.json.
    Neues Format: {"periods": [...], "days": {...}}
    Altes Format (flat dict) wird automatisch als days behandelt.
    """
    if not TRAVEL_LOG.exists():
        return {"periods": [], "days": {}}
    try:
        data = json.loads(TRAVEL_LOG.read_text())
        if isinstance(data, dict) and "periods" not in data:
            data = {"periods": [], "days": data}
        data.setdefault("periods", [])
        data.setdefault("days", {})
        return data
    except Exception:
        return {"periods": [], "days": {}}


def geocode_city(city: str) -> tuple[float, float] | None:
    """Open-Meteo Geocoding API — no API-Key nötig."""
    try:
        r = requests.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": city, "count": 1, "language": "de", "format": "json"},
            timeout=10)
        results = r.json().get("results", [])
        if results:
            return results[0]["latitude"], results[0]["longitude"]
    except Exception:
        pass
    return None


def fetch_open_meteo(lat: float, lon: float,
                     date_from: str, date_to: str) -> list[dict]:
    """
    Holt tägliche Wetterdaten via Open-Meteo Historical API.
    Gibt Liste from Dicts zurück (ein entry pro day).
    """
    lat, lon = round_coords(lat, lon)
    try:
        r = requests.get(
            "https://archive-api.open-meteo.com/v1/archive",
            params={
                "latitude":            lat,
                "longitude":           lon,
                "start_date":          date_from,
                "end_date":            date_to,
                "daily": ",".join([
                    "temperature_2m_mean",
                    "temperature_2m_min",
                    "temperature_2m_max",
                    "relative_humidity_2m_mean",
                    "precipitation_sum",
                    "wind_speed_10m_max",
                    "wind_direction_10m_dominant",
                    "pressure_msl_mean",
                    "uv_index_max",
                    "shortwave_radiation_sum",  # MJ/m² → *1000/3600 = W/m² Tagesmittel
                    "dew_point_2m_mean",
                    "apparent_temperature_mean",
                    "apparent_temperature_min",
                    "apparent_temperature_max",
                ]),
                "timezone":            tz_from_coords(lat, lon) or _cfg.home_timezone,
                "wind_speed_unit":     "kmh",
            },
            timeout=30)
        r.raise_for_status()
        data = r.json()
        daily = data.get("daily", {})
        dates = daily.get("time", [])
        result = []
        for i, date in enumerate(dates):
            def v(key):
                vals = daily.get(key, [])
                return vals[i] if i < len(vals) else None
            # Solarstrahlung: MJ/m² Tagessumme → W/m² Tagesmittel (÷86400s×1e6)
            solar_mj = v("shortwave_radiation_sum")
            solar_wm2 = round(solar_mj * 1e6 / 86400, 1) if solar_mj is not None else None
            result.append({
                "date":       date,
                "temp_mean":  v("temperature_2m_mean"),
                "temp_min":   v("temperature_2m_min"),
                "temp_max":   v("temperature_2m_max"),
                "humidity":   v("relative_humidity_2m_mean"),
                "pressure":   v("pressure_msl_mean"),
                "wind_speed": v("wind_speed_10m_max"),
                "wind_dir":   v("wind_direction_10m_dominant"),
                "rain_mm":    v("precipitation_sum"),
                "uv_max":     v("uv_index_max"),
                "solar_wm2":  solar_wm2,
                "dewpoint":   v("dew_point_2m_mean"),
                "feels_like": v("apparent_temperature_mean"),
            })
        return result
    except Exception as e:
        print(t(f"  Open-Meteo Fehler: {e}", f"  Open-Meteo error: {e}"))
        return []


def import_reise_weather(conn: sqlite3.Connection,
                          date_from: str, date_to: str,
                          person: str | None = None) -> int:
    """
    Imports Wetterdaten for Reisetage aus Open-Meteo.
    Strategie:
      1. days wo weather_station still leer (no Ecowitt-entry)
      2. days wo at_home=0 in home_presence
      3. Koordinaten aus travel_log.json, sonst Home-Koordinaten
    """
    person = resolve_person(person)
    reise_log = load_travel_log()
    geocache: dict[str, tuple] = {}  # city → (lat, lon)

    # All days without Ecowitt-Daten im Time range
    existing = {r[0] for r in conn.execute(
        "SELECT date FROM weather_station WHERE source='ecowitt'")}

    # Away-days aus home_presence
    away_dates = {r[0] for r in conn.execute(
        "SELECT date FROM home_presence WHERE at_home=0")}

    # All Datumswerte im Time range
    from_d = datetime.strptime(date_from, "%Y-%m-%d")
    to_d   = datetime.strptime(date_to,   "%Y-%m-%d")
    all_dates = []
    cur = from_d
    while cur <= to_d:
        all_dates.append(cur.strftime("%Y-%m-%d"))
        cur += timedelta(days=1)

    # days die wir holen wollen: away ODER still no entry
    target_dates = sorted(set(all_dates) - existing | away_dates - existing)
    if not target_dates:
        print(t("  Keine fehlenden Tage gefunden.", "  No missing days found."))
        return 0

    # Häufigste Nicht-Zuhause-Position aus location_history pro day
    location_history_coords: dict[str, tuple[float, float, str]] = {}
    try:
        for row in conn.execute("""
            SELECT date, lat, lon, city, COUNT(*) n
            FROM location_history
            WHERE state != 'home'
            GROUP BY date, ROUND(lat,2), ROUND(lon,2)
            ORDER BY date, n DESC"""):
            d, lat, lon, city, _ = row
            if d not in location_history_coords:  # erste = häufigste
                lat_r, lon_r = round_coords(lat, lon)
                location_history_coords[d] = (lat_r, lon_r, city or f"{lat_r:.2f},{lon_r:.2f}")
    except Exception:
        pass

    # Koordinaten pro day bestimmen (Priorität: reise_log > location_history > home)
    def coords_for_date(date: str) -> tuple[float, float, str]:
        # 1. Einzeltag-entry im reise_log
        days_entry = reise_log.get("days", {}).get(date)
        if days_entry:
            if isinstance(days_entry, dict) and "lat" in days_entry:
                return days_entry["lat"], days_entry["lon"], days_entry.get("city", date)
            city = days_entry if isinstance(days_entry, str) else days_entry.get("city", "")
            if city:
                if city not in geocache:
                    coords = geocode_city(city)
                    geocache[city] = coords or (HOME_LAT, HOME_LON)
                lat, lon = geocache.get(city, (HOME_LAT, HOME_LON))
                return lat, lon, city

        # 2. Time range-entries im reise_log
        for period in reise_log.get("periods", []):
            if period["from"] <= date <= period["to"]:
                return period["lat"], period["lon"], period.get("city", date)

        # 3. location_history (iPhone-GPS)
        if date in location_history_coords:
            return location_history_coords[date]

        # 4. Fallback: Zuhause
        return HOME_LAT, HOME_LON, HOME_NAME

    # Gruppiere zusammenhängende days with gleichen Koordinaten → ein API-Call
    groups: list[tuple[float, float, str, list[str]]] = []
    for date in target_dates:
        lat, lon, loc = coords_for_date(date)
        if groups and groups[-1][:3] == (lat, lon, loc):
            groups[-1][3].append(date)
        else:
            groups.append((lat, lon, loc, [date]))

    rows = []
    for lat, lon, loc, dates in groups:
        lat, lon = round_coords(lat, lon)
        d_from = dates[0]
        d_to   = dates[-1]
        print(t(f"  Open-Meteo: {loc} ({lat:.2f},{lon:.2f}) {d_from}→{d_to} ...",
                f"  Open-Meteo: {loc} ({lat:.2f},{lon:.2f}) {d_from}→{d_to} ..."), end=" ", flush=True)
        weather = fetch_open_meteo(lat, lon, d_from, d_to)
        print(t(f"{len(weather)} Tage", f"{len(weather)} days"))
        for w in weather:
            if w["date"] not in target_dates:
                continue
            source = "open_meteo_home" if loc == HOME_NAME else "open_meteo_reise"
            rows.append((
                w["date"], loc, lat, lon,
                w["temp_mean"], w["temp_min"],  w["temp_max"],
                w["humidity"], None, None,
                w["pressure"], None, None,
                w["wind_speed"], None, w["wind_dir"],
                w["rain_mm"], None,
                w["uv_max"], w["solar_wm2"],
                w["dewpoint"], w["feels_like"],
                person, source,
            ))

    if rows:
        conn.executemany("""
            INSERT OR IGNORE INTO weather_station
            (date, location, lat, lon,
             temp_out_c, temp_out_min, temp_out_max,
             humidity_out, temp_in_c, humidity_in,
             pressure_hpa, pressure_min, pressure_max,
             wind_speed_kmh, wind_gust_max, wind_dir_deg,
             rain_mm, rain_rate_max, uv_index_max, solar_wm2_max,
             dewpoint_c, feels_like_c, person, source)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", rows)
        conn.commit()

    return len(rows)


def main():
    """
    Hauptfunktion: Koordiniert den Import der Home Assistant-Daten.

    Command-Line-Argumente:
        --setup: Konfiguration einrichten
        --discover: Somneo-Entitäten suchen
        --update: Nur neue Daten
        --from: Startdatum (YYYY-MM-DD)
        --to: Enddatum (YYYY-MM-DD)
    """
    parser = argparse.ArgumentParser(description="Home Assistant → health.db")
    parser.add_argument("--setup",    action="store_true", help="Konfiguration einrichten")
    parser.add_argument("--discover", action="store_true", help="Somneo-Entitäten suchen")
    parser.add_argument("--update",   action="store_true", help="Nur neue Daten (seit letztem Import)")
    parser.add_argument("--from",     dest="date_from", default=None, help="Start YYYY-MM-DD")
    parser.add_argument("--to",       dest="date_to",   default=None, help="Ende YYYY-MM-DD")
    parser.add_argument("--add-entity", dest="add_entity", default=None,
                        help="Entität zur Konfiguration hinzufügen")
    parser.add_argument("--discover-ftms", action="store_true",
                        help="FTMS Walking Pad Sensoren suchen (Pad muss laufen)")
    parser.add_argument("--ecowitt",  action="store_true",
                        help="Ecowitt Wetterstation importieren")
    parser.add_argument("--reisen",   action="store_true",
                        help="Reisetage via Open-Meteo auffüllen")
    parser.add_argument("--discover-airpurifiers", action="store_true",
                        help="Dyson/VeSync Luftreiniger-Sensoren suchen")
    parser.add_argument("--airpurifiers", action="store_true",
                        help="Dyson/VeSync Luftqualitätsdaten importieren")
    parser.add_argument("--add-airpurifier", dest="add_airpurifier", default=None,
                        metavar="ENTITY_ID",
                        help="Luftreiniger-Entität zur Konfiguration hinzufügen")
    parser.add_argument("--person", default=None, help="Ziel-Person (Default: OWN_PERSON_ID)")
    add_lang_arg(parser)

    args = parser.parse_args()
    apply_lang_from_args(args)
    person = resolve_person(args.person)

    if args.setup:
        setup_config()
        return

    config = load_config()

    if args.discover_ftms:
        print(t("Suche FTMS Walking Pad Sensoren (FITHOME JJ-BT2-P) ...",
                "Searching for FTMS walking pad sensors (FITHOME JJ-BT2-P) ..."))
        print(t("Hinweis: Pad muss eingeschaltet und verbunden sein.\n",
                "Note: pad must be switched on and connected.\n"))
        try:
            all_states = ha_get(config, "/api/states")
            found_ftms = {}
            for s in all_states:
                eid = s.get("entity_id", "")
                name = s.get("attributes", {}).get("friendly_name", "")
                val  = s.get("state", "")
                unit = s.get("attributes", {}).get("unit_of_measurement", "")
                # FTMS-typische Entity-Muster
                if (any(kw in eid.lower() for kw in
                        ["fithome","ftms","jj_bt2","treadmill","laufband"]) or
                    eid in FTMS_SENSOR_CANDIDATES):
                    found_ftms[eid] = {"name": name, "value": val, "unit": unit}
            if found_ftms:
                print(t(f"✅ {len(found_ftms)} FTMS-Sensoren gefunden:\n",
                        f"✅ {len(found_ftms)} FTMS sensors found:\n"))
                for eid, m in found_ftms.items():
                    print(f"  {eid}")
                    print(f"    {m['name']}: {m['value']} {m['unit']}")
            else:
                print(t("❌ Keine FTMS-Sensoren aktiv.", "❌ No FTMS sensors active."))
                print(t("   Starte das Walking Pad und verbinde es mit HA,",
                        "   Start the walking pad and connect it to HA,"))
                print(t("   dann diesen Befehl erneut ausführen.",
                        "   then run this command again."))
                print(t(f"\n   Bekanntes Gerät: FITHOME JJ-BT2-P ({FTMS_DEVICE_MAC})",
                        f"\n   Known device: FITHOME JJ-BT2-P ({FTMS_DEVICE_MAC})"))
                print(t("   HA-Integration: ftms (Status: setup_retry)",
                        "   HA integration: ftms (status: setup_retry)"))
        except Exception as e:
            print(t(f"Fehler: {e}", f"Error: {e}"))
        return

    if args.discover_airpurifiers:
        found = discover_airpurifiers(config)
        if not found:
            print(t("Keine Luftreiniger-Sensoren gefunden.",
                    "No air purifier sensors found."))
            print(t("Prüfe ob Dyson/VeSync in HA integriert sind (hacs-dyson / vesync-Integration).",
                    "Check whether Dyson/VeSync are integrated in HA (hacs-dyson / vesync integration)."))
        else:
            print(t(f"{len(found)} Luftreiniger-Sensoren gefunden:\n",
                    f"{len(found)} air purifier sensors found:\n"))
            for eid, meta in found.items():
                brand = _airpurifier_brand(eid)
                stype = infer_sensor_type(eid, meta["unit"])
                print(f"  [{brand:6s}] {eid}")
                print(f"           {meta['friendly_name']}: {meta['current_value']} {meta['unit']} ({stype})")
            print(t("\nGewünschte Sensoren hinzufügen:",
                    "\nAdd desired sensors:"))
            print("  python import_homeassistant.py --add-airpurifier sensor.dyson_pm25")
        return

    if args.add_airpurifier:
        ap_entities = config.get("airpurifier_entities", [])
        eid = args.add_airpurifier
        if eid not in ap_entities:
            ap_entities.append(eid)
        config["airpurifier_entities"] = ap_entities
        write_private_text(CONFIG_PATH, json.dumps(config, indent=2))
        brand = _airpurifier_brand(eid)
        stype = infer_sensor_type(eid, "")
        print(t(f"Luftreiniger-Entität hinzugefügt: {eid} ({brand}, {stype})",
                f"Air purifier entity added: {eid} ({brand}, {stype})"))
        return

    if args.discover:
        found = discover_entities(config)
        if not found:
            print(t("Keine Somneo-Entitäten gefunden.", "No Somneo entities found."))
            print(t("Überprüfe Schlüsselwörter oder füge manuell hinzu.",
                    "Check keywords or add manually."))
        else:
            print(t(f"{len(found)} relevante Sensoren gefunden:\n",
                    f"{len(found)} relevant sensors found:\n"))
            for eid, meta in found.items():
                print(f"  {eid}")
                print(f"    Name:  {meta['friendly_name']}")
                print(t(f"    Einheit: {meta['unit']} | Aktuell: {meta['current_value']}",
                        f"    Unit: {meta['unit']} | Current: {meta['current_value']}"))
            print(t("\nFüge gewünschte Entitäten zur Konfiguration hinzu:",
                    "\nAdd desired entities to the configuration:"))
            print("  python import_homeassistant.py --add-entity sensor.somneo_temperature")
        return

    if args.add_entity:
        entities = config.get("entities", {})
        eid = args.add_entity
        stype = infer_sensor_type(eid, "")
        entities[stype] = eid
        config["entities"] = entities
        write_private_text(CONFIG_PATH, json.dumps(config, indent=2))
        print(t(f"Entität hinzugefügt: {stype} = {eid}", f"Entity added: {stype} = {eid}"))
        return

    # Entitäten aus Configuration
    entities = config.get("entities", {})
    if not entities:
        print(t("Keine Entitäten konfiguriert. Bitte --discover und dann --add-entity nutzen.",
                "No entities configured. Please run --discover and then --add-entity."))
        sys.exit(1)

    entity_ids = list(entities.values())
    print(t(f"Importiere {len(entity_ids)} Sensoren: {', '.join(entity_ids)}",
            f"Importing {len(entity_ids)} sensors: {', '.join(entity_ids)}"))

    # Time range bestimmen
    conn = open_db()
    setup_db(conn)

    if args.update:
        if args.ecowitt:
            r = conn.execute("SELECT MAX(date) FROM weather_station").fetchone()
            last_w = r[0] if r and r[0] else None
            start_dt = (datetime.fromisoformat(last_w) + timedelta(days=1)).replace(
                tzinfo=timezone.utc) if last_w else datetime.fromisoformat(
                ECOWITT_DEFAULT_START).replace(tzinfo=timezone.utc)
        else:
            last = get_last_import_date(conn)
            start_dt = (datetime.fromisoformat(last) + timedelta(days=1)).replace(
                tzinfo=timezone.utc) if last else datetime.fromisoformat(
                HA_DEFAULT_START).replace(tzinfo=timezone.utc)
        print(t(f"Update-Modus: ab {start_dt.date()}", f"Update mode: from {start_dt.date()}"))
    elif args.date_from:
        start_dt = datetime.fromisoformat(args.date_from).replace(tzinfo=timezone.utc)
    else:
        start_dt = (datetime.fromisoformat(ECOWITT_DEFAULT_START) if args.ecowitt
                    else datetime.fromisoformat(HA_DEFAULT_START)).replace(tzinfo=timezone.utc)

    end_dt = (datetime.fromisoformat(args.date_to).replace(tzinfo=timezone.utc)
              if args.date_to
              else datetime.now(tz=timezone.utc))

    print(t(f"Zeitraum: {start_dt.date()} → {end_dt.date()}", f"Period: {start_dt.date()} → {end_dt.date()}"))

    # Meta for all Entitäten laden
    entity_meta = {}
    try:
        all_states = ha_get(config, "/api/states")
        for s in all_states:
            if s.get("entity_id") in entity_ids:
                entity_meta[s["entity_id"]] = {
                    "unit": s.get("attributes", {}).get("unit_of_measurement", ""),
                    "friendly_name": s.get("attributes", {}).get("friendly_name", ""),
                }
    except Exception as e:
        print(t(f"  Warnung: Metadaten nicht geladen ({e})", f"  Warning: metadata not loaded ({e})"))

    # Statistiken abrufen (in Monatsblöcken um Timeout zu vermeiden)
    total_imported = 0
    # In einem Zug holen (fetch_statistics macht intern 7-days-Blöcke)
    print(t("  Hole Daten ...", "  Fetching data ..."), end=" ", flush=True)
    stats = fetch_statistics(config, entity_ids, start_dt, end_dt)
    total_imported = import_to_db(conn, stats, entity_meta)
    print(t(f"{total_imported} Einträge", f"{total_imported} entries"))

    print(t(f"\nGesamt Tages-Aggregate: {total_imported} Einträge importiert",
            f"\nTotal daily aggregates: {total_imported} entries imported"))

    # Minütliche Zeitreihen importieren
    print(t("Importiere Zeitreihen (~2-Min-Intervalle) ...",
            "Importing time series (~2-min intervals) ..."))
    ts_data = fetch_timeseries(config, entity_ids, start_dt, end_dt)
    n_ts = import_timeseries_to_db(conn, ts_data, entity_meta)
    for eid, pts in ts_data.items():
        stype = infer_sensor_type(eid, entity_meta.get(eid, {}).get("unit", ""))
        print(t(f"  {stype}: {len(pts)} Messpunkte", f"  {stype}: {len(pts)} data points"))
    print(t(f"Gesamt Zeitreihe: {n_ts} Einträge importiert",
            f"Total time series: {n_ts} entries imported"))

    # Anwesenheit importieren
    print(t("\nImportiere Anwesenheitsdaten (Person, iPhone, Auto) ...",
            "\nImporting presence data (person, iPhone, car) ..."))
    presence = fetch_presence(config, start_dt, end_dt)
    n_pres = import_presence_to_db(conn, presence)
    home_n = sum(1 for p in presence if p["at_home"] == 1)
    away_n = sum(1 for p in presence if p["at_home"] == 0)
    print(t(f"  {n_pres} Tage | Zuhause: {home_n} | Weg: {away_n}",
            f"  {n_pres} days | At home: {home_n} | Away: {away_n}"))

    # Overview
    print(t("\n── Übersicht home_environment ──────────────────────────",
            "\n── Overview home_environment ───────────────────────────"))
    for r in conn.execute("""
        SELECT sensor_type, COUNT(*), MIN(date), MAX(date),
               ROUND(AVG(mean_value),2), unit
        FROM home_environment GROUP BY sensor_type, unit ORDER BY sensor_type"""):
        print(f"  {r[0]:<15} {r[1]:>5} {t('Tage', 'days')} | {r[2]}→{r[3]} | ∅{r[4]} {r[5]}")

    # Ecowitt Weather station
    if args.ecowitt:
        print(t("\n── Ecowitt Wetterstation ────────────────────────",
                "\n── Ecowitt weather station ─────────────────────"))
        ecowitt_ids = list(ECOWITT_ENTITIES.values())
        print(t(f"  {len(ecowitt_ids)} Sensoren werden abgerufen ...",
                f"  Fetching {len(ecowitt_ids)} sensors ..."))
        weather_stats = fetch_statistics(config, ecowitt_ids, start_dt, end_dt)
        n_weather = import_weather_to_db(conn, weather_stats, person)
        print(t(f"  {n_weather} Tage importiert", f"  {n_weather} days imported"))

        r = conn.execute("""
            SELECT COUNT(*), MIN(date), MAX(date),
                   ROUND(AVG(temp_out_c),1),
                   ROUND(MIN(temp_out_min),1), ROUND(MAX(temp_out_max),1),
                   ROUND(AVG(pressure_hpa),1),
                   ROUND(SUM(rain_mm),1)
            FROM weather_station WHERE source='ecowitt'""").fetchone()
        if r and r[0]:
            print(t(f"  Zeitraum: {r[1]} → {r[2]}", f"  Period: {r[1]} → {r[2]}"))
            print(t(f"  Außentemperatur: ∅{r[3]}°C | min {r[4]}°C | max {r[5]}°C",
                    f"  Outdoor temperature: ∅{r[3]}°C | min {r[4]}°C | max {r[5]}°C"))
            print(t(f"  Luftdruck: ∅{r[6]} hPa | Gesamtregen: {r[7]} mm",
                    f"  Air pressure: ∅{r[6]} hPa | Total rain: {r[7]} mm"))

    if args.reisen:
        print(t("\n── Reisetage (Open-Meteo) ───────────────────────────────",
                "\n── Travel days (Open-Meteo) ─────────────────────────────"))
        n_reise = import_reise_weather(conn, start_dt.strftime("%Y-%m-%d"),
                                       end_dt.strftime("%Y-%m-%d"), person)
        print(t(f"  {n_reise} Tage via Open-Meteo importiert",
                f"  {n_reise} days imported via Open-Meteo"))
        # Overview nach Source
        for r in conn.execute("""
            SELECT source, COUNT(*), MIN(date), MAX(date)
            FROM weather_station GROUP BY source ORDER BY source"""):
            print(f"  {r[0]:<25} {r[1]:>4} {t('Tage', 'days')} | {r[2]}→{r[3]}")
        if not TRAVEL_LOG.exists():
            print(t(f"\n  Tipp: Reiseziele in {TRAVEL_LOG} eintragen:",
                    f"\n  Tip: add travel destinations to {TRAVEL_LOG}:"))
            print('  {"YYYY-MM-DD": {"city": "Cityname", "lat": 0.0, "lon": 0.0}}')

    if args.airpurifiers:
        print(t("\n── Luftreiniger (Dyson / VeSync) ───────────────────────",
                "\n── Air purifiers (Dyson / VeSync) ──────────────────────"))
        ap_entity_ids = config.get("airpurifier_entities", [])
        if not ap_entity_ids:
            print(t("Keine Luftreiniger-Entitäten konfiguriert.",
                    "No air purifier entities configured."))
            print(t("  Erst --discover-airpurifiers, dann --add-airpurifier <entity_id> ausführen.",
                    "  Run --discover-airpurifiers first, then --add-airpurifier <entity_id>."))
        else:
            print(t(f"  {len(ap_entity_ids)} Entitäten: {', '.join(ap_entity_ids)}",
                    f"  {len(ap_entity_ids)} entities: {', '.join(ap_entity_ids)}"))
            # Entity-Metadaten laden
            ap_meta = {}
            try:
                all_states = ha_get(config, "/api/states")
                for s in all_states:
                    if s.get("entity_id") in ap_entity_ids:
                        ap_meta[s["entity_id"]] = {
                            "unit":          s.get("attributes", {}).get("unit_of_measurement", ""),
                            "friendly_name": s.get("attributes", {}).get("friendly_name", ""),
                        }
            except Exception as e:
                print(t(f"  Warnung: Metadaten nicht geladen ({e})",
                        f"  Warning: metadata not loaded ({e})"))

            print(t("  Hole Daten ...", "  Fetching data ..."), end=" ", flush=True)
            ap_stats = fetch_statistics(config, ap_entity_ids, start_dt, end_dt)
            n_ap = import_airpurifier_to_db(conn, ap_stats, ap_meta, person)
            print(t(f"{n_ap} Einträge", f"{n_ap} entries"))

            # Summary per device + sensor type
            for r in conn.execute("""
                SELECT device, sensor_type, COUNT(*), MIN(date), MAX(date),
                       ROUND(AVG(mean_value),2), unit
                FROM indoor_air_quality
                GROUP BY device, sensor_type, unit
                ORDER BY device, sensor_type"""):
                print(f"  {r[0]:<8} {r[1]:<12} {r[2]:>5} {t('Tage','days')} | "
                      f"{r[3]}→{r[4]} | ∅{r[5]} {r[6]}")

    log_import(conn, 'homeassistant', '', total_imported, person=person)
    conn.commit()
    conn.close()
    print(t(f"\nDatenbank: {DB_PATH}", f"\nDatabase: {DB_PATH}"))


if __name__ == "__main__":
    main()
