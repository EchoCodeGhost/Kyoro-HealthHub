#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Umweltdaten für Reiseaufenthalte → health.db (air_quality, pollen, biometeo)

@tier infrastructure
@purpose.de Rückwirkender Import von Umweltdaten (Luftqualität, Pollen, Biometeorologie)
           für Reiseaufenthalte zur Korrelationsanalyse mit gesundheitlichen Symptomen
@purpose.en Retrospective import of environmental data (air quality, pollen, biometeorology)
           for travel stays to enable correlation analysis with health symptoms
@method.de Aggregiert Aufenthaltsdaten aus travel_history.json, location_stays (DB) und
           GPS-Trainings-Tracks. Für jeden Nicht-Heim-Aufenthalt werden historische
           Umweltdaten von Open-Meteo (Luftqualität, Pollen, Biometeo) und
           optional AEMET (Spanien) abgerufen und in die DB geschrieben.
           Daten werden in die regulären Tabellen (air_quality, pollen, biometeo) gespeichert.
@method.en Aggregate stay data from travel_history.json, location_stays (DB) and
           GPS training tracks. For each non-home stay, historical environmental data
           is fetched from Open-Meteo (air quality, pollen, biometeorology) and
           optionally AEMET (Spain) and stored in the DB.
           Data is stored in regular tables (air_quality, pollen, biometeo).
@reads ~/Kyoro-HealthHub/.config/kyoro/travel_history.json,
       health.db:location_stays, health.db:location_stays_geocoded,
       health.db:sessions, health.db:session_tracks
@writes health.db:air_quality, health.db:pollen, health.db:biometeo, health.db:import_log
@limits.de Erfordert Internetverbindung für API-Abfragen.
           Koordinatenauflösung für Aufenthalte ohne GPS-Daten via Nominatim.
           AEMET erfordert API-Key (kostenlos, aber manuelle Registrierung).
           Aufenthalte < 2 km vom Heim werden übersprungen.
@limits.en Requires internet connection for API queries.
           Coordinate resolution for stays without GPS data via Nominatim.
           AEMET requires API key (free, but manual registration).
           Stays < 2 km from home are skipped.
@usage python3 import_travel_environment.py                   # alle Aufenthalte
       python3 import_travel_environment.py --from 2022-01-01
       python3 import_travel_environment.py --sources travel  # nur travel_history
       python3 import_travel_environment.py --dry-run
       python3 import_travel_environment.py --force           # vorhandene überschreiben
@refs Open-Meteo API: https://open-meteo.com/en/docs
      AEMET OpenData: https://opendata.aemet.es/


@relevance.de  Ermöglicht den Import von Umweltdaten, essentiell für die Analyse von Umweltfaktoren
@relevance.en  Enables import of environmental data, essential for environmental factor analysis
@relevance.de  Ermöglicht den Import von Umweltdaten, essentiell für die Analyse von Umweltfaktoren
@relevance.en  Enables import of environmental data, essential for environmental factor analysis
"""
import argparse
import json
import sqlite3
import sys
import time
import urllib.parse
import urllib.request
from datetime import date
from math import radians, sin, cos, sqrt, asin
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from health_config import Config as _Cfg, KYORO_CONFIG_DIR
from modules.db import open_db, DB_OPERATIONAL_ERRORS
from modules.base import ImportResult, log_import, resolve_person
from utils.anonymize import round_coords
from modules.i18n import t, set_lang, add_lang_arg, apply_lang_from_args

_cfg = _Cfg()
TRAVEL_FILE      = KYORO_CONFIG_DIR / "travel_history.json"
# Zweite Reise-Quelle: das von track_location.py --travel-add gepflegte Log.
# Beide Dateien existieren historisch nebeneinander und haben unterschiedliche
# Formate; fetch_daily.py liest nur travel_log.json, dieser Importer las bisher
# nur travel_history.json. Ein ueber die CLI eingetragener Aufenthalt war damit
# fuer den Umwelt-Backfill unsichtbar. Jetzt werden beide gelesen.
TRAVEL_LOG_FILE  = KYORO_CONFIG_DIR / "travel_log.json"
GEO_CACHE_FILE   = Path.home() / ".cache" / "kyoro_geocode.json"
HOME_SKIP_KM     = 2.0     # Aufenthalte < 2 km vom Heim überspringen
DAYTRIP_MAX_KM   = 60.0    # Tagesausflug-Radius (>60 km = echte Reise)

# Länder-/Regions-Zentroide als Fallback wenn travel_history keine lat/lon hat
_COUNTRY_CENTROIDS: dict[str, tuple[float, float]] = {
    "DE": (51.2, 10.5), "ES": (40.4, -3.7), "FR": (46.2, 2.2),
    "IT": (42.8, 12.8), "AT": (47.5, 13.9), "CH": (46.8, 8.2),
    "GB": (54.1, -2.1), "NL": (52.1, 5.3),  "BE": (50.5, 4.5),
    "PL": (51.9, 19.1), "CZ": (49.8, 15.5), "SK": (48.7, 19.7),
    "HU": (47.2, 19.5), "RO": (45.9, 24.9), "BG": (42.7, 25.5),
    "GR": (39.1, 21.8), "HR": (45.1, 15.2), "PT": (39.6, -8.0),
    "TR": (39.0, 35.2), "TH": (15.9, 101.0),"VN": (16.5, 107.5),
    "ID": (-0.8, 113.9),"MY": (4.2, 108.0), "SG": (1.4, 103.8),
    "IN": (20.6, 78.9), "CN": (35.9, 104.2),"JP": (36.2, 138.3),
    "AU": (-25.3, 133.8),"NZ": (-41.3, 172.6),"US": (38.0, -97.0),
    "CA": (56.1, -106.3),"MX": (23.6, -102.5),"BR": (-14.2, -51.9),
    "AR": (-38.4, -63.6),"ZA": (-29.0, 25.1), "EG": (26.8, 30.8),
    "MA": (31.8, -7.1),  "TN": (33.9, 9.6),   "KE": (-0.0, 37.9),
}

# Bekannte spanische Subregionen → Koordinaten (wichtig für AQ/UV-Genauigkeit)
_ES_SUBREGIONS: dict[str, tuple[float, float]] = {
    "balearen":           (39.7, 3.0),    "mallorca":          (39.7, 3.0),
    "ibiza":              (39.0, 1.4),    "menorca":           (40.0, 4.0),
    "kanarische inseln":  (28.3, -15.6),  "teneriffa":         (28.3, -16.5),
    "gran canaria":       (28.0, -15.6),  "fuerteventura":     (28.4, -14.0),
    "lanzarote":          (29.0, -13.6),
    "costa del azahar":   (39.8, 0.0),    "valencianische":    (39.5, -0.5),
    "costa dorada":       (41.1, 1.2),    "barcelona":         (41.4, 2.2),
    "madrid":             (40.4, -3.7),   "andalusien":        (37.5, -4.5),
    "costa del sol":      (36.7, -4.4),   "malaga":            (36.7, -4.4),
    "costa brava":        (41.8, 3.0),    "galicien":          (42.6, -8.0),
    "sonnenstrand":       (42.7, 27.7),   # Bulgarien
}


# ── Schema-Migration: env-Tabellen auf (date, lat, lon) Compound-PK ──────────

_ENV_TABLES = {
    "air_quality": (
        "CREATE TABLE air_quality ("
        "date TEXT NOT NULL, lat REAL NOT NULL, lon REAL NOT NULL,"
        "pm25_mean REAL, pm25_max REAL, pm10_mean REAL, pm10_max REAL,"
        "no2_mean REAL, no2_max REAL, o3_mean REAL, o3_max REAL,"
        "co_mean REAL, co_max REAL, aqi_eu_mean REAL, aqi_eu_max INTEGER,"
        "dust_mean REAL, dust_max REAL, source TEXT DEFAULT 'open-meteo',"
        "person TEXT NOT NULL DEFAULT 'unknown',"
        "PRIMARY KEY (date, lat, lon))"
    ),
    "pollen": (
        "CREATE TABLE pollen ("
        "date TEXT NOT NULL, lat REAL NOT NULL, lon REAL NOT NULL,"
        "birch REAL, alder REAL, grass REAL, mugwort REAL,"
        "ragweed REAL, olive REAL, source TEXT DEFAULT 'open-meteo',"
        "person TEXT NOT NULL DEFAULT 'unknown',"
        "PRIMARY KEY (date, lat, lon))"
    ),
    "biometeo": (
        "CREATE TABLE biometeo ("
        "date TEXT NOT NULL, lat REAL NOT NULL, lon REAL NOT NULL,"
        "sunshine_h REAL, solar_mj_m2 REAL, uv_index_max REAL,"
        "apparent_temp_mean REAL, apparent_temp_max REAL, apparent_temp_min REAL,"
        "dewpoint_mean REAL, humidity_mean REAL, source TEXT DEFAULT 'open-meteo',"
        "person TEXT NOT NULL DEFAULT 'unknown',"
        "PRIMARY KEY (date, lat, lon))"
    ),
}


def _env_pk_needs_migration(conn: sqlite3.Connection) -> bool:
    """Prüfen ob eine Migration der env-Tabellen auf Compound-PK nötig ist.
    
    @purpose.de Validierung ob air_quality, pollen oder biometeo noch Migration benötigen
    @purpose.en Validate if air_quality, pollen or biometeo need migration
    @method.de Prüft ob Tabellen existieren und ob ihr Primary Key (date, lat, lon) ist
    @method.en Check if tables exist and if their primary key is (date, lat, lon)
    @param conn SQLite-Datenbankverbindung
    @returns True wenn Migration nötig, False sonst
    """
    for tbl in _ENV_TABLES:
        row = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (tbl,)
        ).fetchone()
        if not row:
            return True
        if "PRIMARY KEY (date, lat, lon)" not in (row[0] or ""):
            return True
    return False


def migrate_env_compound_pk(conn: sqlite3.Connection) -> bool:
    """Migration der env-Tabellen auf Compound Primary Key (date, lat, lon).
    
    @purpose.de Einmalige Migration der Umweltdaten-Tabellen für standortspezifische Daten
    @purpose.en One-time migration of environmental data tables for location-specific data
    @method.de Erstellt neue Tabellen mit (date, lat, lon) als Primary Key,
               kopiert Daten aus alten Tabellen, löscht alte Tabellen,
               benennt neue Tabellen um. Views die biometeo referenzieren werden
               angepasst um nach home-Koordinaten zu filtern.
    @method.en Create new tables with (date, lat, lon) as primary key,
               copy data from old tables, drop old tables,
               rename new tables. Views referencing biometeo are adapted
               to filter by home coordinates.
    @param conn SQLite-Datenbankverbindung
    @returns True wenn Migration durchgeführt wurde, False wenn bereits migriert
    """
    if not _env_pk_needs_migration(conn):
        return False

    home_lat = round(_cfg.home_lat or 0, 2)
    home_lon = round(_cfg.home_lon or 0, 2)

    print(t("  [migration] env-Tabellen auf (date, lat, lon) PK migrieren …",
            "  [migration] migrating env tables to (date, lat, lon) PK …"))
    conn.execute("PRAGMA foreign_keys=OFF")

    # Collect and drop views that reference any env table
    views_to_restore: list[tuple[str, str]] = []
    for tbl in _ENV_TABLES:
        rows = conn.execute(
            "SELECT name, sql FROM sqlite_master "
            "WHERE type='view' AND sql LIKE ?",
            (f"%{tbl}%",)
        ).fetchall()
        for vname, vsql in rows:
            if not any(v[0] == vname for v in views_to_restore):
                views_to_restore.append((vname, vsql))
                conn.execute(f"DROP VIEW IF EXISTS {vname}")

    for tbl, new_ddl in _ENV_TABLES.items():
        tmp = f"{tbl}_mig_tmp"
        try:
            tbl_exists = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (tbl,)
            ).fetchone()
            conn.execute(f"DROP TABLE IF EXISTS {tmp}")
            conn.execute(new_ddl.replace(f"CREATE TABLE {tbl}", f"CREATE TABLE {tmp}"))
            if tbl_exists:
                cols_row = conn.execute(f"PRAGMA table_info({tbl})").fetchall()
                cols = [c[1] for c in cols_row]
                col_list = ", ".join(cols)
                conn.execute(
                    f"UPDATE {tbl} SET lat = ?, lon = ? WHERE lat IS NULL OR lon IS NULL",
                    (home_lat, home_lon)
                )
                conn.execute(f"INSERT OR IGNORE INTO {tmp} ({col_list}) SELECT {col_list} FROM {tbl}")
                conn.execute(f"DROP TABLE {tbl}")
            conn.execute(f"ALTER TABLE {tmp} RENAME TO {tbl}")
            print(f"  [migration] {tbl} ✓")
        except Exception as e:
            print(t(f"  [migration] {tbl} Fehler: {e}",
                    f"  [migration] {tbl} error: {e}"))

    # Recreate views, patching biometeo joins to filter by home coordinates.
    # Pattern: "LEFT JOIN biometeo <alias> ON" →
    #          "LEFT JOIN (SELECT * FROM biometeo WHERE lat=X AND lon=Y) <alias> ON"
    import re as _re
    for vname, vsql in views_to_restore:
        patched = _re.sub(
            r'LEFT JOIN\s+biometeo\s+(\w+)\s+ON',
            lambda m: (
                f"LEFT JOIN (SELECT * FROM biometeo WHERE lat={home_lat} "
                f"AND lon={home_lon}) {m.group(1)} ON"
            ),
            vsql
        )
        try:
            conn.execute(f"DROP VIEW IF EXISTS {vname}")
            conn.execute(patched)
            print(t(f"  [migration] view {vname} neu erstellt",
                    f"  [migration] view {vname} recreated"))
        except Exception as e:
            try:
                conn.execute(f"DROP VIEW IF EXISTS {vname}")
                conn.execute(vsql)
                print(t(f"  [migration] view {vname} (original) wiederhergestellt: {e}",
                        f"  [migration] view {vname} (original) restored: {e}"))
            except Exception as e2:
                print(t(f"  [migration] view {vname} Fehler: {e2}",
                        f"  [migration] view {vname} error: {e2}"))

    conn.execute("PRAGMA foreign_keys=ON")
    conn.commit()
    return True


# ── Geo-Hilfsfunktionen ───────────────────────────────────────────────────────

def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Berechnung der Entfernung zwischen zwei Koordinaten in Kilometern (Haversine-Formel).
    
    @purpose.de Distanzberechnung für Heimbereich-Filter und Reise-Erkennung
    @purpose.en Distance calculation for home area filter and travel detection
    @method.de Nutzt Haversine-Formel auf einer Kugel mit Radius 6371 km.
               Gibt unendlich zurück wenn eine Koordinate None ist.
    @method.en Use Haversine formula on a sphere with radius 6371 km.
               Returns infinity if any coordinate is None.
    @param lat1 Breitengrad Punkt 1
    @param lon1 Längengrad Punkt 1
    @param lat2 Breitengrad Punkt 2
    @param lon2 Längengrad Punkt 2
    @returns Entfernung in Kilometern
    """
    if None in (lat1, lon1, lat2, lon2):
        return float("inf")
    R = 6371.0
    p1, p2 = radians(lat1), radians(lat2)
    dp = radians(lat2 - lat1)
    dl = radians(lon2 - lon1)
    a  = sin(dp/2)**2 + cos(p1)*cos(p2)*sin(dl/2)**2
    return 2 * R * asin(sqrt(max(0, a)))


def _resolve_coords(stay: dict) -> tuple[float, float] | tuple[None, None]:
    """Auflösung von Aufenthalts-Koordinaten aus verschiedenen Quellen.
    
    @purpose.de Bestimmung von Koordinaten für Aufenthalte ohne explizite GPS-Daten
    @purpose.en Determine coordinates for stays without explicit GPS data
    @method.de Versucht Koordinaten in dieser Reihenfolge zuitteln:
               1. Explizite lat/lon im Stay
               2. Subregions-Lookup (v.a. für Spanien)
               3. Länder-Zentroid aus country_iso
               4. Nominatim-Geocoding-Suche
    @method.en Try to resolve coordinates in this order:
               1. Explicit lat/lon in stay
               2. Subregion lookup (especially for Spain)
               3. Country centroid from country_iso
               4. Nominatim geocoding search
    @param stay Aufenthalts-Dictionary mit optional lat, lon, subregion, country_iso
    @returns Tuple aus (lat, lon) oder (None, None) bei Fehlschlag
    """
    lat = stay.get("lat")
    lon = stay.get("lon")
    if lat is not None and lon is not None:
        return float(lat), float(lon)

    # Subregions-Lookup (v.a. für Spanien)
    subregion = (stay.get("subregion") or "").lower()
    if subregion:   # leerer String würde "" in key → immer True ergeben
        for key, coords in _ES_SUBREGIONS.items():
            if key in subregion or subregion in key:
                return coords

    # Länder-Zentroid
    iso = (stay.get("country_iso") or "").upper()
    if iso in _COUNTRY_CENTROIDS:
        return _COUNTRY_CENTROIDS[iso]

    # Nominatim-Suche als letzter Ausweg
    query = stay.get("subregion") or stay.get("country") or ""
    if not query:
        return None, None
    try:
        cache = json.loads(GEO_CACHE_FILE.read_text("utf-8")) \
                if GEO_CACHE_FILE.exists() else {}
        cache_key = f"search:{query}"
        if cache_key in cache:
            r = cache[cache_key]
            return r.get("lat"), r.get("lon")
        params = urllib.parse.urlencode(
            {"q": query, "format": "json", "limit": 1}
        )
        req = urllib.request.Request(
            f"https://nominatim.openstreetmap.org/search?{params}",
            headers={"User-Agent": "Kyoro-HealthHub/1.0"},
        )
        with urllib.request.urlopen(req, timeout=8) as r:
            results = json.loads(r.read().decode())
        if results:
            lat = float(results[0]["lat"])
            lon = float(results[0]["lon"])
            cache[cache_key] = {"lat": lat, "lon": lon}
            GEO_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
            GEO_CACHE_FILE.write_text(
                json.dumps(cache, ensure_ascii=False, indent=2), "utf-8"
            )
            time.sleep(1.1)
            return lat, lon
    except Exception:
        pass
    return None, None


# ── Aufenthaltsdaten laden ────────────────────────────────────────────────────

def _load_travel_history(dfrom: str | None = None) -> list[dict]:
    if dfrom is None:
        dfrom = _cfg.birthdate or "1900-01-01"
    if not TRAVEL_FILE.exists():
        return []
    try:
        entries = json.loads(TRAVEL_FILE.read_text("utf-8"))
    except Exception:
        return []
    result = []
    for e in entries:
        d0 = e.get("date_from", "")[:10]
        d1 = e.get("date_to", d0)[:10]
        if not d0 or d0 < dfrom:
            continue
        lat = e.get("lat") or e.get("_lat")
        lon = e.get("lon") or e.get("_lon")
        result.append({
            "date_from":   d0,
            "date_to":     d1,
            "lat":         lat,
            "lon":         lon,
            "country":     e.get("country"),
            "country_iso": e.get("country_iso"),
            "subregion":   e.get("subregion"),
            "label":       (e.get("name") or e.get("subregion")
                            or e.get("country") or "?"),
            "source":      "travel_history",
        })
    return result


def _load_travel_log(dfrom: str | None = None) -> list[dict]:
    """
    Reise-Eintraege aus travel_log.json (track_location.py --travel-add).

    @purpose.de Macht ueber die CLI gepflegte Aufenthalte fuer den Umwelt-Backfill
                sichtbar — sie standen bisher nur fetch_daily.py zur Verfuegung.
    @purpose.en Exposes stays maintained via the CLI to the environment backfill —
                previously only fetch_daily.py could see them.
    @method.de  Liest die Struktur {"periods": [{from,to,lat,lon,city}],
                "days": {datum: {lat,lon,city}}} und normalisiert sie auf dasselbe
                Format wie _load_travel_history().
    @method.en  Reads {"periods": [...], "days": {...}} and normalises it to the
                same shape as _load_travel_history().

    Args:
        dfrom: frühestes zu beruecksichtigendes Datum (YYYY-MM-DD)

    Returns:
        Liste normalisierter Reise-Eintraege
    """
    if dfrom is None:
        dfrom = _cfg.birthdate or "1900-01-01"
    if not TRAVEL_LOG_FILE.exists():
        return []
    try:
        data = json.loads(TRAVEL_LOG_FILE.read_text("utf-8"))
    except Exception:
        return []
    if not isinstance(data, dict):
        return []

    raw: list[tuple[str, str, dict]] = []
    for p in data.get("periods", []) or []:
        if isinstance(p, dict) and p.get("from"):
            raw.append((p["from"][:10], p.get("to", p["from"])[:10], p))
    for day, e in (data.get("days", {}) or {}).items():
        if isinstance(e, dict):
            raw.append((day[:10], day[:10], e))

    result = []
    for d0, d1, e in raw:
        if not d0 or d0 < dfrom:
            continue
        if e.get("lat") is None or e.get("lon") is None:
            continue
        result.append({
            "date_from":   d0,
            "date_to":     d1,
            "lat":         e["lat"],
            "lon":         e["lon"],
            "country":     e.get("country"),
            "country_iso": e.get("country_iso"),
            "subregion":   e.get("subregion"),
            "label":       e.get("city") or e.get("name") or "?",
            "source":      "travel_log",
        })
    return result


def _load_db_stays(conn: sqlite3.Connection, dfrom: str) -> list[dict]:
    try:
        rows = conn.execute("""
            SELECT ls.start_ts, ls.end_ts, ls.lat, ls.lon,
                   COALESCE(g.country,''), COALESCE(g.country_iso,''),
                   COALESCE(g.city, g.subregion, '')
            FROM   location_stays ls
            LEFT JOIN location_stays_geocoded g ON g.stay_id = ls.id
            WHERE  ls.is_home = 0 AND ls.start_ts >= ?
            ORDER  BY ls.start_ts
        """, (dfrom,)).fetchall()
    except DB_OPERATIONAL_ERRORS:
        return []
    result = []
    for r in rows:
        d0 = (r[0] or "")[:10]
        d1 = (r[1] or d0)[:10]
        if not d0:
            continue
        result.append({
            "date_from":   d0,
            "date_to":     d1,
            "lat":         r[2],
            "lon":         r[3],
            "country":     r[4] or None,
            "country_iso": r[5] or None,
            "label":       r[6] or r[5] or "GPS-Stay",
            "source":      "location_stays",
        })
    return result


def _load_gps_daytrips(conn: sqlite3.Connection, dfrom: str,
                       home_lat: float, home_lon: float,
                       min_km: float = HOME_SKIP_KM,
                       max_km: float = DAYTRIP_MAX_KM) -> list[dict]:
    """Training-Sessions mit GPS-Track, deren Zentroid min_km…max_km vom Heim liegt."""
    try:
        rows = conn.execute("""
            SELECT s.date,
                   AVG(st.lat)  AS clat,
                   AVG(st.lon)  AS clon,
                   s.sport
            FROM sessions s
            JOIN session_tracks st ON st.session_id = s.id
            WHERE s.type = 'training' AND s.date >= ?
            GROUP BY s.id
            HAVING clat IS NOT NULL
        """, (dfrom,)).fetchall()
    except DB_OPERATIONAL_ERRORS:
        return []

    result = []
    for d0, clat, clon, sport in rows:
        km = _haversine_km(clat, clon, home_lat, home_lon)
        if not (min_km <= km <= max_km):
            continue
        rlat, rlon = round_coords(clat, clon)
        result.append({
            "date_from":   d0,
            "date_to":     d0,
            "lat":         rlat,
            "lon":         rlon,
            "label":       f"GPS-Ausflug ({sport or '?'}, {km:.1f} km)",
            "source":      "gps_track",
        })
    # Deduplizieren: gleiche (date, ~lat, ~lon) nur einmal
    seen: set[tuple] = set()
    unique = []
    for s in result:
        key = (s["date_from"], round(s["lat"], 1), round(s["lon"], 1))
        if key not in seen:
            seen.add(key)
            unique.append(s)
    return unique


def _all_stays(conn: sqlite3.Connection,
               dfrom: str,
               sources: list[str],
               home_lat: float | None,
               home_lon: float | None) -> list[dict]:
    """Aggregation aller Nicht-Heim-Aufenthalte mit bekannten Koordinaten.
    
    @purpose.de Sammeln aller relevanten Aufenthalte für Umwelt-Datenimport
    @purpose.en Collect all relevant stays for environmental data import
    @method.de Kombiniert Aufenthalte aus travel_history.json, location_stays (DB)
               und GPS-Trainings-Tracks. Filtert Aufenthalte < 2 km vom Heim.
               Löst Koordinaten mit _resolve_coords auf.
    @method.en Combine stays from travel_history.json, location_stays (DB)
               and GPS training tracks. Filter stays < 2 km from home.
               Resolve coordinates with _resolve_coords.
    @param conn SQLite-Datenbankverbindung
    @param dfrom Frühestes Datum (ISO-Format)
    @param sources Liste der Quellen: 'travel', 'db', 'gps', 'all'
    @param home_lat Breitengrad des Heims
    @param home_lon Längengrad des Heims
    @returns Liste von Aufenthalts-Dictionaries mit lat, lon, date_from, date_to
    """
    raw: list[dict] = []
    use_all = "all" in sources
    if use_all or "travel" in sources:
        raw.extend(_load_travel_history(dfrom))
        raw.extend(_load_travel_log(dfrom))
    if use_all or "db" in sources:
        raw.extend(_load_db_stays(conn, dfrom))
    if use_all or "gps" in sources:
        if home_lat and home_lon:
            raw.extend(_load_gps_daytrips(conn, dfrom, home_lat, home_lon))

    result = []
    for stay in raw:
        lat, lon = _resolve_coords(stay)
        if lat is None:
            continue
        if home_lat and home_lon:
            d_km = _haversine_km(lat, lon, home_lat, home_lon)
            if d_km < HOME_SKIP_KM:
                continue
        stay = dict(stay, lat=lat, lon=lon)
        result.append(stay)
    return result


# ── Datenlücken prüfen ────────────────────────────────────────────────────────

def _has_gap(conn: sqlite3.Connection, table: str,
             d_from: str, d_to: str,
             lat: float | None = None, lon: float | None = None) -> bool:
    """Prüfen ob Datenlücken für einen Zeitraum und Standort existieren.
    
    @purpose.de Identifikation von fehlenden Daten für inkrementellen Import
    @purpose.en Identify missing data for incremental import
    @method.de Vergleicht Anzahl bestehender Einträge mit erwarteter Anzahl von Tagen.
               Bei Angabe von lat/lon wird standortspezifisch geprüft.
    @method.en Compare count of existing entries with expected number of days.
               With lat/lon specified, check is location-specific.
    @param conn SQLite-Datenbankverbindung
    @param table Tabellenname (air_quality, pollen oder biometeo)
    @param d_from Startdatum (ISO-Format)
    @param d_to Enddatum (ISO-Format)
    @param lat Breitengrad (optional, für standortspezifische Prüfung)
    @param lon Längengrad (optional, für standortspezifische Prüfung)
    @returns True wenn mindestens ein Tag fehlt, False sonst
    """
    try:
        if lat is not None and lon is not None:
            existing = conn.execute(
                f"SELECT COUNT(*) FROM {table} "
                f"WHERE date >= ? AND date <= ? AND lat = ? AND lon = ?",
                (d_from, d_to, round(lat, 2), round(lon, 2))
            ).fetchone()[0]
        else:
            existing = conn.execute(
                f"SELECT COUNT(*) FROM {table} WHERE date >= ? AND date <= ?",
                (d_from, d_to)
            ).fetchone()[0]
    except DB_OPERATIONAL_ERRORS:
        return True
    expected = (date.fromisoformat(d_to) - date.fromisoformat(d_from)).days + 1
    return existing < expected


# ── Umweltdaten-Fetcher ───────────────────────────────────────────────────────

def _fetch_openmeteo(conn: sqlite3.Connection, stay: dict,
                     force: bool = False, person: str | None = None) -> dict[str, int]:
    """Open-Meteo: Luftqualität + Pollen + Biometeo für einen Aufenthalt."""
    from importers.import_airquality import import_airquality, import_biometeo

    lat = round(stay["lat"], 4)
    lon = round(stay["lon"], 4)
    d0  = stay["date_from"]
    d1  = stay["date_to"]

    counts = {"aq": 0, "pollen": 0, "biometeo": 0}

    # update=True laesst import_airquality nur fehlende DATUMSZEILEN nachladen
    # (_missing prueft auf Zeilenexistenz, nicht auf befuellte Spalten). Bei --force
    # muss deshalb der volle Zeitraum neu geholt werden, sonst bleibt eine bereits
    # vorhandene, aber unvollstaendig befuellte Zeile fuer immer unvollstaendig —
    # genau das war hier der Fall: 122 von 124 Reisezeilen ohne AQI, Ozon und Staub,
    # obwohl die API diese Werte fuer dieselben Orte und Tage liefert.
    if force or _has_gap(conn, "air_quality", d0, d1, lat, lon):
        try:
            aq, pol = import_airquality(conn, lat, lon, d0, d1, update=not force, person=person)
            counts["aq"]     = aq
            counts["pollen"] = pol
        except Exception as e:
            print(t(f"    Open-Meteo AQ-Fehler: {e}",
                    f"    Open-Meteo AQ error: {e}"))
        time.sleep(0.5)

    if force or _has_gap(conn, "biometeo", d0, d1, lat, lon):
        try:
            counts["biometeo"] = import_biometeo(conn, lat, lon, d0, d1,
                                                  update=not force, person=person)
        except Exception as e:
            print(t(f"    Open-Meteo Biometeo-Fehler: {e}",
                    f"    Open-Meteo biometeo error: {e}"))
        time.sleep(0.5)

    return counts


def _fetch_aemet(conn: sqlite3.Connection, stay: dict, person: str | None = None) -> int:
    """AEMET: offizielle spanische Stationsdaten (erfordert API-Key)."""
    try:
        from importers.import_aemet import (
            _get_api_key, _is_spain, fetch_and_import
        )
    except ImportError:
        return 0

    lat = stay["lat"]
    lon = stay["lon"]
    if not _is_spain(lat, lon):
        return 0

    api_key = _get_api_key()
    if not api_key:
        return 0

    try:
        n = fetch_and_import(conn, lat, lon,
                             stay["date_from"], stay["date_to"], person=person)
        return n or 0
    except Exception as e:
        print(t(f"    AEMET-Fehler: {e}",
                f"    AEMET error: {e}"))
        return 0


# ── Haupt-Import ──────────────────────────────────────────────────────────────

def run(conn: sqlite3.Connection | None = None,
        date_from: str | None = None,
        sources: list[str] | None = None,
        force: bool = False,
        dry_run: bool = False,
        lang: str | None = None,
        person: str | None = None) -> ImportResult:
    """Hauptfunktion für den Import von Umweltdaten für Reiseaufenthalte.
    
    @purpose.de Orchestrierung des kompletten Import-Prozesses
    @purpose.en Orchestrate the complete import process
    @method.de Führt Migration durch, lädt Aufenthalte mit _all_stays,
               prüft Datenlücken mit _has_gap, holt fehlende Daten von Open-Meteo
               und optional AEMET (für Spanien). Im dry_run-Modus werden keine Daten
               geschrieben. Im force-Modus werden bestehende Daten überschrieben.
    @method.en Perform migration, load stays with _all_stays,
               check data gaps with _has_gap, fetch missing data from Open-Meteo
               and optionally AEMET (for Spain). In dry_run mode, no data is written.
               In force mode, existing data is overwritten.
    @param conn SQLite-Datenbankverbindung (optional, wird bei None geöffnet)
    @param date_from Frühestes Datum (ISO-Format, optional, Standard: Geburtsdatum —
                     Reise-/Wohnsitzdaten sind lebenszeitbezogen, nicht an
                     clinical.data_start/Wearable-Verfuegbarkeit gebunden)
    @param sources Liste der Aufenthalts-Quellen (optional, Standard: ['all'])
    @param force Vorhandene Daten überschreiben (optional, Standard: False)
    @param dry_run Nur anzeigen was importiert würde (optional, Standard: False)
    @param lang Sprache für i18n (optional)
    @returns ImportResult mit source und rows_inserted
    """
    if lang:
        set_lang(lang)
    person = resolve_person(person)
    if date_from is None:
        date_from = _cfg.birthdate or "1900-01-01"
    sources = sources or ["all"]
    close   = conn is None
    if conn is None:
        conn = open_db()

    # Einmalige Migration auf Compound-PK (kein-op wenn bereits migriert)
    migrate_env_compound_pk(conn)

    home_lat = _cfg._cfg.get("home_lat") or _cfg.home_lat
    home_lon = _cfg._cfg.get("home_lon") or _cfg.home_lon

    stays = _all_stays(conn, date_from, sources, home_lat, home_lon)
    print(t(f"  Aufenthalte mit Koordinaten: {len(stays)}",
            f"  Stays with coordinates: {len(stays)}"))

    if dry_run:
        for s in stays:
            print(f"    [dry-run] {s['date_from']} – {s['date_to']}  "
                  f"{s['label']} ({s['lat']:.2f}, {s['lon']:.2f})")
        if close:
            conn.close()
        return ImportResult(source="travel_environment", rows_inserted=0)

    total_aq = total_bm = total_aemet = 0

    for i, stay in enumerate(stays, 1):
        label   = stay["label"]
        d0, d1  = stay["date_from"], stay["date_to"]
        dur     = (date.fromisoformat(d1) - date.fromisoformat(d0)).days + 1
        iso     = stay.get("country_iso", "")
        spain   = iso == "ES" or (stay["lat"] and stay["lon"]
                                   and -10 < stay["lon"] < 5
                                   and 27 < stay["lat"] < 44)

        print(t(f"\n  [{i}/{len(stays)}] {label}  {d0} – {d1} ({dur}d)"
                + ("  🇪🇸 AEMET" if spain else ""),
                f"\n  [{i}/{len(stays)}] {label}  {d0} – {d1} ({dur}d)"
                + ("  🇪🇸 AEMET" if spain else "")))

        # Open-Meteo (global, immer)
        om = _fetch_openmeteo(conn, stay, force, person)
        if om["aq"] or om["pollen"] or om["biometeo"]:
            print(t(f"    Open-Meteo: AQ={om['aq']} Pollen={om['pollen']} "
                    f"Biometeo={om['biometeo']} neue Tage",
                    f"    Open-Meteo: AQ={om['aq']} Pollen={om['pollen']} "
                    f"Biometeo={om['biometeo']} new days"))
        else:
            print(t("    Open-Meteo: bereits vollständig vorhanden",
                    "    Open-Meteo: already complete"))
        total_aq += om["aq"]
        total_bm += om["biometeo"]

        # AEMET (nur Spanien, wenn API-Key vorhanden)
        if spain:
            n = _fetch_aemet(conn, stay, person)
            if n:
                print(t(f"    AEMET: {n} neue Datensätze",
                        f"    AEMET: {n} new records"))
                total_aemet += n
            time.sleep(0.3)

    total = total_aq + total_bm + total_aemet
    log_import(conn, 'travel_environment', '', total, person=person)
    conn.commit()
    if close:
        conn.close()
    return ImportResult(source="travel_environment", rows_inserted=total)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    """Hauptfunktion für den Reise-Umweltdaten-Import.
    
    @purpose.de CLI-Einstiegspunkt für den Import von Umweltdaten für Reiseaufenthalte
    @purpose.en CLI entry point for importing environmental data for travel stays
    @method.de Parsen von CLI-Argumenten, Aufruf von run() mit den Argumenten,
               Anzeige des Endergebnisses
    @method.en Parse CLI arguments, call run() with the arguments,
               display final result
    """
    ap = argparse.ArgumentParser(
        description="Umweltdaten (AQ, UV, Pollen) für Reiseaufenthalte rückwirkend importieren"
    )
    ap.add_argument("--from",    dest="date_from", default=_cfg.birthdate or "1900-01-01",
                    help="Frühestes Datum (Standard: Geburtsdatum — Reise-/Wohnsitzdaten "
                         "sind lebenszeitbezogen, nicht an clinical.data_start gebunden)")
    ap.add_argument("--sources", nargs="+",
                    choices=["travel", "db", "gps", "all"],
                    default=["all"],
                    help="Aufenthalts-Quellen (Standard: alle; gps=GPS-Trainings-Tracks)")
    ap.add_argument("--force",   action="store_true",
                    help="Vorhandene Tage überschreiben (Standard: nur Lücken füllen)")
    ap.add_argument("--dry-run", action="store_true",
                    help="Nur anzeigen was gefetcht würde, nichts importieren")
    ap.add_argument("--person", default=None, help="Ziel-Person (Default: OWN_PERSON_ID)")
    add_lang_arg(ap)
    args = ap.parse_args()
    apply_lang_from_args(args)

    print(t("Umweltdaten für Reiseaufenthalte importieren …",
            "Importing environment data for travel stays …"))
    result = run(
        date_from = args.date_from,
        sources   = args.sources,
        force     = args.force,
        dry_run   = args.dry_run,
        person    = args.person,
    )
    print(t(f"\nGesamt: {result.rows_inserted} neue Datensätze importiert",
            f"\nTotal: {result.rows_inserted} new records imported"))


if __name__ == "__main__":
    main()
