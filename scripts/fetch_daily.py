#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Daily Fetch — holt Daten von allen Online-Quellen und speichert sie als JSON.

@tier        infrastructure
@purpose.de  Holt Gesundheits- und Umweltdaten von Online-Quellen und speichert
             sie als JSON-Dateien in data/staging/YYYY-MM-DD/. Ermöglicht den
             Offline-Import durch import_staged.py ohne direkte Datenbankzugriffe.
@purpose.en  Fetches health and environmental data from online sources and stores
             them as JSON files in data/staging/YYYY-MM-DD/. Enables offline import
             via import_staged.py without direct database access.
@method.de   Ruft verschiedene APIs ab: Open-Meteo (Luftqualität, Biometeo), DWD
             (Pollenflug), Google Pollen API, Home Assistant (Dyson, Ecowitt).
             Außerdem synchronisiert es direkt Gerätedaten: Oura Ring API und
             Garmin Connect API (--update, schreibt direkt in health.db).
             Polar hat keine API — Import über import_all.py --update nach manuellem Export.
             Standortdaten werden aus Konfiguration oder Reiseprotokoll entnommen.
             Jede Quelle wird als separate JSON-Datei mit Status-Informationen
             in einem manifest.json gespeichert.
@method.en   Fetches data from various APIs: Open-Meteo (air quality, biometeo), DWD
             (pollen flight), Google Pollen API, Home Assistant (Dyson, Ecowitt).
             Also directly syncs device data: Oura Ring API and Garmin Connect API
             (--update, writes directly to health.db).
             Polar has no API — import via import_all.py --update after manual export.
             Location data is sourced from configuration or travel log.
             Each source is stored as a separate JSON file with status information
             in a manifest.json.
@reads       Open-Meteo API, DWD/Brightsky API, Google Pollen API,
             Home Assistant API (Dyson, Ecowitt), Reiseprotokoll (DB),
             Oura Cloud API, Garmin Connect API
@writes      data/staging/YYYY-MM-DD/*.json (Rohdaten)
             data/staging/YYYY-MM-DD/manifest.json (Metadaten)
             health.db (Oura + Garmin direkt via --update)
@limits.de   Keine Datenvalidierung auf Semantik-Ebene. Abhängig von der
             Verfügbarkeit der externen APIs und der Qualität der zurückgegebenen
             Daten. Keine medizinische Interpretation der Daten.

@relevance.de  Bietet Gesundheitsdatenfunktionen, essentiell für die medizinische Datenverarbeitung
@relevance.en  Provides health data functions, essential for medical data processing
@limits.en   No semantic data validation. Dependent on the availability of external
             APIs and the quality of returned data. No medical interpretation of data.
@usage
    python fetch_daily.py
    python fetch_daily.py --date 2026-06-01
    python fetch_daily.py --days-back 7    # letzte 7 Tage nachholen
    python fetch_daily.py --no-ha          # Home Assistant überspringen
    python fetch_daily.py --no-devices     # Oura/Garmin-Sync überspringen
"""

import argparse
import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from health_config import Config as _Cfg, KYORO_CONFIG_DIR
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from utils.anonymize import round_coords

_cfg = _Cfg()
HOME_LAT, HOME_LON = (
    round_coords(_cfg.home_lat, _cfg.home_lon)
    if _cfg.home_lat is not None and _cfg.home_lon is not None
    else (_cfg.home_lat, _cfg.home_lon)
)

STAGING_BASE = Path(__file__).parent.parent / "data" / "staging"


def _location_from_stays(target_date: str) -> tuple[float, float] | None:
    """Look up (lat, lon) for target_date from the GPS-based location_stays
    table (health.db), independent of the manually maintained
    travel_history.json. Returns None if no stay covers the date or the
    DB is unavailable.
    """
    try:
        from modules.db import open_db
        from health_config import OWN_PERSON_ID
        conn = open_db()
        row = conn.execute(
            "SELECT lat, lon FROM location_stays "
            "WHERE person = ? AND date(start_ts) <= ? AND date(end_ts) >= ? "
            "AND lat IS NOT NULL AND lon IS NOT NULL "
            "ORDER BY is_home ASC LIMIT 1",
            (OWN_PERSON_ID, target_date, target_date),
        ).fetchone()
        conn.close()
        if row:
            return round_coords(row[0], row[1])
    except Exception:
        pass
    return None


def _location_for_date(target_date: str) -> tuple[float, float, bool]:
    """Return (lat, lon, is_home) for the target date.

    Priority: 1) track_location.travel_coords_for_date() (manually
    maintained travel_history.json), 2) GPS-based location_stays table
    (health.db) as fallback for trips not manually logged, 3) HOME_LAT/LON.
    Raises if no home location is configured and neither source matches.
    """
    try:
        sys.path.insert(0, str(Path(__file__).parent / "utils"))
        from track_location import travel_coords_for_date
        coords = travel_coords_for_date(target_date)
        if coords:
            lat, lon, _ = coords
            if HOME_LAT is None or HOME_LON is None:
                return lat, lon, False
            is_home = (abs(lat - HOME_LAT) < 0.05 and abs(lon - HOME_LON) < 0.05)
            return lat, lon, is_home
    except Exception:
        pass

    stay_coords = _location_from_stays(target_date)
    if stay_coords:
        lat, lon = stay_coords
        if HOME_LAT is None or HOME_LON is None:
            return lat, lon, False
        is_home = (abs(lat - HOME_LAT) < 0.05 and abs(lon - HOME_LON) < 0.05)
        return lat, lon, is_home

    if HOME_LAT is None or HOME_LON is None:
        raise RuntimeError(
            "Kein Standort verfügbar — bitte location.lat/lon in "
            "~/.config/kyoro/health_config.json setzen oder travel_log.json pflegen."
        )
    return HOME_LAT, HOME_LON, True


# ── Helpers ───────────────────────────────────────────────────────────────────

def _save(staging_day: Path, name: str, data) -> None:
    (staging_day / f"{name}.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2)
    )


def _ok(file: str) -> dict:
    return {"status": "ok", "file": file,
            "fetched_at": datetime.now(timezone.utc).isoformat()}


def _err(reason: str) -> dict:
    return {"status": "error", "reason": reason,
            "fetched_at": datetime.now(timezone.utc).isoformat()}


def _skip(reason: str) -> dict:
    return {"status": "skipped", "reason": reason,
            "fetched_at": datetime.now(timezone.utc).isoformat()}


# ── Fetch functions ───────────────────────────────────────────────────────────

def fetch_airquality(staging_day: Path, lat: float, lon: float,
                     date_from: str, date_to: str) -> dict:
    """
    Holt Luftqualitäts- und Pollendaten von Open-Meteo.

    Args:
        staging_day: Zielverzeichnis für die JSON-Dateien
        lat: Geografische Breite
        lon: Geografische Länge
        date_from: Startdatum (YYYY-MM-DD)
        date_to: Enddatum (YYYY-MM-DD)

    Returns:
        dict: Status-Informationen für jede Quelle
    """
    from importers.import_airquality import (
        AQ_API_URL, AQ_HOURLY_VARS,
        ARCHIVE_API_URL, BIOMETEO_DAILY_VARS, BIOMETEO_HOURLY_VARS,
        _fetch,
    )
    lat, lon = round_coords(lat, lon)
    results = {}

    aq_url = (f"{AQ_API_URL}?latitude={lat}&longitude={lon}"
              f"&start_date={date_from}&end_date={date_to}"
              f"&hourly={AQ_HOURLY_VARS}&timezone=Europe%2FBerlin")
    aq_data = _fetch(aq_url)
    if aq_data:
        _save(staging_day, "airquality_aq", aq_data)
        results["airquality_aq"] = _ok("airquality_aq.json")
        print(t(f"  ✓ Open-Meteo Luftqualität+Pollen ({date_from}→{date_to})",
                f"  ✓ Open-Meteo air quality+pollen ({date_from}→{date_to})"))
    else:
        results["airquality_aq"] = _err("fetch failed")
        print(t("  ✗ Open-Meteo Luftqualität: Fehler", "  ✗ Open-Meteo air quality: error"),
              file=sys.stderr)

    bio_url = (f"{ARCHIVE_API_URL}?latitude={lat}&longitude={lon}"
               f"&start_date={date_from}&end_date={date_to}"
               f"&daily={BIOMETEO_DAILY_VARS}&hourly={BIOMETEO_HOURLY_VARS}"
               f"&timezone=Europe%2FBerlin")
    bio_data = _fetch(bio_url)
    if bio_data:
        _save(staging_day, "airquality_bio", bio_data)
        results["airquality_bio"] = _ok("airquality_bio.json")
        print(t("  ✓ Open-Meteo Biometeo", "  ✓ Open-Meteo biometeo"))
    else:
        results["airquality_bio"] = _err("fetch failed")
        print(t("  ✗ Open-Meteo Biometeo: Fehler", "  ✗ Open-Meteo biometeo: error"),
              file=sys.stderr)

    return results


def fetch_pollen_dwd(staging_day: Path, region_id: int) -> dict:
    from importers.import_pollen_dwd import _fetch_dwd
    content = _fetch_dwd()
    if content:
        _save(staging_day, "pollen_dwd", {"content": content})
        print(t(f"  ✓ DWD Pollen (Region {region_id})",
                f"  ✓ DWD pollen (region {region_id})"))
        return {"pollen_dwd": _ok("pollen_dwd.json")}
    else:
        print(t("  ✗ DWD Pollen: Fehler", "  ✗ DWD pollen: error"), file=sys.stderr)
        return {"pollen_dwd": _err("fetch failed")}


def fetch_pollen_google(staging_day: Path, lat: float, lon: float, days: int = 5) -> dict:
    from importers.import_pollen_google import _get_api_key, _fetch_google
    api_key = _get_api_key()
    if not api_key:
        print(t("  – Google Pollen: kein API-Key, übersprungen",
                "  – Google pollen: no API key, skipped"))
        return {"pollen_google": _skip("no api key")}
    data = _fetch_google(api_key, lat, lon, days)
    if data:
        _save(staging_day, "pollen_google", data)
        print(t(f"  ✓ Google Pollen ({days} Tage)", f"  ✓ Google pollen ({days} days)"))
        return {"pollen_google": _ok("pollen_google.json")}
    else:
        print(t("  ✗ Google Pollen: Fehler", "  ✗ Google pollen: error"), file=sys.stderr)
        return {"pollen_google": _err("fetch failed")}


def fetch_dwd_brightsky(staging_day: Path, lat: float, lon: float,
                        date_from: str, date_to: str) -> dict:
    from importers.import_dwd_brightsky import fetch_brightsky
    data = fetch_brightsky(lat, lon, date_from, date_to)
    if data and data.get("weather"):
        _save(staging_day, "dwd_direct", data)
        sources = data.get("sources", [])
        label = sources[0].get("station_name", "?") if sources else "?"
        sid   = sources[0].get("dwd_station_id", "?") if sources else "?"
        print(t(f"  ✓ DWD Brightsky: {label} ({sid})",
                f"  ✓ DWD Brightsky: {label} ({sid})"))
        return {"dwd_direct": _ok("dwd_direct.json")}
    else:
        print(t("  ✗ DWD Brightsky: Fehler", "  ✗ DWD Brightsky: error"), file=sys.stderr)
        return {"dwd_direct": _err("fetch failed")}


def fetch_ha_data(staging_day: Path, start_dt: datetime, end_dt: datetime,
                  is_spain: bool = False) -> dict:
    results = {}
    try:
        from importers.import_homeassistant import (
            load_config, fetch_statistics, ha_get,
            ECOWITT_ENTITIES, DWD_STATION_ENTITIES, DWD_STATION_NAME,
        )
        _DWD_LABEL = DWD_STATION_NAME or ""
        config = load_config()

        # Dyson / VeSync
        ap_ids = config.get("airpurifier_entities", [])
        if ap_ids:
            try:
                all_states = ha_get(config, "/api/states")
                ap_meta = {
                    s["entity_id"]: {
                        "unit":          s.get("attributes", {}).get("unit_of_measurement", ""),
                        "friendly_name": s.get("attributes", {}).get("friendly_name", ""),
                    }
                    for s in all_states if s.get("entity_id") in ap_ids
                }
            except Exception:
                ap_meta = {}
            stats = fetch_statistics(config, ap_ids, start_dt, end_dt)
            _save(staging_day, "dyson", {"statistics": stats, "entity_meta": ap_meta})
            n = sum(len(v) for v in stats.values())
            print(t(f"  ✓ Dyson/VeSync ({n} Tages-Aggregate)",
                    f"  ✓ Dyson/VeSync ({n} daily aggregates)"))
            results["dyson"] = _ok("dyson.json")
        else:
            print(t("  – Dyson: keine Entitäten konfiguriert, übersprungen",
                    "  – Dyson: no entities configured, skipped"))
            results["dyson"] = _skip("no airpurifier entities configured")

        # EcoWitt — ohne Entities wie Dyson/DWD überspringen. Sonst geht eine
        # History-Anfrage mit leerem filter_entity_id raus, HA antwortet 400, und
        # der Lauf meldet trotzdem "✓ EcoWitt (0 Tages-Aggregate)".
        ecowitt_ids = list(ECOWITT_ENTITIES.values())
        if ecowitt_ids:
            stats_e = fetch_statistics(config, ecowitt_ids, start_dt, end_dt)
            _save(staging_day, "ecowitt", {"statistics": stats_e})
            n_e = sum(len(v) for v in stats_e.values())
            print(t(f"  ✓ EcoWitt ({n_e} Tages-Aggregate)",
                    f"  ✓ EcoWitt ({n_e} daily aggregates)"))
            results["ecowitt"] = _ok("ecowitt.json")
        else:
            print(t("  – EcoWitt: keine Entitäten konfiguriert, übersprungen",
                    "  – EcoWitt: no entities configured, skipped"))
            results["ecowitt"] = _skip("no ecowitt entities configured")

        # DWD Station (id/entities aus health_config.home_assistant.dwd_station)
        if is_spain:
            results["dwd_station"] = _skip("in Spain — using AEMET instead")
        elif not DWD_STATION_ENTITIES:
            print(t("  – DWD-Station (HA): keine Entities konfiguriert, übersprungen",
                    "  – DWD station (HA): no entities configured, skipped"))
            results["dwd_station"] = _skip("no DWD station configured")
        else:
            dwd_ids = list(DWD_STATION_ENTITIES.values())
            stats_d = fetch_statistics(config, dwd_ids, start_dt, end_dt)
            _save(staging_day, "dwd_station", {"statistics": stats_d})
            n_d = sum(len(v) for v in stats_d.values())
            label = f"DWD-Station {_DWD_LABEL}" if _DWD_LABEL else "DWD-Station"
            print(t(f"  ✓ {label} ({n_d} Tages-Aggregate)",
                    f"  ✓ {label} ({n_d} daily aggregates)"))
            results["dwd_station"] = _ok("dwd_station.json")

    except SystemExit:
        print(t("  – Home Assistant: keine Konfiguration, übersprungen",
                "  – Home Assistant: no config found, skipped"))
        results.setdefault("dyson",   _skip("no HA config"))
        results.setdefault("ecowitt", _skip("no HA config"))
    except Exception as e:
        print(t(f"  ✗ Home Assistant: {e}", f"  ✗ Home Assistant: {e}"), file=sys.stderr)
        results.setdefault("dyson",   _err(str(e)))
        results.setdefault("ecowitt", _err(str(e)))

    return results


# ── Device sync (Oura + Garmin — schreiben direkt in health.db) ──────────────

def fetch_devices(scripts_dir: Path) -> dict:
    """Synchronisiert Oura Ring und Garmin Connect direkt in health.db (--update).

    Polar hat keine Cloud-API und wird hier übersprungen — manueller Export nötig.
    """
    import subprocess
    results = {}

    # Oura Ring API
    oura_script = scripts_dir / "importers" / "import_oura.py"
    if oura_script.exists():
        try:
            r = subprocess.run(
                [sys.executable, str(oura_script), "--update"],
                capture_output=True, text=True,
            )
            if r.returncode == 0:
                print(t("  ✓ Oura Ring API synchronisiert", "  ✓ Oura Ring API synced"))
                results["oura_app"] = _ok("direct-db")
            else:
                msg = (r.stderr or r.stdout or "").strip().splitlines()[-1][:120]
                print(t(f"  ✗ Oura: {msg}", f"  ✗ Oura: {msg}"), file=sys.stderr)
                results["oura_app"] = _err(msg)
        except Exception as e:
            print(t(f"  ✗ Oura: {e}", f"  ✗ Oura: {e}"), file=sys.stderr)
            results["oura_app"] = _err(str(e))
    else:
        print(t("  – Oura: import_oura.py nicht gefunden, übersprungen",
                "  – Oura: import_oura.py not found, skipped"))
        results["oura_app"] = _skip("script not found")

    # Garmin Connect: erst Download, dann Import
    garmin_dl = scripts_dir / "importers" / "garmin_download.py"
    garmin_imp = scripts_dir / "importers" / "import_garmin.py"
    if garmin_dl.exists() and garmin_imp.exists():
        try:
            r_dl = subprocess.run(
                [sys.executable, str(garmin_dl), "--update"],
                capture_output=True, text=True,
            )
            if r_dl.returncode != 0:
                msg = (r_dl.stderr or r_dl.stdout or "").strip().splitlines()[-1][:120]
                print(t(f"  ✗ Garmin Download: {msg}", f"  ✗ Garmin download: {msg}"),
                      file=sys.stderr)
                results["garmin_connect"] = _err(f"download: {msg}")
            else:
                r_imp = subprocess.run(
                    [sys.executable, str(garmin_imp), "--update"],
                    capture_output=True, text=True,
                )
                if r_imp.returncode == 0:
                    print(t("  ✓ Garmin Connect synchronisiert", "  ✓ Garmin Connect synced"))
                    results["garmin_connect"] = _ok("direct-db")
                else:
                    msg = (r_imp.stderr or r_imp.stdout or "").strip().splitlines()[-1][:120]
                    print(t(f"  ✗ Garmin Import: {msg}", f"  ✗ Garmin import: {msg}"),
                          file=sys.stderr)
                    results["garmin_connect"] = _err(f"import: {msg}")
        except Exception as e:
            print(t(f"  ✗ Garmin: {e}", f"  ✗ Garmin: {e}"), file=sys.stderr)
            results["garmin_connect"] = _err(str(e))
    else:
        print(t("  – Garmin: Skripte nicht gefunden, übersprungen",
                "  – Garmin: scripts not found, skipped"))
        results["garmin_connect"] = _skip("scripts not found")

    # Polar AccessLink API
    polar_script = scripts_dir / "importers" / "import_polar_accesslink.py"
    polar_cfg    = KYORO_CONFIG_DIR / "polar_config.json"
    if not polar_script.exists():
        results["polar_accesslink"] = _skip("script not found")
    elif not polar_cfg.exists() or not json.loads(polar_cfg.read_text()).get("access_token"):
        print(t("  – Polar AccessLink: kein Token — bitte --setup ausführen",
                "  – Polar AccessLink: no token — please run --setup"))
        results["polar_accesslink"] = _skip("no access token; run --setup")
    else:
        try:
            r = subprocess.run(
                [sys.executable, str(polar_script), "--update"],
                capture_output=True, text=True,
            )
            if r.returncode == 0:
                print(t("  ✓ Polar AccessLink synchronisiert", "  ✓ Polar AccessLink synced"))
                results["polar_accesslink"] = _ok("direct-db")
            else:
                msg = (r.stderr or r.stdout or "").strip().splitlines()[-1][:120]
                print(t(f"  ✗ Polar: {msg}", f"  ✗ Polar: {msg}"), file=sys.stderr)
                results["polar_accesslink"] = _err(msg)
        except Exception as e:
            print(t(f"  ✗ Polar: {e}", f"  ✗ Polar: {e}"), file=sys.stderr)
            results["polar_accesslink"] = _err(str(e))

    return results


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    """
    Hauptfunktion: Parsed Argumente und koordiniert den täglichen Fetch.

    Command-Line-Argumente:
        --date: Datum im Format YYYY-MM-DD (Standard: heute)
        --days-back: Anzahl der Tage in die Vergangenheit (Standard: 0)
        --no-ha: Home Assistant-Daten überspringen
    """
    parser = argparse.ArgumentParser(
        description=t(
            "Täglicher Fetch — Rohdaten in data/staging/YYYY-MM-DD/ speichern",
            "Daily fetch — save raw data to data/staging/YYYY-MM-DD/"
        )
    )
    parser.add_argument("--date", default=None, metavar="YYYY-MM-DD",
                        help=t("Zieldatum (Standard: heute)", "Target date (default: today)"))
    parser.add_argument("--days-back", type=int, default=1, metavar="N",
                        help=t("Wie viele Tage zurück holen (Standard: 1)",
                               "How many days back to fetch (default: 1)"))
    parser.add_argument("--no-ha", action="store_true",
                        help=t("Home Assistant überspringen", "Skip Home Assistant"))
    parser.add_argument("--no-devices", action="store_true",
                        help=t("Oura/Garmin-Sync überspringen", "Skip Oura/Garmin device sync"))
    add_lang_arg(parser)
    args = parser.parse_args()
    apply_lang_from_args(args)

    target_date = date.fromisoformat(args.date) if args.date else date.today()
    date_from   = str(target_date - timedelta(days=args.days_back - 1))
    date_to     = str(target_date)

    staging_day = STAGING_BASE / str(target_date)
    staging_day.mkdir(parents=True, exist_ok=True)

    # Determine actual location for the target date (travel-aware)
    from importers.import_aemet import _is_spain
    fetch_lat, fetch_lon, is_home = _location_for_date(str(target_date))
    fetch_lat, fetch_lon = round_coords(fetch_lat, fetch_lon)
    is_spain = _is_spain(fetch_lat, fetch_lon)
    location_label = "Zuhause" if is_home else ("Spanien" if is_spain else "Reise")
    print(t(
        f"  📍 Standort: {location_label} ({fetch_lat:.2f},{fetch_lon:.2f})",
        f"  📍 Location: {location_label} ({fetch_lat:.2f},{fetch_lon:.2f})",
    ))

    from importers.import_pollen_dwd import _nearest_region
    region_id = _nearest_region(fetch_lat, fetch_lon)

    manifest = {
        "date":      str(target_date),
        "date_from": date_from,
        "date_to":   date_to,
        "lat":       fetch_lat,
        "lon":       fetch_lon,
        "is_home":   is_home,
        "region_id": region_id,
        "sources":   {},
    }

    print(t(f"Staging: {staging_day}", f"Staging: {staging_day}"))

    print(t("\n── Open-Meteo ───────────────────────────────────────────",
            "\n── Open-Meteo ───────────────────────────────────────────"))
    manifest["sources"].update(
        fetch_airquality(staging_day, fetch_lat, fetch_lon, date_from, date_to))

    print(t("\n── DWD Pollen ───────────────────────────────────────────",
            "\n── DWD pollen ───────────────────────────────────────────"))
    manifest["sources"].update(fetch_pollen_dwd(staging_day, region_id))

    if not is_spain:
        print(t("\n── DWD Station (Brightsky) ──────────────────────────────",
                "\n── DWD station (Brightsky) ──────────────────────────────"))
        manifest["sources"].update(
            fetch_dwd_brightsky(staging_day, fetch_lat, fetch_lon, date_from, date_to))

    print(t("\n── Google Pollen ────────────────────────────────────────",
            "\n── Google pollen ────────────────────────────────────────"))
    manifest["sources"].update(fetch_pollen_google(staging_day, fetch_lat, fetch_lon))

    if not args.no_ha:
        start_dt = datetime.fromisoformat(date_from).replace(tzinfo=timezone.utc)
        end_dt   = datetime.fromisoformat(date_to).replace(
            hour=23, minute=59, second=59, tzinfo=timezone.utc)
        print(t("\n── Home Assistant ───────────────────────────────────────",
                "\n── Home Assistant ───────────────────────────────────────"))
        manifest["sources"].update(fetch_ha_data(staging_day, start_dt, end_dt,
                                                 is_spain=is_spain))

    if not args.no_devices:
        scripts_dir = Path(__file__).parent
        print(t("\n── Geräte-Sync (Oura · Garmin) ─────────────────────────",
                "\n── Device sync (Oura · Garmin) ──────────────────────────"))
        manifest["sources"].update(fetch_devices(scripts_dir))

    # AEMET — nur bei Spanien-Aufenthalt (ersetzt DWD als offizielle Messstation)
    if is_spain:
        print(t("\n── AEMET (Spanien) ──────────────────────────────────────",
                "\n── AEMET (Spain) ────────────────────────────────────────"))
        try:
            from importers.import_aemet import _get_api_key, fetch_stations, nearest_station, fetch_daily as aemet_daily
            api_key = _get_api_key()
            if api_key:
                stations = fetch_stations(api_key)
                station  = nearest_station(stations or [], fetch_lat, fetch_lon) if stations else None
                if station:
                    sid   = station.get("indicativo", "?")
                    sname = station.get("nombre", sid)
                    dist  = station.get("_distance_km", "?")
                    records = aemet_daily(api_key, sid, date_from, date_to)
                    if records:
                        _save(staging_day, "aemet", {
                            "records":      records,
                            "station_id":   sid,
                            "station_name": sname,
                        })
                        print(t(f"  ✓ AEMET {sname} ({sid}), {dist} km, {len(records)} Tage",
                                f"  ✓ AEMET {sname} ({sid}), {dist} km, {len(records)} days"))
                        manifest["sources"]["aemet"] = _ok("aemet.json")
                    else:
                        manifest["sources"]["aemet"] = _err("no data returned")
                else:
                    print(t("  – AEMET: keine Station in der Nähe", "  – AEMET: no nearby station"))
                    manifest["sources"]["aemet"] = _skip("no nearby station")
            else:
                print(t("  – AEMET: kein API-Key (apis.aemet_api_key in health_config.json eintragen)",
                        "  – AEMET: no API key (add apis.aemet_api_key to health_config.json)"))
                manifest["sources"]["aemet"] = _skip("no api key")
        except Exception as e:
            print(t(f"  ✗ AEMET: {e}", f"  ✗ AEMET: {e}"), file=sys.stderr)
            manifest["sources"]["aemet"] = _err(str(e))

    _save(staging_day, "manifest", manifest)

    ok  = sum(1 for v in manifest["sources"].values() if v["status"] == "ok")
    err = sum(1 for v in manifest["sources"].values() if v["status"] == "error")
    skp = sum(1 for v in manifest["sources"].values() if v["status"] == "skipped")
    print(t(f"\n✓ {ok} OK | ✗ {err} Fehler | – {skp} übersprungen",
            f"\n✓ {ok} OK | ✗ {err} errors | – {skp} skipped"))
    if err == 0:
        print(t("\nJetzt importieren: python import_staged.py",
                "\nNow import: python import_staged.py"))
        
        # Tages-Monitor (Oura + Garmin + Polar Sync + Score)
        print(t("\nFühre Tages-Monitor aus...", "\nRunning daily monitor..."))
        try:
            import subprocess
            subprocess.run([sys.executable, "scripts/compute/compute_acute_events.py", "--today"],
                          check=True)
            print(t("Tages-Monitor erfolgreich ausgeführt.", "Daily monitor completed successfully."))
        except subprocess.CalledProcessError as e:
            print(t(f"Tages-Monitor Fehler: {e}", f"Daily monitor error: {e}"), file=sys.stderr)
        except Exception as e:
            print(t(f"Tages-Monitor ausgefallen: {e}", f"Daily monitor failed: {e}"), file=sys.stderr)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
