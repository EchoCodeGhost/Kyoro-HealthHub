#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
iPhone location tracker via Home Assistant

@tier        infrastructure
@purpose.de  Verfolgt iPhone-Standortdaten über Home Assistant für Wetter- und Reiseanalysen
@purpose.en  Tracks iPhone location data via Home Assistant for weather and travel analysis
@method.de   Abfrage des aktuellen Standorts von Home Assistant alle paar Stunden; speichert in location_history; Wetter-Importer nutzt diese Daten für Open-Meteo-Standortbestimmung
@method.en   Queries current location from Home Assistant every few hours; stores in location_history; weather importer uses this data for Open-Meteo location determination
@limits.de   Abhängig von Home Assistant-Konfiguration und iPhone-Standortfreigabe

@relevance.de  Ermöglicht die Verfolgung und Analyse von Standortdaten, essentiell für die Mobilitätsanalyse
@relevance.en  Enables tracking and analysis of location data, essential for mobility analysis
@limits.en   Dependent on Home Assistant configuration and iPhone location sharing

Queries the current location from HA every few hours and stores
it in location_history. The weather importer uses this data to
determine the correct Open-Meteo location for travel days.

Configuration: ~/.config/kyoro/ha_config.json (shared with import_homeassistant.py)

Usage:
  python3 track_location.py            # single query (+ auto-backfill on gap)
  python3 track_location.py --backfill # fill gaps from HA history
  python3 track_location.py --history  # show last entries
  python3 track_location.py --today    # show today's summary

@reads       ~/.config/kyoro/travel_history.json, ext. Geolocation-APIs
@writes      ~/.config/kyoro/travel_history.json
@usage
    python track_location.py
    python track_location.py --help
    python track_location.py --from 2024-01-01 --to 2024-12-31
"""

import argparse
import json
import sqlite3
import sys
import urllib.parse
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys as _sys
_sys.path.insert(0, str(Path(__file__).parent.parent))
from health_config import Config as _Cfg, KYORO_CONFIG_DIR
from modules.db import open_db
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from utils.anonymize import round_coords
_cfg = _Cfg()

try:
    import requests
except ImportError:
    print("requests missing: pip3 install requests", file=sys.stderr)
    sys.exit(1)

DB_PATH     = _cfg.db_path
CONFIG_PATH = KYORO_CONFIG_DIR / "ha_config.json"
TRAVEL_LOG  = KYORO_CONFIG_DIR / "travel_log.json"

# Auf 2 dec gerundet bevor an DB/API weitergereicht (siehe utils.anonymize)
HOME_LAT, HOME_LON = (
    round_coords(_cfg.home_lat, _cfg.home_lon)
    if _cfg.home_lat is not None and _cfg.home_lon is not None
    else (_cfg.home_lat, _cfg.home_lon)
)
HOME_NAME = _cfg.home_name



# ── Helpers ───────────────────────────────────────────────────────────────────
def now_local() -> datetime:
    utc = datetime.now(timezone.utc)
    y = utc.year
    mar = datetime(y,3,31) - timedelta(days=datetime(y,3,31).weekday()+1)
    oct = datetime(y,10,31) - timedelta(days=datetime(y,10,31).weekday()+1)
    offset = 2 if mar <= utc.replace(tzinfo=None) < oct else 1
    return (utc + timedelta(hours=offset)).replace(tzinfo=None)


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        print(t(f"Keine HA-Konfiguration: {CONFIG_PATH}",
                f"No HA configuration: {CONFIG_PATH}"), file=sys.stderr)
        sys.exit(1)
    return json.loads(CONFIG_PATH.read_text())


def ha_get_history(config: dict, entity_id: str,
                   since: datetime, until: datetime) -> list:
    """Fetches state history in 7-day blocks."""
    headers = {
        "Authorization": f"Bearer {config['token']}",
        "Content-Type":  "application/json",
    }
    result = []
    cur = since
    while cur < until:
        end = min(cur + timedelta(days=7), until)
        params = {
            "filter_entity_id": entity_id,
            "end_time":         end.isoformat(),
            "minimal_response": "false",
            "no_attributes":    "false",
        }
        try:
            r = requests.get(
                f"{config['url']}/api/history/period/{urllib.parse.quote(cur.isoformat())}",
                headers=headers, params=params, timeout=30)
            r.raise_for_status()
            data = r.json()
            if data and data[0]:
                result.extend(data[0])
        except Exception as e:
            print(t(f"  History-Fehler: {e}", f"  History error: {e}"), file=sys.stderr)
        cur = end
    return result


def ha_get_zones(config: dict) -> dict:
    """Returns all HA zones: entity_id → {lat, lon, name}."""
    headers = {
        "Authorization": f"Bearer {config['token']}",
        "Content-Type":  "application/json",
    }
    zones = {}
    try:
        r = requests.get(f"{config['url']}/api/states", headers=headers, timeout=15)
        for s in r.json():
            if not s["entity_id"].startswith("zone."):
                continue
            a = s.get("attributes", {})
            if a.get("latitude"):
                zones[s["entity_id"]] = {
                    "lat":  a["latitude"],
                    "lon":  a["longitude"],
                    "name": a.get("friendly_name", s["entity_id"]),
                }
    except Exception:
        pass
    zones.setdefault("zone.home", {"lat": HOME_LAT, "lon": HOME_LON, "name": HOME_NAME})
    return zones


def ha_get_state(config: dict, entity_id: str) -> dict:
    headers = {
        "Authorization": f"Bearer {config['token']}",
        "Content-Type":  "application/json",
    }
    r = requests.get(
        f"{config['url']}/api/states/{entity_id}",
        headers=headers, timeout=15)
    r.raise_for_status()
    return r.json()


def geocode_city(city: str) -> tuple[float, float] | None:
    """Open-Meteo geocoding — no API key required."""
    try:
        r = requests.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": city, "count": 1, "language": "en", "format": "json"},
            timeout=10)
        results = r.json().get("results", [])
        if results:
            return results[0]["latitude"], results[0]["longitude"]
    except Exception:
        pass
    return None


def reverse_geocode(lat: float, lon: float) -> str | None:
    """Nominatim (OpenStreetMap) — no API key, max 1 req/s."""
    rlat, rlon = round_coords(lat, lon)
    try:
        r = requests.get(
            "https://nominatim.openstreetmap.org/reverse",
            params={"lat": rlat, "lon": rlon, "format": "json", "zoom": 10},
            headers={"User-Agent": "health-tracker/1.0"},
            timeout=10)
        data = r.json()
        addr = data.get("address", {})
        city = (addr.get("city") or addr.get("town") or
                addr.get("village") or addr.get("county") or "")
        state = addr.get("state", "")
        return f"{city}, {state}" if city and state else city or state or None
    except Exception:
        return None


# ── Database ─────────────────────────────────────────────────────────────────
def setup_db(conn: sqlite3.Connection):
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS location_history (
        datetime     TEXT PRIMARY KEY,
        date         TEXT NOT NULL,
        hour         INTEGER,
        state        TEXT,        -- 'home' / 'not_home' / zone-name
        lat          REAL,
        lon          REAL,
        gps_accuracy REAL,
        zone         TEXT,
        city         TEXT,
        source       TEXT DEFAULT 'ha_iphone'
    );
    CREATE INDEX IF NOT EXISTS idx_loc_date ON location_history(date);
    CREATE INDEX IF NOT EXISTS idx_loc_state ON location_history(state);
    """)
    conn.commit()


def last_recorded(conn: sqlite3.Connection) -> str | None:
    r = conn.execute("SELECT MAX(datetime) FROM location_history").fetchone()
    return r[0] if r and r[0] else None


def last_location(conn: sqlite3.Connection) -> tuple | None:
    r = conn.execute(
        "SELECT lat, lon FROM location_history ORDER BY datetime DESC LIMIT 1").fetchone()
    return r if r else None


# ── Core logic ────────────────────────────────────────────────────────────────
def record_location(conn: sqlite3.Connection, config: dict,
                    verbose: bool = True) -> dict | None:
    now = now_local()
    dt_str   = now.strftime("%Y-%m-%d %H:%M:%S")
    date_str = now.strftime("%Y-%m-%d")

    tracker = None
    for attempt, wait in enumerate([0, 30, 90]):
        if wait:
            import time
            if verbose:
                print(t(f"HA nicht erreichbar, Retry {attempt}/2 in {wait}s ...",
                        f"HA unreachable, retry {attempt}/2 in {wait}s ..."), file=sys.stderr)
            time.sleep(wait)
        try:
            tracker = ha_get_state(config, config["device_trackers"]["iphone"])
            break
        except Exception:
            if attempt == 2:
                last = conn.execute(
                    "SELECT state, lat, lon, city FROM location_history "
                    "ORDER BY datetime DESC LIMIT 1").fetchone()
                if last and last[0] == "home":
                    conn.execute("""
                        INSERT OR IGNORE INTO location_history
                        (datetime, date, hour, state, lat, lon, city, source)
                        VALUES (?,?,?,?,?,?,?,'ha_fallback')""",
                        (dt_str, date_str, now.hour,
                         "home", last[1], last[2], last[3]))
                    conn.commit()
                    if verbose:
                        print(t(f"[{dt_str}] HA offline — home fortgeschrieben (Fallback)",
                                f"[{dt_str}] HA offline — home carried forward (fallback)"),
                              file=sys.stderr)
                else:
                    if verbose:
                        print(t(f"[{dt_str}] HA offline, letzter State nicht home — übersprungen",
                                f"[{dt_str}] HA offline, last state not home — skipped"),
                              file=sys.stderr)
                return None

    attrs = tracker.get("attributes", {})
    state = tracker.get("state", "unknown")
    lat   = attrs.get("latitude")
    lon   = attrs.get("longitude")
    acc   = attrs.get("gps_accuracy")
    zones = attrs.get("in_zones", [])
    zone  = zones[0] if zones else None

    if lat is None or lon is None:
        if verbose:
            print(t(f"Keine GPS-Daten verfügbar (state: {state})",
                    f"No GPS data available (state: {state})"))
        return None

    lat, lon = round_coords(lat, lon)

    if state == "home" or (abs(lat - HOME_LAT) < 0.01 and abs(lon - HOME_LON) < 0.01):
        city = HOME_NAME
    else:
        prev = last_location(conn)
        if prev and abs(prev[0] - lat) < 0.005 and abs(prev[1] - lon) < 0.005:
            r = conn.execute(
                "SELECT city FROM location_history ORDER BY datetime DESC LIMIT 1").fetchone()
            city = r[0] if r else None
        else:
            city = reverse_geocode(lat, lon)

    conn.execute("""
        INSERT OR IGNORE INTO location_history
        (datetime, date, hour, state, lat, lon, gps_accuracy, zone, city)
        VALUES (?,?,?,?,?,?,?,?,?)""",
        (dt_str, date_str, now.hour, state, lat, lon, acc, zone, city))
    conn.commit()

    if verbose:
        loc_str = city or f"{lat:.2f},{lon:.2f}"
        print(f"[{dt_str}] {state} | {loc_str} | GPS ±{acc}m")

    return {"datetime": dt_str, "state": state, "lat": lat, "lon": lon, "city": city}


def backfill_from_ha(conn: sqlite3.Connection, config: dict,
                     verbose: bool = True) -> int:
    """Fills gaps in location_history from HA person history."""
    last = last_recorded(conn)
    if last:
        since_local = datetime.strptime(last, "%Y-%m-%d %H:%M:%S")
    else:
        since_local = now_local() - timedelta(days=90)

    gap_hours = (now_local() - since_local).total_seconds() / 3600
    if gap_hours < 4:
        if verbose:
            print(t(f"  Lücke nur {gap_hours:.1f}h — kein Backfill nötig.",
                    f"  Gap only {gap_hours:.1f}h — no backfill needed."))
        return 0

    if verbose:
        print(t(f"  Lücke: {gap_hours/24:.1f} Tage seit {since_local.strftime('%Y-%m-%d %H:%M')}",
                f"  Gap: {gap_hours/24:.1f} days since {since_local.strftime('%Y-%m-%d %H:%M')}"))
        print(t("  Lese HA Zone-History ...", "  Reading HA zone history ..."))

    y = since_local.year
    mar = datetime(y,3,31) - timedelta(days=datetime(y,3,31).weekday()+1)
    oct = datetime(y,10,31) - timedelta(days=datetime(y,10,31).weekday()+1)
    offset = 2 if mar <= since_local < oct else 1
    since_utc = since_local - timedelta(hours=offset)
    since_utc = since_utc.replace(tzinfo=timezone.utc)
    until_utc = datetime.now(timezone.utc)

    import time
    zones   = {}
    history = []
    for attempt, wait in enumerate([0, 30, 120]):
        if wait:
            if verbose:
                print(t(f"  HA nicht erreichbar, Retry {attempt}/2 in {wait}s ...",
                        f"  HA unreachable, retry {attempt}/2 in {wait}s ..."))
            time.sleep(wait)
        try:
            zones   = ha_get_zones(config)
            history = ha_get_history(config, config["device_trackers"]["person"], since_utc, until_utc)
            break
        except Exception:
            if attempt == 2:
                if verbose:
                    print(t("  HA nach 3 Versuchen nicht erreichbar — Backfill übersprungen.",
                            "  HA unreachable after 3 attempts — backfill skipped."))
                    print(t("  Wird beim nächsten Start oder manuell nachgeholt.",
                            "  Will be retried on next run or manually."))
                return 0

    if not history:
        if verbose:
            print(t("  Keine HA-History verfügbar.", "  No HA history available."))
        return 0

    if verbose:
        print(t(f"  {len(history)} State-Änderungen gefunden.",
                f"  {len(history)} state changes found."))

    def ha_ts_to_local(ts: str) -> datetime | None:
        if not ts or len(ts) < 16:
            return None
        try:
            ts_clean = ts.replace("Z", "+00:00")
            dt_utc = datetime.fromisoformat(ts_clean)
            if dt_utc.tzinfo is None:
                dt_utc = dt_utc.replace(tzinfo=timezone.utc)
            dt_naive = datetime(*dt_utc.utctimetuple()[:6])
            y = dt_naive.year
            mar2 = datetime(y,3,31) - timedelta(days=datetime(y,3,31).weekday()+1)
            oct2 = datetime(y,10,31) - timedelta(days=datetime(y,10,31).weekday()+1)
            off  = 2 if mar2 <= dt_naive < oct2 else 1
            return dt_naive + timedelta(hours=off)
        except Exception:
            return None

    segments = []
    for entry in history:
        ts    = entry.get("last_updated") or entry.get("last_changed") or ""
        state = entry.get("state", "unknown")
        attrs = entry.get("attributes", {})
        dt_local = ha_ts_to_local(ts)
        if not dt_local:
            continue

        lat = attrs.get("latitude")
        lon = attrs.get("longitude")

        if lat is None or lon is None:
            zone_entity = f"zone.{state}" if state not in ("home","not_home","unknown") else \
                          ("zone.home" if state == "home" else None)
            if zone_entity and zone_entity in zones:
                lat = zones[zone_entity]["lat"]
                lon = zones[zone_entity]["lon"]
            elif state == "home":
                lat, lon = HOME_LAT, HOME_LON
            else:
                lat, lon = None, None

        segments.append((dt_local, state, lat, lon))

    if not segments:
        return 0

    existing_ts = {r[0] for r in conn.execute(
        "SELECT datetime FROM location_history WHERE datetime >= ?",
        (since_local.strftime("%Y-%m-%d %H:%M:%S"),))}

    rows = []
    geocache: dict[tuple, str] = {}

    for i, (seg_start, state, lat, lon) in enumerate(segments):
        seg_end = segments[i+1][0] if i+1 < len(segments) else now_local()

        slot = seg_start.replace(minute=0, second=0, microsecond=0)
        if slot < seg_start:
            slot += timedelta(hours=1)

        if lat is not None and lon is not None:
            lat_r, lon_r = round_coords(lat, lon)
        else:
            lat_r, lon_r = None, None

        while slot < seg_end:
            dt_str = slot.strftime("%Y-%m-%d %H:%M:%S")
            if dt_str not in existing_ts:
                city = None
                if state == "home" or (lat_r is not None and abs(lat_r - HOME_LAT) < 0.01):
                    city = HOME_NAME
                elif lat_r is not None and lon_r is not None:
                    key = (lat_r, lon_r)
                    if key not in geocache:
                        geocache[key] = reverse_geocode(lat_r, lon_r) or f"{lat_r:.2f},{lon_r:.2f}"
                        if verbose and geocache[key] != HOME_NAME:
                            print(t(f"  Geocodiert: {geocache[key]}",
                                    f"  Geocoded: {geocache[key]}"))
                    city = geocache[key]

                rows.append((
                    dt_str, slot.strftime("%Y-%m-%d"), slot.hour,
                    state, lat_r, lon_r, None,
                    f"zone.{state}" if state == "home" else None,
                    city, "ha_backfill"
                ))
                existing_ts.add(dt_str)
            slot += timedelta(hours=1)

    if rows:
        conn.executemany("""
            INSERT OR IGNORE INTO location_history
            (datetime, date, hour, state, lat, lon, gps_accuracy, zone, city, source)
            VALUES (?,?,?,?,?,?,?,?,?,?)""", rows)
        conn.commit()

    if verbose:
        print(t(f"  {len(rows)} Einträge rückwirkend eingefügt.",
                f"  {len(rows)} entries backfilled."))

    return len(rows)


# ── Travel log ────────────────────────────────────────────────────────────────
def load_travel_log() -> dict:
    """
    Format:
    {
      "periods": [
        {"from":"YYYY-MM-DD","to":"YYYY-MM-DD","city":"Cityname","lat":0.0,"lon":0.0,"note":"Trip"}
      ],
      "days": {
        "YYYY-MM-DD": {"city":"Cityname","lat":0.0,"lon":0.0}
      }
    }
    Legacy flat format (days only) is automatically migrated.
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


def save_travel_log(data: dict):
    TRAVEL_LOG.parent.mkdir(parents=True, exist_ok=True)
    TRAVEL_LOG.write_text(json.dumps(data, indent=2, ensure_ascii=False))


def travel_coords_for_date(date: str) -> tuple[float, float, str] | None:
    """Returns (lat, lon, city) for a date if a travel entry matches. days > periods."""
    data = load_travel_log()

    if date in data["days"]:
        e = data["days"][date]
        return e["lat"], e["lon"], e.get("city", f"{e['lat']:.2f},{e['lon']:.2f}")

    for p in data["periods"]:
        if p["from"] <= date <= p["to"]:
            return p["lat"], p["lon"], p.get("city", f"{p['lat']:.2f},{p['lon']:.2f}")

    return None


def travel_add(city: str, date_from: str, date_to: str | None, note: str | None):
    date_to = date_to or date_from
    print(t(f"Geocodiere '{city}' ...", f"Geocoding '{city}' ..."))
    coords = geocode_city(city)
    if not coords:
        print(t("Geocodierung fehlgeschlagen. Bitte --lat/--lon manuell angeben.",
                "Geocoding failed. Please provide --lat/--lon manually."))
        return
    lat, lon = round_coords(coords[0], coords[1])
    print(f"  → {lat:.2f}, {lon:.2f}")

    data = load_travel_log()

    if date_from == date_to:
        data["days"][date_from] = {"city": city, "lat": lat, "lon": lon}
        if note:
            data["days"][date_from]["note"] = note
        print(t(f"Eintrag gespeichert: {date_from} → {city}",
                f"Entry saved: {date_from} → {city}"))
    else:
        entry = {"from": date_from, "to": date_to, "city": city, "lat": lat, "lon": lon}
        if note:
            entry["note"] = note
        data["periods"] = [p for p in data["periods"]
                           if not (p["from"] <= date_to and p["to"] >= date_from
                                   and p["city"] == city)]
        data["periods"].append(entry)
        data["periods"].sort(key=lambda p: p["from"])
        days = (datetime.strptime(date_to, "%Y-%m-%d") -
                datetime.strptime(date_from, "%Y-%m-%d")).days + 1
        print(t(f"Zeitraum gespeichert: {date_from} → {date_to} ({days} Tage) | {city}",
                f"Period saved: {date_from} → {date_to} ({days} days) | {city}"))

    save_travel_log(data)


def travel_list():
    data = load_travel_log()
    today = now_local().strftime("%Y-%m-%d")

    if not data["periods"] and not data["days"]:
        print(t("Keine Reise-Einträge vorhanden.",
                "No travel entries found."))
        print(t("Tipp: python3 track_location.py --travel-add \"Stadtname\" --from YYYY-MM-DD --to YYYY-MM-DD",
                "Tip: python3 track_location.py --travel-add \"Cityname\" --from YYYY-MM-DD --to YYYY-MM-DD"))
        return

    print(f"\n{t('Reise-Log', 'Travel log')} ({TRAVEL_LOG}):\n")

    if data["periods"]:
        print(t("Zeiträume:", "Periods:"))
        for p in sorted(data["periods"], key=lambda x: x["from"]):
            days = (datetime.strptime(p["to"], "%Y-%m-%d") -
                    datetime.strptime(p["from"], "%Y-%m-%d")).days + 1
            active = t(" ← heute", " ← today") if p["from"] <= today <= p["to"] else ""
            note   = f"  [{p['note']}]" if p.get("note") else ""
            print(f"  {p['from']} – {p['to']}  ({days}d)  {p['city']}{note}{active}")

    if data["days"]:
        print(t("\nEinzeltage:", "\nSingle days:"))
        for date, e in sorted(data["days"].items()):
            active = t(" ← heute", " ← today") if date == today else ""
            note   = f"  [{e['note']}]" if e.get("note") else ""
            print(f"  {date}  {e['city']}{note}{active}")


def travel_remove(date: str):
    data = load_travel_log()
    removed = False

    if date in data["days"]:
        del data["days"][date]
        print(t(f"Einzeltag {date} entfernt.", f"Single-day entry {date} removed."))
        removed = True

    before = len(data["periods"])
    data["periods"] = [p for p in data["periods"]
                       if not (p["from"] <= date <= p["to"])]
    if len(data["periods"]) < before:
        print(t(f"Zeitraum(e) die {date} enthalten entfernt.",
                f"Period(s) containing {date} removed."))
        removed = True

    if not removed:
        print(t(f"Kein Eintrag für {date} gefunden.",
                f"No entry found for {date}."))
    else:
        save_travel_log(data)


def show_history(conn: sqlite3.Connection, days: int = 7):
    print(t(f"\nStandort-Verlauf (letzte {days} Tage):\n",
            f"\nLocation history (last {days} days):\n"))
    since = (now_local() - timedelta(days=days)).strftime("%Y-%m-%d")
    rows = conn.execute("""
        SELECT date, state, city,
               ROUND(lat,4) lat, ROUND(lon,4) lon,
               COUNT(*) n,
               MIN(datetime) first, MAX(datetime) last
        FROM location_history
        WHERE date >= ?
        GROUP BY date, state, city
        ORDER BY date DESC, n DESC""", (since,)).fetchall()

    cur_date = None
    for r in rows:
        if r[0] != cur_date:
            cur_date = r[0]
            print(f"  {cur_date}")
        loc = r[2] or f"{r[3]},{r[4]}"
        print(f"    {r[1]:<10} {loc:<30} {r[5]:>2}× ({r[6][11:16]}–{r[7][11:16]})")


def show_today(conn: sqlite3.Connection):
    today = now_local().strftime("%Y-%m-%d")
    rows = conn.execute("""
        SELECT datetime, state, city, lat, lon, gps_accuracy
        FROM location_history WHERE date=? ORDER BY datetime""", (today,)).fetchall()
    if not rows:
        print(t("Heute noch keine Einträge.", "No entries for today yet."))
        return
    print(f"\n{t('Heute', 'Today')} ({today}):")
    for r in rows:
        loc = r[2] or f"{r[3]:.4f},{r[4]:.4f}"
        print(f"  {r[0][11:16]}  {r[1]:<10}  {loc}")


def main():
    parser = argparse.ArgumentParser(
        description=t("iPhone-Standort-Tracker via HA", "iPhone location tracker via HA"),
        formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("--history",      action="store_true",
                        help=t("Letzte 7 Tage anzeigen", "Show last 7 days"))
    parser.add_argument("--days",         type=int, default=7,
                        help=t("Tage für --history", "Days for --history"))
    parser.add_argument("--today",        action="store_true",
                        help=t("Heutigen Tag anzeigen", "Show today"))
    parser.add_argument("--backfill",     action="store_true",
                        help=t("Lücken aus HA-History schließen", "Fill gaps from HA history"))
    parser.add_argument("--quiet",        action="store_true",
                        help=t("Keine Ausgabe", "Suppress output"))
    parser.add_argument("--travel-add",   metavar="CITY",
                        help=t("Reise eintragen (z.B. 'Paris')", "Add travel entry (e.g. 'Paris')"))
    parser.add_argument("--from",         dest="date_from", metavar="YYYY-MM-DD",
                        help=t("Startdatum", "Start date"))
    parser.add_argument("--to",           dest="date_to",   metavar="YYYY-MM-DD",
                        help=t("Enddatum (optional)", "End date (optional)"))
    parser.add_argument("--note",         metavar="TEXT",
                        help=t("Notiz zum Reise-Eintrag", "Note for travel entry"))
    parser.add_argument("--lat",          type=float,
                        help=t("Breitengrad (wenn Geocoding fehlschlägt)", "Latitude (if geocoding fails)"))
    parser.add_argument("--lon",          type=float,
                        help=t("Längengrad (wenn Geocoding fehlschlägt)", "Longitude (if geocoding fails)"))
    parser.add_argument("--travel-list",  action="store_true",
                        help=t("Alle Reise-Einträge anzeigen", "Show all travel entries"))
    parser.add_argument("--travel-remove", metavar="YYYY-MM-DD",
                        help=t("Eintrag für Datum entfernen", "Remove entry for date"))
    add_lang_arg(parser)
    args = parser.parse_args()
    apply_lang_from_args(args)

    if args.travel_list:
        travel_list()
        return

    if args.travel_remove:
        travel_remove(args.travel_remove)
        return

    if args.travel_add:
        if not args.date_from:
            parser.error(t("--travel-add benötigt --from YYYY-MM-DD",
                           "--travel-add requires --from YYYY-MM-DD"))
        city = args.travel_add
        if args.lat and args.lon:
            data = load_travel_log()
            date_to = args.date_to or args.date_from
            lat_r, lon_r = round_coords(args.lat, args.lon)
            entry = {"city": city, "lat": lat_r, "lon": lon_r}
            if args.note:
                entry["note"] = args.note
            if args.date_from == date_to:
                data["days"][args.date_from] = entry
            else:
                data["periods"].append({"from": args.date_from, "to": date_to, **entry})
                data["periods"].sort(key=lambda p: p["from"])
            save_travel_log(data)
            print(t(f"Gespeichert: {city} ({lat_r:.2f}, {lon_r:.2f})",
                    f"Saved: {city} ({lat_r:.2f}, {lon_r:.2f})"))
        else:
            travel_add(city, args.date_from, args.date_to, args.note)
        return

    conn = open_db()
    setup_db(conn)

    if args.history:
        show_history(conn, args.days)
        conn.close()
        return

    if args.today:
        show_today(conn)
        conn.close()
        return

    config = load_config()

    if args.backfill:
        backfill_from_ha(conn, config, verbose=True)
        conn.close()
        return

    last = last_recorded(conn)
    if last:
        gap_h = (now_local() - datetime.strptime(last, "%Y-%m-%d %H:%M:%S")).total_seconds() / 3600
        if gap_h > 4:
            if not args.quiet:
                print(t(f"Lücke {gap_h:.0f}h — backfill ...",
                        f"Gap {gap_h:.0f}h — backfilling ..."))
            backfill_from_ha(conn, config, verbose=not args.quiet)

    record_location(conn, config, verbose=not args.quiet)
    conn.close()


if __name__ == "__main__":
    main()
