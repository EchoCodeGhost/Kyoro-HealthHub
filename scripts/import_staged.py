#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Staged Import — Importiert Rohdaten aus dem Staging-Verzeichnis in health.db.

@tier        infrastructure
@purpose.de  Liest Rohdaten aus data/staging/YYYY-MM-DD/ und importiert sie in health.db.
             Ermöglicht Offline-Import: Daten werden einmal von fetch_daily.py geholt und
             können beliebig oft neu importiert werden.
@purpose.en  Reads raw data from data/staging/YYYY-MM-DD/ and imports it into health.db.
             Enables offline import: data is fetched once by fetch_daily.py and can be
             imported any number of times.
@method.de   Durchsucht das Staging-Verzeichnis nach JSON-Dateien mit Gesundheitsdaten.
             Jede Datei wird geparst und die Daten in die entsprechenden Tabellen der
             health.db geschrieben. Unterstützt verschiedene Datenquellen (Polar, Apple,
             Oura, Dyson, Ecowitt, etc.) basierend auf der manifest.json. Standortdaten
             werden aus dem Manifest oder der Konfiguration entnommen.
@method.en   Scans the staging directory for JSON files with health data. Each file is
             parsed and the data is written to the corresponding tables in health.db.
             Supports various data sources (Polar, Apple, Oura, Dyson, Ecowitt, etc.)
             based on the manifest.json. Location data is sourced from the manifest or
             configuration.
@reads       data/staging/YYYY-MM-DD/*.json (Rohdaten)
@writes      health.db (alle Tabellen basierend auf den importierten Daten)
@limits.de   Keine Datenvalidierung auf Semantik-Ebene. Abhängig von der Qualität der
             Rohdaten aus fetch_daily.py. Kein Abgleich mit bestehenden Daten -
             importiert einfach alle verfügbaren Daten. Keine medizinische Interpretation.

@relevance.de  Bietet Gesundheitsdatenfunktionen, essentiell für die medizinische Datenverarbeitung
@relevance.en  Provides health data functions, essential for medical data processing
@limits.en   No semantic data validation. Dependent on the quality of raw data from
             fetch_daily.py. No comparison with existing data - simply imports all
             available data. No medical interpretation.
@usage
    python import_staged.py                    # heutiges Staging
    python import_staged.py --date 2026-06-01  # bestimmtes Datum
    python import_staged.py --list             # verfügbare Staging-Tage anzeigen
    python import_staged.py --all              # alle verfügbaren Tage importieren
"""

import argparse
import json
import sqlite3
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from health_config import Config as _Cfg
from modules.db import open_db
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from utils.post_import_sanitize import run as _run_post_import_sanitize

_cfg = _Cfg()
DB_PATH      = _cfg.db_path
STAGING_BASE = Path(__file__).parent.parent / "data" / "staging"


# ── Import functions per source ───────────────────────────────────────────────

def import_source(conn: sqlite3.Connection, staging_day: Path,
                  source: str, entry: dict, manifest: dict) -> int:
    """
    Importiert Daten einer bestimmten Quelle aus dem Staging-Verzeichnis.

    Args:
        conn: SQLite-Datenbankverbindung
        staging_day: Pfad zum Staging-Verzeichnis für einen Tag
        source: Quellenname (z. B. "polar", "apple", "oura")
        entry: Einträge aus manifest.json für diese Quelle
        manifest: Vollständiges manifest.json

    Returns:
        int: Anzahl der importierten Einträge (0 bei Fehler)
    """
    if entry["status"] != "ok":
        reason = entry.get("reason", "")
        marker = "–" if entry["status"] == "skipped" else "✗"
        print(t(f"  {marker} {source}: {entry['status']}" + (f" ({reason})" if reason else ""),
                f"  {marker} {source}: {entry['status']}" + (f" ({reason})" if reason else "")))
        return 0

    file_path = staging_day / entry["file"]
    if not file_path.exists():
        print(t(f"  ✗ {source}: Datei nicht gefunden ({file_path.name})",
                f"  ✗ {source}: file not found ({file_path.name})"), file=sys.stderr)
        return 0

    data = json.loads(file_path.read_text())
    # Standort kommt primär aus dem Manifest (vom fetch_daily.py geschrieben),
    # Fallback aus Config — kein hartkodierter Berlin-Default.
    lat  = manifest.get("lat", _cfg.home_lat)
    lon  = manifest.get("lon", _cfg.home_lon)
    if lat is None or lon is None:
        print(t(f"  ✗ {source}: kein Standort verfügbar (Manifest und Config beide leer)",
                f"  ✗ {source}: no location available (manifest and config both empty)"),
              file=sys.stderr)
        return 0

    try:
        if source == "airquality_aq":
            from importers.import_airquality import import_airquality_from_raw
            aq_n, pollen_n = import_airquality_from_raw(conn, data, lat, lon)
            print(t(f"  ✓ air_quality: {aq_n} Tage | pollen: {pollen_n} Tage",
                    f"  ✓ air_quality: {aq_n} days | pollen: {pollen_n} days"))
            return aq_n + pollen_n

        elif source == "airquality_bio":
            from importers.import_airquality import import_biometeo_from_raw
            n = import_biometeo_from_raw(conn, data, lat, lon)
            print(t(f"  ✓ biometeo: {n} Tage", f"  ✓ biometeo: {n} days"))
            return n

        elif source == "pollen_dwd":
            from importers.import_pollen_dwd import import_pollen_dwd_from_raw
            region_id = manifest.get("region_id", 122)
            n = import_pollen_dwd_from_raw(conn, data["content"], region_id)
            print(t(f"  ✓ pollen_dwd: {n} Tage (Region {region_id})",
                    f"  ✓ pollen_dwd: {n} days (region {region_id})"))
            return n

        elif source == "pollen_google":
            from importers.import_pollen_google import import_pollen_google_from_raw
            n = import_pollen_google_from_raw(conn, data)
            print(t(f"  ✓ pollen_google: {n} Einträge", f"  ✓ pollen_google: {n} entries"))
            return n

        elif source == "dyson":
            from importers.import_homeassistant import import_airpurifier_to_db
            n = import_airpurifier_to_db(conn, data["statistics"], data["entity_meta"])
            print(t(f"  ✓ indoor_air_quality: {n} Einträge",
                    f"  ✓ indoor_air_quality: {n} entries"))
            return n

        elif source == "ecowitt":
            from importers.import_homeassistant import import_weather_to_db
            n = import_weather_to_db(conn, data["statistics"])
            print(t(f"  ✓ weather_station: {n} Tage", f"  ✓ weather_station: {n} days"))
            return n

        elif source == "dwd_station":
            from importers.import_homeassistant import import_dwd_station_to_db
            n = import_dwd_station_to_db(conn, data["statistics"])
            print(t(f"  ✓ weather_dwd_station: {n} Tage",
                    f"  ✓ weather_dwd_station: {n} days"))
            return n

        elif source == "dwd_direct":
            from importers.import_dwd_brightsky import import_brightsky_from_raw
            n = import_brightsky_from_raw(conn, data)
            sid  = (data.get("sources") or [{}])[0].get("dwd_station_id", "?")
            name = (data.get("sources") or [{}])[0].get("station_name", "")
            label = f"{name} ({sid})" if name else sid
            print(t(f"  ✓ dwd_station Brightsky {label}: {n} Tage",
                    f"  ✓ dwd_station Brightsky {label}: {n} days"))
            return n

        elif source == "aemet":
            from importers.import_aemet import import_to_db as aemet_import
            n = aemet_import(conn, data["records"],
                             data["station_id"], data["station_name"])
            print(t(f"  ✓ weather_dwd_station (AEMET): {n} Tage",
                    f"  ✓ weather_dwd_station (AEMET): {n} days"))
            return n

        else:
            print(t(f"  ? {source}: unbekannte Quelle, übersprungen",
                    f"  ? {source}: unknown source, skipped"))
            return 0

    except Exception as e:
        print(t(f"  ✗ {source}: Fehler — {e}", f"  ✗ {source}: error — {e}"),
              file=sys.stderr)
        return 0


def import_day(conn: sqlite3.Connection, target_date: str) -> int:
    """
    Importiert alle Daten für einen bestimmten Tag.

    Args:
        conn: SQLite-Datenbankverbindung
        target_date: Datum im Format YYYY-MM-DD

    Returns:
        int: Gesamtzahl der importierten Einträge
    """
    staging_day = STAGING_BASE / target_date
    manifest_path = staging_day / "manifest.json"

    if not manifest_path.exists():
        print(t(f"Kein Staging für {target_date} gefunden ({staging_day})",
                f"No staging found for {target_date} ({staging_day})"),
              file=sys.stderr)
        return 0

    manifest = json.loads(manifest_path.read_text())
    sources  = manifest.get("sources", {})

    print(t(f"\n── Importiere {target_date} ─────────────────────────────",
            f"\n── Importing {target_date} ──────────────────────────────"))

    total = 0
    for source, entry in sources.items():
        total += import_source(conn, staging_day, source, entry, manifest)

    print(t(f"  Gesamt: {total} Einträge importiert",
            f"  Total: {total} entries imported"))
    return total


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    """
    Hauptfunktion: Parsed Argumente und startet den Import.

    Command-Line-Argumente:
        --date: Datum im Format YYYY-MM-DD (Standard: heute)
        --all: Alle verfügbaren Staging-Tage importieren
        --list: Verfügbare Staging-Tage anzeigen
    """
    parser = argparse.ArgumentParser(
        description=t(
            "Staged Import — aus data/staging/ in health.db importieren",
            "Staged import — from data/staging/ into health.db"
        )
    )
    parser.add_argument("--date", default=None, metavar="YYYY-MM-DD",
                        help=t("Datum importieren (Standard: heute)",
                               "Date to import (default: today)"))
    parser.add_argument("--all", action="store_true",
                        help=t("Alle verfügbaren Staging-Tage importieren",
                               "Import all available staging days"))
    parser.add_argument("--list", action="store_true",
                        help=t("Verfügbare Staging-Tage anzeigen",
                               "List available staging days"))
    add_lang_arg(parser)
    args = parser.parse_args()
    apply_lang_from_args(args)

    if args.list:
        days = sorted(
            d.name for d in STAGING_BASE.iterdir()
            if d.is_dir() and (d / "manifest.json").exists()
        )
        if not days:
            print(t("Keine Staging-Daten gefunden.", "No staging data found."))
        else:
            print(t(f"{len(days)} Staging-Tage verfügbar:",
                    f"{len(days)} staging days available:"))
            for d in days:
                mf = json.loads((STAGING_BASE / d / "manifest.json").read_text())
                sources = mf.get("sources", {})
                ok  = sum(1 for v in sources.values() if v["status"] == "ok")
                err = sum(1 for v in sources.values() if v["status"] == "error")
                print(f"  {d}  {ok} OK" + (t(f"  {err} Fehler", f"  {err} errors") if err else ""))
        return

    conn = open_db()

    if args.all:
        days = sorted(
            d.name for d in STAGING_BASE.iterdir()
            if d.is_dir() and (d / "manifest.json").exists()
        )
        if not days:
            print(t("Keine Staging-Daten gefunden.", "No staging data found."))
            return
        total = 0
        for d in days:
            total += import_day(conn, d)
        print(t(f"\nGesamt über alle Tage: {total} Einträge",
                f"\nTotal across all days: {total} entries"))
    else:
        target = args.date or str(date.today())
        import_day(conn, target)

    conn.close()
    print(t(f"\nDatenbank: {DB_PATH}", f"\nDatabase: {DB_PATH}"))
    _run_post_import_sanitize()


if __name__ == "__main__":
    main()
