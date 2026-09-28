#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
import_pollen_google.py — Google Pollen API → health.db

@tier        infrastructure
@purpose.de  Importiert Pollenflugdaten von der Google Maps Platform Pollen API in die health.db
@purpose.en  Imports pollen flight data from Google Maps Platform Pollen API into health.db
@method.de   Verwendet die Google Pollen API (Universal Pollen Index UPI 0-5) für 13 Pollenarten.
             Unterstützte Arten: ALDER, ASH, BIRCH, COTTONWOOD, ELM, GRASS, MAPLE, MUGWORT, OAK, OLIVE, PINE, RAGWEED, WEED.
             Daten werden in die Tabelle pollen_google geschrieben mit Spalten: date, plant_code, upi, category, person.
             Tägliche Ausführung liefert Daten für heute + bis zu 4 Folgetage.
             Historische Daten werden durch regelmäßigen Import aufgebaut.
@method.en   Uses Google Pollen API (Universal Pollen Index UPI 0-5) for 13 pollen types.
             Supported types: ALDER, ASH, BIRCH, COTTONWOOD, ELM, GRASS, MAPLE, MUGWORT, OAK, OLIVE, PINE, RAGWEED, WEED.
             Data is written to pollen_google table with columns: date, plant_code, upi, category, person.
             Daily execution provides data for today + up to 4 following days.
             Historical data is built through regular imports.
@reads       health_config.json (google_pollen_key)
@writes      pollen_google, import_log
@limits.de   Abhaengig von Google API-Verfuegbarkeit und Key-Konfiguration. Keine medizinische Validierung.

@relevance.de  Ermöglicht den Import von Gesundheitsdaten, essentiell für die umfassende Datenanalyse
@relevance.en  Enables import of health data, essential for comprehensive data analysis
@limits.en   Depends on Google API availability and key configuration. No medical validation.
@usage
    python import_pollen_google.py
    python import_pollen_google.py --days 5
    python import_pollen_google.py --lat 48.1 --lon 11.6 --days 3
"""

import argparse
import json
import sqlite3
import sys
import urllib.request
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from health_config import Config as _Cfg, OWN_PERSON_ID as _OWN_PERSON_ID
from modules.db import open_db
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from modules.base import log_import
from utils.anonymize import round_coords

_cfg = _Cfg()
DB_PATH  = _cfg.db_path
HOME_LAT, HOME_LON = (
    round_coords(_cfg.home_lat, _cfg.home_lon)
    if _cfg.home_lat is not None and _cfg.home_lon is not None
    else (_cfg.home_lat, _cfg.home_lon)
)

API_BASE = "https://pollen.googleapis.com/v1/forecast:lookup"

CATEGORY_ORDER = {
    "NONE": 0, "VERY_LOW": 1, "LOW": 2,
    "MEDIUM": 3, "HIGH": 4, "VERY_HIGH": 5,
}


def _get_api_key() -> str | None:
    key = _cfg._cfg.get("google_pollen_key") or _cfg._cfg.get("apis", {}).get("google_pollen_key")
    return key or None


def _fetch_google(api_key: str, lat: float, lon: float, days: int) -> dict:
    rlat, rlon = round_coords(lat, lon)
    url = (f"{API_BASE}?key={api_key}"
           f"&location.latitude={rlat}&location.longitude={rlon}"
           f"&days={days}&languageCode=de")
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"[import_pollen_google] HTTP {e.code}: {body[:200]}", file=sys.stderr)
        return {}
    except Exception as e:
        print(f"[import_pollen_google] Fehler: {e}", file=sys.stderr)
        return {}


def import_pollen_google_from_raw(conn: sqlite3.Connection, data: dict) -> int:
    """Import pollen_google from a pre-fetched Google Pollen API response."""
    cur   = conn.cursor()
    count = 0
    for day_info in data.get("dailyInfo", []):
        d_obj = day_info.get("date", {})
        try:
            day_str = date(d_obj["year"], d_obj["month"], d_obj["day"]).isoformat()
        except (KeyError, ValueError):
            continue
        for plant in day_info.get("pollenTypeInfo", []):
            code  = plant.get("code", "")
            index = plant.get("indexInfo", {})
            upi   = index.get("value")
            cat   = index.get("category")
            if not code:
                continue
            cur.execute(
                "INSERT OR IGNORE INTO pollen_google (date, plant_code, upi, category, person) "
                "VALUES (?, ?, ?, ?, ?)",
                (day_str, code, upi, cat, _OWN_PERSON_ID)
            )
            count += cur.rowcount
    # person=None explizit: regionale Pollendaten (Google API), keine Personendaten (s. add-importer-person-parameterization-remaining)

    log_import(conn, 'pollen_google', '', count, person=None)
    conn.commit()
    return count


def import_pollen_google(conn: sqlite3.Connection,
                         lat: float, lon: float,
                         days: int = 5) -> int:
    api_key = _get_api_key()
    if not api_key:
        print(t(
            "Kein Google Pollen API-Key in health_config.json (google_pollen_key). "
            "Import übersprungen.",
            "No Google Pollen API key in health_config.json (google_pollen_key). "
            "Skipping import."
        ))
        return 0

    data = _fetch_google(api_key, lat, lon, days)
    if not data:
        return 0

    return import_pollen_google_from_raw(conn, data)


def main():
    parser = argparse.ArgumentParser(
        description=t(
            "Google Pollen API → health.db",
            "Google Pollen API → health.db"
        )
    )
    parser.add_argument("--days", type=int, default=5,
                        help="Anzahl Tage (1–5, Standard: 5)")
    parser.add_argument("--lat", type=float, default=HOME_LAT)
    parser.add_argument("--lon", type=float, default=HOME_LON)
    parser.add_argument("--update",  action="store_true", help="Nur neue Daten (No-op, kein API-Key konfiguriert)")
    parser.add_argument("--from",    dest="date_from", metavar="DATE", help="Ignoriert")
    parser.add_argument("--to",      dest="date_to",   metavar="DATE", help="Ignoriert")
    add_lang_arg(parser)
    args = parser.parse_args()
    apply_lang_from_args(args)

    if args.lat is None or args.lon is None:
        parser.error(t(
            "Standort fehlt: --lat/--lon übergeben oder location.lat/lon in health_config.json setzen.",
            "Missing location: pass --lat/--lon or set location.lat/lon in health_config.json."))

    lat_r, lon_r = round_coords(args.lat, args.lon)
    conn = open_db()
    print(t(
        f"Google Pollen API für ({lat_r:.2f}, {lon_r:.2f}), {args.days} Tage ...",
        f"Google Pollen API for ({lat_r:.2f}, {lon_r:.2f}), {args.days} days ..."
    ))

    n = import_pollen_google(conn, lat_r, lon_r, days=args.days)
    print(t(f"  {n} Einträge gespeichert.", f"  {n} entries stored."))
    conn.close()


if __name__ == "__main__":
    main()
