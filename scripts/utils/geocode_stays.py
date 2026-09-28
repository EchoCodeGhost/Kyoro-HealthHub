#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
geocode_stays — Reverse Geocoding für GPS-Aufenthalte und Reisevorschläge

@tier        infrastructure
@purpose.de  Führt Reverse Geocoding für GPS-Koordinaten aus location_stays und session_tracks durch.
              Liest Breiten- und Längengrade, fragt Nominatim (OpenStreetMap, kostenloser Dienst)
              und schreibt die Ergebnisse in location_stays_geocoded. Erkennt zusätzlich Nicht-Heimaufenthalte
              aus GPS-Tracks (Workouts weit entfernt vom Zuhause) und schlägt neue Einträge für travel_history vor.
@purpose.en  Performs reverse geocoding for GPS coordinates from location_stays and session_tracks.
              Reads latitude/longitude, queries Nominatim (OpenStreetMap, free service)
              and writes results to location_stays_geocoded. Additionally detects non-home stays
              from GPS tracks (workouts far from home) and suggests new entries for travel_history.
@method.de   Verwendet Nominatim-API (https://nominatim.openstreetmap.org/reverse) mit Rate-Limit
              (1,1 Sekunden zwischen Anfragen). GPS-Koordinaten werden auf 2 Dezimalstellen gerundet
              (ca. 1,1 km Genauigkeit) durch round_coords() aus utils.anonymize für Datenschutz.
              Ermittelt Klimazone basierend auf Koordinaten und Ländercode.
              Heimbereich wird als Radius von 0,3 Grad (ca. 30 km) definiert.
              Session-Tracks werden nach Datum gruppiert und gemittelt für Cluster-Erkennung.
@method.en   Uses Nominatim API (https://nominatim.openstreetmap.org/reverse) with rate limiting
              (1.1 seconds between requests). GPS coordinates are rounded to 2 decimal places
              (approx. 1.1km accuracy) via round_coords() from utils.anonymize for privacy.
              Determines climate zone based on coordinates and country code.
              Home area defined as radius of 0.3 degrees (approx. 30km).
              Session tracks are grouped and averaged by date for cluster detection.
@reads       health.db.location_stays, health.db.session_tracks, health.db.sessions,
              ~/.config/kyoro/travel_history.json
@writes      health.db.location_stays_geocoded, health.db.location_stays.timezone,
              ~/.config/kyoro/travel_history.json (bei Bestätigung durch Benutzer)
@limits.de   Nominatim hat Rate-Limits (max. 1 Anfrage/Sekunde) - das Skript respektiert dies.
              Nur Aufenthalte mit gültigen GPS-Koordinaten werden verarbeitet.
              Reisevorschläge erfordern Benutzerbestätigung vor dem Hinzufügen zu travel_history.
              Beachte: Koordinaten werden für Geocoding verwendet, Ergebnisse werden in Datenbank gespeichert.

@relevance.de  Ermöglicht die Geokodierung von Aufenthaltsdaten, essentiell für die räumliche Analyse
@relevance.en  Enables geocoding of location data, essential for spatial analysis
@limits.en   Nominatim has rate limits (max 1 request/second) - script respects this.
              Only stays with valid GPS coordinates are processed.
              Travel suggestions require user confirmation before adding to travel_history.
              Note: Coordinates are used for geocoding, results are stored in database.
              Note: City and country names are used for geocoding but not stored.
@usage
    python scripts/utils/geocode_stays.py
    python scripts/utils/geocode_stays.py --force
    python scripts/utils/geocode_stays.py --suggest-travel
    python scripts/utils/geocode_stays.py --no-stays --suggest-travel
    # --force: Alle Aufenthalte neu kodieren (überschreibt bestehende)
    # --suggest-travel: GPS-Tracks nach Auslandsaufenthalten durchsuchen
    # --no-stays: location_stays überspringen, nur GPS-Tracks verarbeiten
"""
import argparse
import json
import sqlite3
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from health_config import Config as _Cfg
from modules.db import open_db
from utils.anonymize import round_coords
from modules.base import tz_from_coords

_cfg = _Cfg()

NOMINATIM_URL = "https://nominatim.openstreetmap.org/reverse"
RATE_LIMIT_S  = 1.1   # Nominatim: max 1 req/s
HOME_RADIUS   = 0.3   # Grad (~30 km) — innerhalb = "Heimbereich"
MIN_STAY_H    = 4     # Mindest-Aufenthaltsdauer für GPS-Cluster (Stunden)

# Klimazonen-Heuristik nach Koordinaten
def _climate_zone(lat: float, lon: float, country_iso: str = "") -> str:
    if country_iso in ("TH", "VN", "ID", "PH", "MY", "KH", "MM", "LA",
                       "SG", "BN", "TL"):
        return "suedostasiatisch"
    if country_iso in ("KE", "TZ", "NG", "GH", "ET", "CD", "CM"):
        return "afrikanisch"
    if country_iso in ("EG", "MA", "TN", "DZ", "LY"):
        return "nordafrikanisch"
    if country_iso in ("IL", "JO", "SA", "AE", "QA", "KW", "OM", "YE", "IQ"):
        return "nahöstlich"
    if country_iso in ("MX", "GT", "HN", "SV", "NI", "CR", "PA",
                       "CO", "VE", "EC", "PE", "BO", "BR", "PY", "AR", "CL"):
        return "lateinamerikanisch"
    if abs(lat) < 15:
        return "tropisch"
    if abs(lat) < 30:
        return "subtropisch"
    if 30 <= lat < 45 and lon > -15:
        return "mediterran"
    if lat >= 60:
        return "skandinavisch"
    if lat >= 45 and lon > 15:
        return "osteuropaeisch"
    return "kontinental"


def _nominatim(lat: float, lon: float) -> dict:
    """Reverse Geocoding via Nominatim. Rate-limited."""
    lat, lon = round_coords(lat, lon)
    params = urllib.parse.urlencode({
        "lat": lat, "lon": lon,
        "format": "json", "addressdetails": 1,
        "zoom": 10,
    })
    url = f"{NOMINATIM_URL}?{params}"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Kyoro-HealthHub/1.0 (health data pipeline)"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as e:
        print(f"    Nominatim-Fehler ({lat:.2f},{lon:.2f}): {e}")
        return {}


def _extract_region(geo: dict, lat: float, lon: float) -> dict:
    """Extrahiert strukturierte Ortsinfo aus Nominatim-Antwort."""
    addr = geo.get("address", {})
    country     = addr.get("country", "")
    country_iso = addr.get("country_code", "").upper()
    state       = addr.get("state") or addr.get("region") or ""
    county      = addr.get("county") or addr.get("district") or ""
    city        = (addr.get("city") or addr.get("town") or
                   addr.get("village") or addr.get("municipality") or "")
    # Subregion = sinnvollster geografischer Bezeichner für Matching
    # Priorität: Insel > Bundesland > Landkreis > Stadt
    island = addr.get("island") or addr.get("archipelago") or ""
    subregion = island or state or county or city or ""
    climate = _climate_zone(lat, lon, country_iso)

    return {
        "country":      country,
        "country_iso":  country_iso,
        "state":        state,
        "county":       county,
        "city":         city,
        "subregion":    subregion,
        "climate_zone": climate,
    }


def geocode_stays(conn: sqlite3.Connection, force: bool = False) -> int:
    """Kodiert ungekodete location_stays. Gibt Anzahl kodierter Einträge zurück."""
    if force:
        conn.execute("DELETE FROM location_stays_geocoded")

    # Ungekodete Stays laden
    already = {r[0] for r in conn.execute(
        "SELECT stay_id FROM location_stays_geocoded").fetchall()}

    rows = conn.execute("""
        SELECT id, lat, lon FROM location_stays
        WHERE lat IS NOT NULL AND lon IS NOT NULL
    """).fetchall()

    todo = [r for r in rows if r[0] not in already]
    print(f"  Reverse Geocoding: {len(todo)} Aufenthalte (bereits: {len(already)})")

    now = datetime.now().isoformat()
    coded = 0

    for stay_id, lat, lon in todo:
        time.sleep(RATE_LIMIT_S)
        geo = _nominatim(lat, lon)
        if not geo:
            continue

        info = _extract_region(geo, lat, lon)
        tz   = tz_from_coords(lat, lon)

        conn.execute("""
            INSERT OR REPLACE INTO location_stays_geocoded
            (stay_id, country, country_iso, state, county, city,
             subregion, climate_zone, geocoded_at)
            VALUES (?,?,?,?,?,?,?,?,?)
        """, (stay_id, info["country"], info["country_iso"],
              info["state"], info["county"], info["city"],
              info["subregion"], info["climate_zone"], now))

        if tz:
            conn.execute(
                "UPDATE location_stays SET timezone=? WHERE id=?",
                (tz, stay_id),
            )

        coded += 1
        tz_str = f" [{tz}]" if tz else ""
        print(f"    Stay {stay_id}: {info['city'] or info['subregion']}, "
              f"{info['country']} ({info['climate_zone']}){tz_str}")

    conn.commit()
    return coded


def geocode_gps_clusters(conn: sqlite3.Connection,
                         force: bool = False) -> list[dict]:
    """Erkennt Nicht-Heim-GPS-Cluster aus session_tracks.

    Gibt Liste möglicher Aufenthalte zurück die nicht in travel_history sind.
    """
    home = _cfg.travel_history  # als Referenz für "schon bekannt"
    known_isos = {t.get("country_iso", "") for t in home}

    # GPS-Tracks der letzten 5 Jahre laden
    cutoff = (datetime.now() - timedelta(days=5 * 365)).strftime("%Y-%m-%d")
    tracks = conn.execute("""
        SELECT s.date, AVG(t.lat) as lat, AVG(t.lon) as lon,
               MIN(t.lat) as lat_min, MAX(t.lat) as lat_max,
               MIN(t.lon) as lon_min, MAX(t.lon) as lon_max,
               COUNT(*) as n_points
        FROM session_tracks t
        JOIN sessions s ON s.id = t.session_id
        WHERE t.lat IS NOT NULL AND s.date >= ?
        GROUP BY s.date
        HAVING n_points >= 10
        ORDER BY s.date
    """, (cutoff,)).fetchall()

    # Heimposition aus location_stays
    home_stays = conn.execute("""
        SELECT AVG(lat), AVG(lon) FROM location_stays WHERE is_home = 1
    """).fetchone()
    home_lat = home_stays[0] if home_stays and home_stays[0] else None
    home_lon = home_stays[1] if home_stays and home_stays[1] else None

    suggestions = []
    seen_isos: set[str] = set()

    for date, lat, lon, *_ in tracks:
        if home_lat and home_lon:
            dist = ((lat - home_lat) ** 2 + (lon - home_lon) ** 2) ** 0.5
            if dist < HOME_RADIUS:
                continue  # Heimbereich

        time.sleep(RATE_LIMIT_S)
        geo = _nominatim(lat, lon)
        if not geo:
            continue

        info = _extract_region(geo, lat, lon)
        iso  = info["country_iso"]

        # Schon in travel_history?
        if iso in known_isos or iso == "DE":
            continue
        if iso in seen_isos:
            continue
        seen_isos.add(iso)

        suggestions.append({
            "name":         info["city"] or info["subregion"] or info["country"],
            "country":      info["country"],
            "country_iso":  iso,
            "subregion":    info["subregion"],
            "climate_zone": info["climate_zone"],
            "date_from":    date,
            "date_to":      date,
            "lat":          lat,
            "lon":          lon,
            "source":       "gps_tracks",
        })
        print(f"  GPS-Aufenthalt erkannt: {date} — "
              f"{info['city'] or info['country']}, {info['country']}")

    return suggestions


def suggest_travel_entries(suggestions: list[dict]) -> None:
    """Zeigt GPS-basierte travel_history-Vorschläge und fragt ob hinzufügen."""
    if not suggestions:
        print("Keine neuen Aufenthalte außerhalb des Heimbereichs gefunden.")
        return

    print(f"\n{len(suggestions)} GPS-Aufenthalt(e) außerhalb Heimbereich erkannt:\n")
    for i, s in enumerate(suggestions, 1):
        print(f"  {i}. {s['name']}, {s['country']} ({s['date_from']})")

    try:
        answer = input(
            "\nIn travel_history.json übernehmen? "
            "[alle/Nummern z.B. 1,3/n]: "
        ).strip().lower()
    except (EOFError, KeyboardInterrupt):
        return

    if answer in ("", "n", "nein", "no"):
        return

    from pathlib import Path as _P
    travel_file = _P.home() / ".config" / "travel_history.json"
    existing = []
    if travel_file.exists():
        import json as _j
        existing = _j.loads(travel_file.read_text(encoding="utf-8"))

    to_add = []
    if answer == "alle":
        to_add = suggestions
    else:
        for num in answer.split(","):
            try:
                to_add.append(suggestions[int(num.strip()) - 1])
            except (ValueError, IndexError):
                pass

    for s in to_add:
        entry = {k: v for k, v in s.items() if k not in ("lat", "lon", "source")}
        existing.append(entry)
        print(f"  ✓ {s['name']}, {s['country']} hinzugefügt")

    import json as _j
    travel_file.write_text(
        _j.dumps(existing, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Gespeichert: {travel_file}")


def main():
    ap = argparse.ArgumentParser(
        description="Reverse Geocoding für GPS-Aufenthalte")
    ap.add_argument("--force", action="store_true",
                    help="Alle Stays neu kodieren")
    ap.add_argument("--suggest-travel", action="store_true",
                    help="GPS-Tracks nach Auslandsaufenthalten durchsuchen")
    ap.add_argument("--no-stays", action="store_true",
                    help="location_stays überspringen")
    args = ap.parse_args()

    conn = open_db()

    if not args.no_stays:
        n = geocode_stays(conn, force=args.force)
        print(f"  {n} Aufenthalte kodiert.")

    if args.suggest_travel:
        print("\nGPS-Tracks nach Auslandsaufenthalten durchsuchen...")
        suggestions = geocode_gps_clusters(conn, force=args.force)
        suggest_travel_entries(suggestions)

    conn.close()
    print("Fertig.")


if __name__ == "__main__":
    main()
