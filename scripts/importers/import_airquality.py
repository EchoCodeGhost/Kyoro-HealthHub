#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Open-Meteo Luftqualität, Pollen und Biometeo → health.db (air_quality, pollen, biometeo)

@tier infrastructure
@purpose.de Import von Umweltdaten (Luftqualität, Pollen, Biometeorologie) von Open-Meteo API
@purpose.en Import environmental data (air quality, pollen, biometeorology) from Open-Meteo API
@method.de Abruf von Luftqualitätsdaten (PM2.5, PM10, NO2, O3, CO, AQI, Staub) und Pollendaten
           (Birke, Erle, Gräser, Beifuß, Ragweed, Olive) über Air Quality API.
           Biometeo-Daten (Sonnenschein, Strahlung, gefühlte Temperatur, Taupunkt, Feuchte)
           werden über Archive API abgerufen. Tageswerte werden aggregiert.
@method.en Fetch air quality data (PM2.5, PM10, NO2, O3, CO, AQI, dust) and pollen data
           (birch, alder, grass, mugwort, ragweed, olive) via Air Quality API.
           Biometeo data (sunshine, radiation, apparent temperature, dewpoint, humidity)
           is fetched via Archive API. Daily values are aggregated.
@reads Open-Meteo Air Quality API, Open-Meteo Archive API
@writes health.db:air_quality, health.db:pollen, health.db:biometeo, health.db:import_log
@limits.de Erfordert Internetverbindung. Datenabruf in 90-Tage-Chunks. Koordinaten werden gerundet.
           Historische Daten ab 2013-01-01 verfügbar. Keine Echtzeit-Daten (leicht verzögert).
@limits.en Requires internet connection. Data fetched in 90-day chunks. Coordinates are rounded.
           Historical data available from 2013-01-01. No real-time data (slightly delayed).
@usage python3 import_airquality.py --lat 51.2 --lon 10.5
       python3 import_airquality.py --update --from 2024-01-01
@refs Open-Meteo Air Quality API: https://open-meteo.com/en/docs/air-quality-api
      Open-Meteo Archive API: https://open-meteo.com/en/docs/archive-api


@relevance.de  Ermöglicht den Import von Gesundheitsdaten, essentiell für die umfassende Datenanalyse
@relevance.en  Enables import of health data, essential for comprehensive data analysis
@relevance.de  Ermöglicht den Import von Gesundheitsdaten, essentiell für die umfassende Datenanalyse
@relevance.en  Enables import of health data, essential for comprehensive data analysis
"""

import argparse
import json
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
# Keine Default-Koordinaten — Standort muss aus health_config.json (location.lat/lon)
# kommen oder per --lat/--lon übergeben werden.
HOME_LAT, HOME_LON = (
    round_coords(_cfg.home_lat, _cfg.home_lon)
    if _cfg.home_lat is not None and _cfg.home_lon is not None
    else (_cfg.home_lat, _cfg.home_lon)
)
# Zeitzone aus der Konfigurationsdatei lesen
TIMEZONE = getattr(_cfg, 'home_timezone', None) or 'UTC'

# Standardstart für Backfill: clinical.data_start aus der Config, sonst Open-Meteo-Archivanfang.
# Open-Meteo Air-Quality-Archiv beginnt 2013-01-01, Biometeo (ERA5) auch ab 2013.
AQ_START      = _cfg.data_start or "2013-01-01"
BIOMETEO_START = _cfg.data_start or "2013-01-01"

AQ_API_URL      = "https://air-quality-api.open-meteo.com/v1/air-quality"
ARCHIVE_API_URL = "https://archive-api.open-meteo.com/v1/archive"

AQ_HOURLY_VARS = ",".join([
    "pm2_5", "pm10", "nitrogen_dioxide", "ozone", "carbon_monoxide",
    "european_aqi", "dust",
    "alder_pollen", "birch_pollen", "grass_pollen",
    "mugwort_pollen", "ragweed_pollen", "olive_pollen",
])

BIOMETEO_DAILY_VARS  = "sunshine_duration,shortwave_radiation_sum,uv_index_max," \
                        "apparent_temperature_max,apparent_temperature_min,apparent_temperature_mean"
BIOMETEO_HOURLY_VARS = "dewpoint_2m,relativehumidity_2m"

# ── Upserts ──────────────────────────────────────────────────────────────────
# Beide Tabellen haben PRIMARY KEY (date, lat, lon). Ein erneuter Lauf MUSS
# bestehende Zeilen aktualisieren koennen, sonst laesst sich ein Importfehler
# nie reparieren — genau das war hier der Fall:
#   * air_quality aktualisierte bei Konflikt NUR dust_mean/dust_max
#   * pollen benutzte INSERT OR IGNORE und ruehrte bestehende Zeilen nie an
# Zusammen mit dem leeren _max_v()-Rumpf blieben dadurch 5.087 Pollen-Zeilen und
# alle *_max-Spalten dauerhaft NULL, auch nach wiederholten Importlaeufen.
_AQ_COLS = ["date", "lat", "lon",
            "pm25_mean", "pm25_max", "pm10_mean", "pm10_max",
            "no2_mean", "no2_max", "o3_mean", "o3_max", "co_mean", "co_max",
            "aqi_eu_mean", "aqi_eu_max", "dust_mean", "dust_max", "person"]
_POLLEN_COLS = ["date", "lat", "lon",
                "birch", "alder", "grass", "mugwort", "ragweed", "olive", "person"]


def _upsert_sql(table: str, cols: list[str]) -> str:
    """INSERT … ON CONFLICT(date,lat,lon) DO UPDATE über alle Wertespalten."""
    values = ",".join("?" * len(cols))
    updates = ", ".join(f"{c}=excluded.{c}" for c in cols
                        if c not in ("date", "lat", "lon"))
    return (f"INSERT INTO {table} ({','.join(cols)}) VALUES ({values}) "
            f"ON CONFLICT(date, lat, lon) DO UPDATE SET {updates}")


AQ_UPSERT     = _upsert_sql("air_quality", _AQ_COLS)
POLLEN_UPSERT = _upsert_sql("pollen", _POLLEN_COLS)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _fetch(url: str) -> dict:
    """Abruf von Daten von einer API-URL.
    
    @purpose.de Generischer HTTP-Client für Open-Meteo API-Aufrufe
    @purpose.en Generic HTTP client for Open-Meteo API calls
    @method.de Führt GET-Request mit Timeout aus und parst JSON-Antwort.
               Fehlschläge werden logged und resultieren in leerem Dict.
    @method.en Perform GET request with timeout and parse JSON response.
               Failures are logged and result in empty dict.
    @param url API-URL als String
    @returns JSON-Antwort als Dictionary oder {} bei Fehler
    """
    try:
        with urllib.request.urlopen(url, timeout=20) as resp:
            return json.loads(resp.read())
    except Exception as e:
        print(f"[import_airquality] API error: {e}", file=sys.stderr)
        return {}


def _mean(vals: list) -> float | None:
    """Berechnung des Mittelwerts einer Liste von Werten.
    
    @purpose.de Aggregationsfunktion für Tagesmittelwerte von stündlichen Daten
    @purpose.en Aggregation function for daily mean values from hourly data
    @method.de Filtert None-Werte und berechnet arithmetischen Mittelwert
    @method.en Filters None values and calculates arithmetic mean
    @param vals Liste von numerischen Werten (kann None enthalten)
    @returns Mittelwert als Float (auf 2 Dezimalstellen gerundet) oder None
    """
    clean = [v for v in vals if v is not None]
    return round(sum(clean) / len(clean), 2) if clean else None


def _max_v(vals: list) -> float | None:
    """Berechnung des Maximalwerts einer Liste von Werten.
    
    @purpose.de Aggregationsfunktion für Tagesmaximumwerte von stündlichen Daten
    @purpose.en Aggregation function for daily maximum values from hourly data
    @method.de Filtert None-Werte und berechnet Maximum
    @method.en Filters None values and calculates maximum
    @param vals Liste von numerischen Werten (kann None enthalten)
    @returns Maximalwert als Float (auf 2 Dezimalstellen gerundet) oder None
    """
    clean = [v for v in vals if v is not None]
    return round(max(clean), 2) if clean else None


def _date_chunks(dates: list[str], chunk_days: int = 90) -> list[tuple[str, str]]:
    """Aufteilung einer Liste von Datumsstrings in Chunks fester Größe.
    
    @purpose.de Optimierung des API-Abrufs durch Aufteilung in 90-Tage-Blöcke
               (Open-Meteo limitiert Anfragen auf ~90 Tage pro Request)
    @purpose.en Optimize API fetching by splitting into 90-day chunks
               (Open-Meteo limits requests to ~90 days per request)
    @method.de Gruppen aufeinanderfolgende Daten in Chunks von maximal chunk_days Tagen
    @method.en Group consecutive dates into chunks of at most chunk_days days
    @param dates Liste von Datumsstrings im ISO-Format (YYYY-MM-DD)
    @param chunk_days Maximale Anzahl von Tagen pro Chunk (Standard: 90)
    @returns Liste von Tuples (start_date, end_date) für jeden Chunk
    """
    if not dates:
        return []
    chunks, start, prev = [], dates[0], dates[0]
    for d in dates[1:]:
        if (date.fromisoformat(d) - date.fromisoformat(start)).days >= chunk_days:
            chunks.append((start, prev))
            start = d
        prev = d
    chunks.append((start, prev))
    return chunks


def _missing(conn: sqlite3.Connection, table: str, d_from: str, d_to: str,
             lat: float | None = None, lon: float | None = None) -> list[str]:
    """Ermitteln fehlender Daten für eine Tabelle und Zeitraum.
    
    @purpose.de Identifikation von Lücken im Datenbestand für inkrementellen Import
    @purpose.en Identify gaps in existing data for incremental import
    @method.de Vergleicht bestehende Datumsangaben in der DB mit dem gewünschten Zeitraum.
               Bei Angabe von lat/lon wird standortspezifisch geprüft.
    @method.en Compare existing dates in DB with desired period.
               With lat/lon specified, check is location-specific.
    @param conn SQLite-Datenbankverbindung
    @param table Tabellenname (air_quality, pollen oder biometeo)
    @param d_from Startdatum (ISO-Format)
    @param d_to Enddatum (ISO-Format)
    @param lat Breitengrad (optional, für standortspezifische Prüfung)
    @param lon Längengrad (optional, für standortspezifische Prüfung)
    @returns Liste von fehlenden Datumsstrings im ISO-Format
    """
    if lat is not None and lon is not None:
        lat_r, lon_r = round_coords(lat, lon)
        existing = {r[0] for r in conn.execute(
            f"SELECT date FROM {table} WHERE date >= ? AND date <= ? AND lat=? AND lon=?",
            (d_from, d_to, lat_r, lon_r)
        )}
    else:
        existing = {r[0] for r in conn.execute(
            f"SELECT date FROM {table} WHERE date >= ? AND date <= ?", (d_from, d_to)
        )}
    cur = date.fromisoformat(d_from)
    end = date.fromisoformat(d_to)
    result = []
    while cur <= end:
        s = cur.isoformat()
        if s not in existing:
            result.append(s)
        cur += timedelta(days=1)
    return result


# ── Air Quality + Pollen ──────────────────────────────────────────────────────

def _aq_aggregate(data: dict, lat: float, lon: float) -> tuple[list, list]:
    """Aggregation von stündlichen Luftqualitäts- und Pollendaten zu Tageswerten.
    
    @purpose.de Umwandlung von Open-Meteo stündlichen Daten in tägliche Aggregationen
    @purpose.en Convert Open-Meteo hourly data to daily aggregations
    @method.de Gruppiert stündliche Werte nach Datum und berechnet Mittelwerte (PM2.5, PM10, NO2, O3, CO, AQI, Staub)
               und Maximalwerte (AQI, alle Schadstoffe) für air_quality.
               Für Pollen werden Tagesmaximalwerte berechnet.
    @method.en Groups hourly values by date and calculates means (PM2.5, PM10, NO2, O3, CO, AQI, dust)
               and maximums (AQI, all pollutants) for air_quality.
               For pollen, daily maximum values are calculated.
    @param data API-Antwort von Open-Meteo Air Quality API
    @param lat Breitengrad für den Standort
    @param lon Längengrad für den Standort
    @returns Tuple aus (air_quality_rows, pollen_rows) als Listen von Daten-Tuples
    """
    h = data.get("hourly", {})
    times = h.get("time", [])
    if not times:
        return [], []

    keys = ["pm25", "pm10", "no2", "o3", "co", "aqi", "dust",
            "birch", "alder", "grass", "mugwort", "ragweed", "olive"]
    api  = ["pm2_5", "pm10", "nitrogen_dioxide", "ozone", "carbon_monoxide",
            "european_aqi", "dust",
            "birch_pollen", "alder_pollen", "grass_pollen",
            "mugwort_pollen", "ragweed_pollen", "olive_pollen"]
    src  = {k: h.get(a, []) for k, a in zip(keys, api)}

    days: dict[str, dict] = {}
    for i, ts in enumerate(times):
        d = ts[:10]
        if d not in days:
            days[d] = {k: [] for k in keys}
        for k in keys:
            lst = src[k]
            days[d][k].append(lst[i] if i < len(lst) else None)

    aq_rows, pollen_rows = [], []
    for d, v in days.items():
        aqi_max = _max_v(v["aqi"])
        aq_rows.append((
            d, lat, lon,
            _mean(v["pm25"]),  _max_v(v["pm25"]),
            _mean(v["pm10"]),  _max_v(v["pm10"]),
            _mean(v["no2"]),   _max_v(v["no2"]),
            _mean(v["o3"]),    _max_v(v["o3"]),
            _mean(v["co"]),    _max_v(v["co"]),
            _mean(v["aqi"]),   int(aqi_max) if aqi_max is not None else None,
            _mean(v["dust"]),  _max_v(v["dust"]),
        ))
        pollen_rows.append((
            d, lat, lon,
            _max_v(v["birch"]),   _max_v(v["alder"]),
            _max_v(v["grass"]),   _max_v(v["mugwort"]),
            _max_v(v["ragweed"]), _max_v(v["olive"]),
        ))
    return aq_rows, pollen_rows


def import_airquality_from_raw(conn: sqlite3.Connection,
                               aq_data: dict,
                               lat: float, lon: float,
                               person: str = None) -> tuple[int, int]:
    """Import von Luftqualitäts- und Pollendaten aus einer vorab abgerufenen API-Antwort.
    
    @purpose.de Direkter Import aus API-Daten ohne erneuten API-Aufruf (für Batch-Verarbeitung)
    @purpose.en Direct import from API data without re-fetching (for batch processing)
    @method.de Aggregiert Daten mit _aq_aggregate und speichert in air_quality und pollen.
               air_quality verwendet ON CONFLICT DO UPDATE für Staubwerte.
    @method.en Aggregate data with _aq_aggregate and store in air_quality and pollen.
               air_quality uses ON CONFLICT DO UPDATE for dust values.
    @param conn SQLite-Datenbankverbindung
    @param aq_data Open-Meteo Air Quality API-Antwort (JSON als Dict)
    @param lat Breitengrad
    @param lon Längengrad
    @param person Personen-ID (optional, Standard: OWN_PERSON_ID)
    @returns Tuple aus (anzahl_air_quality, anzahl_pollen) importierter Datensätze
    """
    _person = person or _OWN_PERSON_ID
    aq_rows, pollen_rows = _aq_aggregate(aq_data, lat, lon)
    cur = conn.cursor()
    cur.executemany(
        AQ_UPSERT,
        [r + (_person,) for r in aq_rows]
    )
    aq_total = cur.rowcount
    cur.executemany(
        POLLEN_UPSERT,
        [r + (_person,) for r in pollen_rows]
    )
    conn.commit()
    return aq_total, cur.rowcount


def import_biometeo_from_raw(conn: sqlite3.Connection,
                              bio_data: dict,
                              lat: float, lon: float,
                              person: str = None) -> int:
    """Import von Biometeorologie-Daten aus einer vorab abgerufenen API-Antwort.
    
    @purpose.de Direkter Import aus API-Daten ohne erneuten API-Aufruf (für Batch-Verarbeitung)
    @purpose.en Direct import from API data without re-fetching (for batch processing)
    @method.de Aggregiert Daten mit _biometeo_aggregate und speichert in biometeo-Tabelle
    @method.en Aggregate data with _biometeo_aggregate and store in biometeo table
    @param conn SQLite-Datenbankverbindung
    @param bio_data Open-Meteo Archive API-Antwort (JSON als Dict)
    @param lat Breitengrad
    @param lon Längengrad
    @param person Personen-ID (optional, Standard: OWN_PERSON_ID)
    @returns Anzahl der importierten Biometeo-Datensätze
    """
    _person = person or _OWN_PERSON_ID
    rows = _biometeo_aggregate(bio_data, lat, lon)
    cur = conn.cursor()
    cur.executemany(
        "INSERT OR IGNORE INTO biometeo "
        "(date,lat,lon,sunshine_h,solar_mj_m2,uv_index_max,"
        "apparent_temp_mean,apparent_temp_max,apparent_temp_min,"
        "dewpoint_mean,humidity_mean,person) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        [r + (_person,) for r in rows]
    )
    conn.commit()
    return cur.rowcount


def import_airquality(conn: sqlite3.Connection,
                      lat: float, lon: float,
                      date_from: str | None = None,
                      date_to: str | None = None,
                      update: bool = False,
                      person: str = None) -> tuple[int, int]:
    """Import von Luftqualitäts- und Pollendaten von Open-Meteo API.
    
    @purpose.de Hauptfunktion für den Abruf und Import von Luftqualitätsdaten
    @purpose.en Main function for fetching and importing air quality data
    @method.de Prüft fehlende Daten mit _missing, lädt Daten in 90-Tage-Chunks,
               aggregiert mit _aq_aggregate und speichert in air_quality und pollen.
               Im Update-Modus werden nur fehlende Daten geholt.
    @method.en Check missing data with _missing, fetch data in 90-day chunks,
               aggregate with _aq_aggregate and store in air_quality and pollen.
               In update mode, only missing data is fetched.
    @param conn SQLite-Datenbankverbindung
    @param lat Breitengrad
    @param lon Längengrad
    @param date_from Startdatum (ISO-Format, optional, Standard: AQ_START)
    @param date_to Enddatum (ISO-Format, optional, Standard: heute)
    @param update Nur fehlende Daten ergänzen
    @param person Personen-ID (optional, Standard: OWN_PERSON_ID)
    @returns Tuple aus (anzahl_air_quality, anzahl_pollen) importierter Datensätze
    """
    _person = person or _OWN_PERSON_ID
    lat, lon = round_coords(lat, lon)
    today = date.today().isoformat()
    start = date_from or AQ_START
    end   = date_to   or today

    chunks = _date_chunks(_missing(conn, "air_quality", start, end, lat, lon)) if update \
             else [(start, end)]

    aq_total = pollen_total = 0
    cur = conn.cursor()

    for cs, ce in chunks:
        print(t(f"  AQ+Pollen {cs} → {ce} ...", f"  AQ+pollen {cs} → {ce} ..."))
        # Verwende die lokale Zeitzone des Benutzers für den Datenabruf
        # Die Timestamps werden später in UTC konvertiert
        url  = (f"{AQ_API_URL}?latitude={lat}&longitude={lon}"
                f"&start_date={cs}&end_date={ce}"
                f"&hourly={AQ_HOURLY_VARS}&timezone={TIMEZONE.replace('/', '%2F')}")
        data = _fetch(url)
        if not data:
            continue

        aq_rows, pollen_rows = _aq_aggregate(data, lat, lon)

        cur.executemany(
            AQ_UPSERT,
            [r + (_person,) for r in aq_rows]
        )
        aq_total += cur.rowcount

        cur.executemany(
            POLLEN_UPSERT,
            [r + (_person,) for r in pollen_rows]
        )
        pollen_total += cur.rowcount

    log_import(conn, 'air_quality', '', aq_total + pollen_total, person=_person)
    conn.commit()
    return aq_total, pollen_total


# ── Biometeo ──────────────────────────────────────────────────────────────────

def _biometeo_aggregate(data: dict, lat: float, lon: float) -> list:
    """Aggregation von Biometeorologie-Daten zu Tageswerten.
    
    @purpose.de Umwandlung von Open-Meteo stündlichen/täglichen Daten in Biometeo-Datensätze
    @purpose.en Convert Open-Meteo hourly/daily data to biometeo records
    @method.de Kombiniert tägliche Werte (Sonnenschein, Strahlung, UV-Index, gefühlte Temperatur)
               mit aggregierten stündlichen Werten (Taupunkt, Luftfeuchtigkeit).
               Sonnenscheindauer wird von Sekunden in Stunden umgerechnet.
    @method.en Combine daily values (sunshine, radiation, UV index, apparent temperature)
               with aggregated hourly values (dewpoint, humidity).
               Sunshine duration is converted from seconds to hours.
    @param data API-Antwort von Open-Meteo Archive API
    @param lat Breitengrad für den Standort
    @param lon Längengrad für den Standort
    @returns Liste von Biometeo-Daten-Tuples
    """
    daily  = data.get("daily",  {})
    hourly = data.get("hourly", {})
    times_d = daily.get("time", [])
    times_h = hourly.get("time", [])
    if not times_d:
        return []

    # Pre-aggregate hourly → daily means
    dewpoint = hourly.get("dewpoint_2m", [])
    humidity = hourly.get("relativehumidity_2m", [])
    h_by_day: dict[str, dict] = {}
    for i, ts in enumerate(times_h):
        d = ts[:10]
        if d not in h_by_day:
            h_by_day[d] = {"dew": [], "hum": []}
        h_by_day[d]["dew"].append(dewpoint[i] if i < len(dewpoint) else None)
        h_by_day[d]["hum"].append(humidity[i] if i < len(humidity) else None)

    sunshine  = daily.get("sunshine_duration", [])
    solar     = daily.get("shortwave_radiation_sum", [])
    uv        = daily.get("uv_index_max", [])
    at_max    = daily.get("apparent_temperature_max", [])
    at_min    = daily.get("apparent_temperature_min", [])
    at_mean   = daily.get("apparent_temperature_mean", [])

    def _g(lst, i):
        return lst[i] if i < len(lst) else None

    rows = []
    for i, d in enumerate(times_d):
        sun_s = _g(sunshine, i)
        hday  = h_by_day.get(d, {})
        rows.append((
            d, lat, lon,
            round(sun_s / 3600, 2) if sun_s is not None else None,
            _g(solar, i),
            _g(uv, i),
            _g(at_mean, i),
            _g(at_max,  i),
            _g(at_min,  i),
            _mean(hday.get("dew", [])),
            _mean(hday.get("hum", [])),
        ))
    return rows


def import_biometeo(conn: sqlite3.Connection,
                    lat: float, lon: float,
                    date_from: str | None = None,
                    date_to: str | None = None,
                    update: bool = False,
                    person: str = None) -> int:
    """Import von Biometeorologie-Daten von Open-Meteo Archive API.
    
    @purpose.de Hauptfunktion für den Abruf und Import von Biometeorologie-Daten
    @purpose.en Main function for fetching and importing biometeorology data
    @method.de Prüft fehlende Daten mit _missing, lädt Daten in 90-Tage-Chunks,
               aggregiert mit _biometeo_aggregate und speichert in biometeo-Tabelle.
               Im Update-Modus werden nur fehlende Daten geholt.
    @method.en Check missing data with _missing, fetch data in 90-day chunks,
               aggregate with _biometeo_aggregate and store in biometeo table.
               In update mode, only missing data is fetched.
    @param conn SQLite-Datenbankverbindung
    @param lat Breitengrad
    @param lon Längengrad
    @param date_from Startdatum (ISO-Format, optional, Standard: BIOMETEO_START)
    @param date_to Enddatum (ISO-Format, optional, Standard: heute)
    @param update Nur fehlende Daten ergänzen
    @param person Personen-ID (optional, Standard: OWN_PERSON_ID)
    @returns Anzahl der importierten Biometeo-Datensätze
    """
    _person = person or _OWN_PERSON_ID
    lat, lon = round_coords(lat, lon)
    today = date.today().isoformat()
    start = date_from or BIOMETEO_START
    end   = date_to   or today

    chunks = _date_chunks(_missing(conn, "biometeo", start, end, lat, lon)) if update \
             else [(start, end)]

    total = 0
    cur = conn.cursor()

    for cs, ce in chunks:
        print(t(f"  Biometeo {cs} → {ce} ...", f"  Biometeo {cs} → {ce} ..."))
        # Verwende die lokale Zeitzone des Benutzers für den Datenabruf
        # Die Timestamps werden später in UTC konvertiert
        url = (f"{ARCHIVE_API_URL}?latitude={lat}&longitude={lon}"
               f"&start_date={cs}&end_date={ce}"
               f"&daily={BIOMETEO_DAILY_VARS}"
               f"&hourly={BIOMETEO_HOURLY_VARS}"
               f"&timezone={TIMEZONE.replace('/', '%2F')}")
        data = _fetch(url)
        if not data:
            continue

        rows = _biometeo_aggregate(data, lat, lon)
        cur.executemany(
            "INSERT OR IGNORE INTO biometeo "
            "(date,lat,lon,sunshine_h,solar_mj_m2,uv_index_max,"
            "apparent_temp_mean,apparent_temp_max,apparent_temp_min,"
            "dewpoint_mean,humidity_mean,person) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            [r + (_person,) for r in rows]
        )
        total += cur.rowcount

    log_import(conn, 'biometeo', '', total, person=_person)
    conn.commit()
    return total


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    """Hauptfunktion für den Open-Meteo Import.
    
    @purpose.de Orchestrierung des Import-Prozesses für Luftqualität, Pollen und Biometeo
    @purpose.en Orchestrate import process for air quality, pollen and biometeorology
    @method.de Parsen von CLI-Argumenten, Validierung der Standortangabe,
               Aufruf von import_airquality und import_biometeo,
               Anzeige von Import-Statistiken
    @method.en Parse CLI arguments, validate location,
               call import_airquality and import_biometeo,
               display import statistics
    """
    parser = argparse.ArgumentParser(
        description="Open-Meteo Luftqualität + Pollen + Biometeo → health.db"
    )
    parser.add_argument("--update", action="store_true",
                        help="Nur fehlende Daten ergänzen")
    parser.add_argument("--from", dest="date_from", metavar="DATE")
    parser.add_argument("--to",   dest="date_to",   metavar="DATE")
    parser.add_argument("--lat",  type=float, default=HOME_LAT)
    parser.add_argument("--lon",  type=float, default=HOME_LON)
    parser.add_argument("--no-biometeo", action="store_true",
                        help="Biometeo-Import überspringen")
    parser.add_argument("--no-aq", action="store_true",
                        help="Luftqualität/Pollen-Import überspringen")
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
        f"Importiere Umweltdaten für ({lat_r:.2f}, {lon_r:.2f}) ...",
        f"Importing environmental data for ({lat_r:.2f}, {lon_r:.2f}) ..."
    ))

    if not args.no_aq:
        aq, pollen = import_airquality(
            conn, lat_r, lon_r,
            date_from=args.date_from, date_to=args.date_to, update=args.update
        )
        print(t(
            f"  Luftqualität: {aq} Tage | Pollen: {pollen} Tage",
            f"  Air quality: {aq} days | Pollen: {pollen} days",
        ))

    if not args.no_biometeo:
        bio = import_biometeo(
            conn, lat_r, lon_r,
            date_from=args.date_from, date_to=args.date_to, update=args.update
        )
        print(t(
            f"  Biometeo: {bio} neue Tage",
            f"  Biometeo: {bio} new days",
        ))

    conn.close()


if __name__ == "__main__":
    main()
