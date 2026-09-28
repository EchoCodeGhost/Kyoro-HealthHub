#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
DWD Pollenflug-Gefahrenindex → health.db (pollen_dwd)

@tier infrastructure
@purpose.de Import des täglichen Pollenflug-Gefahrenindex vom Deutschen Wetterdienst (DWD) OpenData
@purpose.en Import daily pollen risk index from German Weather Service (DWD) OpenData
@method.de Abruf des aktuellen Pollenflug-Status als JSON von DWD OpenData Server.
           Verarbeitet Daten für heute, morgen und übermorgen.
           Unterstützt alle DWD-Teilregionen mit Pollenflugvorhersage.
           Werte: 0-6 (0=kein, 1=gering, 2=gering-mittel, 3=mittel, 4=mittel-hoch, 5=hoch, 6=sehr hoch).
           Bereichsangaben (z.B. "2-3") werden als Mittelwert gespeichert.
@method.en Fetch current pollen flight status as JSON from DWD OpenData server.
           Process data for today, tomorrow and day after tomorrow.
           Supports all DWD sub-regions with pollen forecast.
           Values: 0-6 (0=none, 1=low, 2=low-medium, 3=medium, 4=medium-high, 5=high, 6=very high).
           Range values (e.g. "2-3") are stored as average.
@reads DWD OpenData API (https://opendata.dwd.de/climate_environment/health/alerts/s31fg.json)
@writes health.db:pollen_dwd, health.db:import_log
@limits.de Liefert nur aktuelle und zukünftige Daten (heute + 2 Tage).
           Historische Daten müssen durch täglichen Import aufgebaut werden.
           Erfordert Internetverbindung. Keine Authentifizierung nötig.
@limits.en Only provides current and future data (today + 2 days).
           Historical data must be built through daily imports.
           Requires internet connection. No authentication needed.
@usage python import_pollen_dwd.py
       python import_pollen_dwd.py --region 122
       python import_pollen_dwd.py --list-regions
@refs DWD OpenData: https://www.dwd.de/DE/leistungen/opendata/opendata.html
      DWD Pollenflug: https://www.dwd.de/DE/wetter/wetterundklima_vorort/pollenflug/pollenflug.html


@relevance.de  Ermöglicht den Import von Gesundheitsdaten, essentiell für die umfassende Datenanalyse
@relevance.en  Enables import of health data, essential for comprehensive data analysis
@relevance.de  Ermöglicht den Import von Gesundheitsdaten, essentiell für die umfassende Datenanalyse
@relevance.en  Enables import of health data, essential for comprehensive data analysis
"""

import argparse
import json
import math
import sqlite3
import sys
import urllib.request
from datetime import date, timedelta
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

DWD_URL = "https://opendata.dwd.de/climate_environment/health/alerts/s31fg.json"

# Ungefähre Mittelpunkte der DWD-Teilregionen (lat, lon)
REGION_CENTERS: dict[int, tuple[float, float]] = {
    11:  (54.7,  9.0),   # Inseln und Marschen
    12:  (53.8, 10.2),   # Geest, Schleswig-Holstein und Hamburg
    31:  (53.1,  8.1),   # Westl. Niedersachsen/Bremen
    32:  (52.7, 10.6),   # Östl. Niedersachsen
    41:  (51.7,  7.0),   # Rhein.-Westfäl. Tiefland
    42:  (51.9,  8.8),   # Ostwestfalen
    43:  (51.3,  7.8),   # Mittelgebirge NRW
    61:  (51.9, 11.6),   # Tiefland Sachsen-Anhalt
    62:  (51.7, 10.8),   # Harz
    71:  (51.1, 11.2),   # Tiefland Thüringen
    72:  (50.6, 11.4),   # Mittelgebirge Thüringen
    81:  (51.4, 13.1),   # Tiefland Sachsen
    82:  (50.8, 13.2),   # Mittelgebirge Sachsen
    91:  (51.1,  9.5),   # Nordhessen und hess. Mittelgebirge
    92:  (50.1,  8.7),   # Rhein-Main
    101: (49.9,  7.6),   # Rhein, Pfalz, Nahe und Mosel
    102: (49.6,  7.3),   # Mittelgebirgsbereich Rheinland-Pfalz
    103: (49.4,  7.0),   # Saarland
    111: (48.7,  7.9),   # Oberrhein und unteres Neckartal
    112: (48.9,  9.7),   # Hohenlohe/mittlerer Neckar/Oberschwaben
    113: (48.3,  8.5),   # Mittelgebirge Baden-Württemberg
    121: (47.8, 10.6),   # Allgäu/Oberbayern/Bay. Wald
    122: (48.6, 12.6),   # Donauniederungen
    123: (49.2, 11.5),   # Bayern nördl. der Donau, o. Bayr. Wald, o. Mainfranken
    124: (49.8, 10.1),   # Mainfranken
}


def _nearest_region(lat: float, lon: float) -> int:
    """Bestimmung der nächstgelegenen DWD-Teilregion zu gegebenen Koordinaten.
    
    @purpose.de Automatische Regionenauswahl basierend auf Heimkoordinaten
    @purpose.en Automatic region selection based on home coordinates
    @method.de Berechnet euklidische Distanz zu allen REGION_CENTERS und wählt die nächste.
               Standard-Rückgabe ist Region 122 (Donauniederungen) falls keine näher gefunden wird.
    @method.en Calculate Euclidean distance to all REGION_CENTERS and select the nearest.
               Default return is region 122 (Danube lowlands) if none closer is found.
    @param lat Breitengrad
    @param lon Längengrad
    @returns DWD-Teilregion-ID als Integer
    """
    best_id, best_dist = 122, float("inf")
    for rid, (rlat, rlon) in REGION_CENTERS.items():
        d = math.hypot(lat - rlat, lon - rlon)
        if d < best_dist:
            best_dist, best_id = d, rid
    return best_id


def _parse_val(s: str | None) -> float | None:
    """Parsen eines Pollenwerts aus String.
    
    @purpose.de Konvertierung von DWD-Pollenwerten (String) zu Float-Werten
    @purpose.en Convert DWD pollen values (string) to float values
    @method.de Behandelt None, leere Strings und "-1" als keine Daten (None).
               Bereichsangaben wie "2-3" werden als Mittelwert berechnet.
               Einfache numerische Strings werden direkt konvertiert.
    @method.en Treat None, empty strings and "-1" as no data (None).
               Range values like "2-3" are calculated as average.
               Simple numeric strings are converted directly.
    @param s Pollenwert als String (z.B. "3", "2-3", "-1", "none")
    @returns Float-Wert (0.0-6.0) oder None bei ungültigem Wert
    """
    if s is None:
        return None
    s = str(s).strip()
    if s in ("-1", "", "none"):
        return None
    if "-" in s:
        parts = s.split("-")
        try:
            return (float(parts[0]) + float(parts[1])) / 2
        except ValueError:
            return None
    try:
        return float(s)
    except ValueError:
        return None


def _fetch_dwd() -> list[dict]:
    """Abruf der aktuellen DWD Pollenflug-Daten.
    
    @purpose.de Holen der aktuellen Pollenflugvorhersage von DWD OpenData
    @purpose.en Fetch current pollen forecast from DWD OpenData
    @method.de Führt GET-Request an DWD OpenData API aus und extrahiert content-Feld.
               Fehlschläge werden logged und resultieren in leerer Liste.
    @method.en Perform GET request to DWD OpenData API and extract content field.
               Failures are logged and result in empty list.
    @returns Liste von Dictionaries mit Pollendaten für alle Regionen oder [] bei Fehler
    """
    try:
        with urllib.request.urlopen(DWD_URL, timeout=15) as resp:
            return json.loads(resp.read()).get("content", [])
    except Exception as e:
        print(f"[import_pollen_dwd] Fehler: {e}", file=sys.stderr)
        return []


def import_pollen_dwd_from_raw(conn: sqlite3.Connection,
                               content: list, region_id: int) -> int:
    """Import von Pollendaten aus einer vorab abgerufenen DWD-Antwort.
    
    @purpose.de Direkter Import aus API-Daten ohne erneuten API-Aufruf (für Batch-Verarbeitung)
    @purpose.en Direct import from API data without re-fetching (for batch processing)
    @method.de Extrahiert Pollendaten für die angegebene Region aus dem content.
               Verarbeitet heute, morgen und übermorgen.
               Speichert in pollen_dwd-Tabelle mit INSERT OR IGNORE.
    @method.en Extract pollen data for the specified region from content.
               Process today, tomorrow and day after tomorrow.
               Store in pollen_dwd table with INSERT OR IGNORE.
    @param conn SQLite-Datenbankverbindung
    @param content DWD API content (Liste von Regions-Dicts)
    @param region_id DWD-Teilregion-ID
    @returns Anzahl der importierten Datensätze
    """
    region = next((r for r in content if r.get("partregion_id") == region_id), None)
    if region is None:
        print(t(f"Region {region_id} nicht gefunden.",
                f"Region {region_id} not found."), file=sys.stderr)
        return 0

    region_name = region.get("partregion_name", "")
    pollen = region.get("Pollen", {})
    today   = date.today()
    day_map = {
        "today":       str(today),
        "tomorrow":    str(today + timedelta(days=1)),
        "dayafter_to": str(today + timedelta(days=2)),
    }
    cur   = conn.cursor()
    count = 0
    for day_key, day_str in day_map.items():
        row = (
            day_str, region_id, region_name,
            _parse_val(pollen.get("Hasel",    {}).get(day_key)),
            _parse_val(pollen.get("Erle",     {}).get(day_key)),
            _parse_val(pollen.get("Esche",    {}).get(day_key)),
            _parse_val(pollen.get("Birke",    {}).get(day_key)),
            _parse_val(pollen.get("Graeser",  {}).get(day_key)),
            _parse_val(pollen.get("Roggen",   {}).get(day_key)),
            _parse_val(pollen.get("Beifuss",  {}).get(day_key)),
            _parse_val(pollen.get("Ambrosia", {}).get(day_key)),
            _OWN_PERSON_ID,
        )
        cur.execute(
            "INSERT OR IGNORE INTO pollen_dwd "
            "(date,region_id,region_name,hazel,alder,ash,birch,grass,rye,mugwort,ragweed,person) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            row
        )
        count += cur.rowcount
    # person=None explizit: regionaler Pollenflug-Index (DWD), keine Personendaten (s. add-importer-person-parameterization-remaining)

    log_import(conn, 'pollen_dwd', '', count, person=None)
    conn.commit()
    return count


def import_pollen_dwd(conn: sqlite3.Connection, region_id: int) -> int:
    """Import von DWD Pollenflug-Daten für eine spezifische Region.
    
    @purpose.de Hauptfunktion für den Import von Pollendaten für eine Region
    @purpose.en Main function for importing pollen data for a region
    @method.de Ruft _fetch_dwd auf, validiert die Region und speichert Pollendaten
               für heute, morgen und übermorgen in pollen_dwd-Tabelle.
    @method.en Call _fetch_dwd, validate region and store pollen data
               for today, tomorrow and day after tomorrow in pollen_dwd table.
    @param conn SQLite-Datenbankverbindung
    @param region_id DWD-Teilregion-ID
    @returns Anzahl der importierten Datensätze oder 0 bei Fehler
    """
    content = _fetch_dwd()
    if not content:
        return 0

    region = next((r for r in content if r.get("partregion_id") == region_id), None)
    if region is None:
        print(t(
            f"Region {region_id} nicht gefunden.",
            f"Region {region_id} not found."
        ), file=sys.stderr)
        return 0

    region_name = region.get("partregion_name", "")
    pollen = region.get("Pollen", {})

    today     = date.today()
    day_map   = {
        "today":        str(today),
        "tomorrow":     str(today + timedelta(days=1)),
        "dayafter_to":  str(today + timedelta(days=2)),
    }

    cur   = conn.cursor()
    count = 0
    for day_key, day_str in day_map.items():
        row = (
            day_str, region_id, region_name,
            _parse_val(pollen.get("Hasel",   {}).get(day_key)),
            _parse_val(pollen.get("Erle",    {}).get(day_key)),
            _parse_val(pollen.get("Esche",   {}).get(day_key)),
            _parse_val(pollen.get("Birke",   {}).get(day_key)),
            _parse_val(pollen.get("Graeser", {}).get(day_key)),
            _parse_val(pollen.get("Roggen",  {}).get(day_key)),
            _parse_val(pollen.get("Beifuss", {}).get(day_key)),
            _parse_val(pollen.get("Ambrosia",{}).get(day_key)),
            _OWN_PERSON_ID,
        )
        cur.execute(
            "INSERT OR IGNORE INTO pollen_dwd "
            "(date,region_id,region_name,hazel,alder,ash,birch,grass,rye,mugwort,ragweed,person) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            row
        )
        count += cur.rowcount

    # person=None explizit: regionaler Pollenflug-Index (DWD), keine Personendaten (s. add-importer-person-parameterization-remaining)


    log_import(conn, 'pollen_dwd', '', count, person=None)
    conn.commit()
    return count


def main():
    """Hauptfunktion für den DWD Pollen-Import.
    
    @purpose.de Orchestrierung des Import-Prozesses mit Argument-Parsing
    @purpose.en Orchestrate import process with argument parsing
    @method.de Parsen von CLI-Argumenten, Validierung der Region oder Standort,
               Aufruf von import_pollen_dwd, Anzeige von Import-Statistik
    @method.en Parse CLI arguments, validate region or location,
               call import_pollen_dwd, display import statistics
    """
    parser = argparse.ArgumentParser(
        description=t(
            "DWD Pollenflug-Gefahrenindex → health.db",
            "DWD pollen risk index → health.db"
        )
    )
    parser.add_argument("--region", type=int, default=None,
                        help="DWD Teilregion-ID (Standard: nächste zu HOME_LAT/LON)")
    parser.add_argument("--list-regions", action="store_true",
                        help="Alle verfügbaren Regionen anzeigen und beenden")
    parser.add_argument("--update",  action="store_true", help="Nur neue Daten (No-op, DWD liefert immer aktuellen Stand)")
    parser.add_argument("--from",    dest="date_from", metavar="DATE", help="Ignoriert")
    parser.add_argument("--to",      dest="date_to",   metavar="DATE", help="Ignoriert")
    add_lang_arg(parser)
    args = parser.parse_args()
    apply_lang_from_args(args)

    if args.list_regions:
        content = _fetch_dwd()
        print(t("Verfügbare DWD-Regionen:", "Available DWD regions:"))
        for r in content:
            pid = r.get("partregion_id", -1)
            if pid > 0:
                print(f"  {pid:4d}  {r.get('partregion_name','')} "
                      f"({r.get('region_name','')})")
        return

    if args.region is None and (HOME_LAT is None or HOME_LON is None):
        parser.error(t(
            "--region erforderlich (oder location.lat/lon in health_config.json setzen).",
            "--region required (or set location.lat/lon in health_config.json)."))

    region_id = args.region or _nearest_region(HOME_LAT, HOME_LON)
    if HOME_LAT is not None and HOME_LON is not None:
        print(t(
            f"DWD Pollen-Import für Region {region_id} "
            f"(nächste zu {HOME_LAT:.2f}°N, {HOME_LON:.2f}°E) ...",
            f"DWD pollen import for region {region_id} "
            f"(nearest to {HOME_LAT:.2f}°N, {HOME_LON:.2f}°E) ..."
        ))
    else:
        print(t(
            f"DWD Pollen-Import für Region {region_id} ...",
            f"DWD pollen import for region {region_id} ..."
        ))

    conn = open_db()
    n = import_pollen_dwd(conn, region_id)
    print(t(f"  {n} Tage gespeichert.", f"  {n} days stored."))
    conn.close()


if __name__ == "__main__":
    main()
