#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Expositionsanalyse: Reiseverlauf/Wohnsitz × Ausbruchsdaten

Korreliert travel_history.json + location_stays (GPS-Reisen UND Wohnsitze,
is_home=0/1) mit outbreak_events aus der DB (WHO DON, ECDC NewsRoom, RKI
SurvStat, LGL Bayern, CDC Travel, ProMED, HealthMap, Eurosurveillance,
ReliefWeb, CRM, Endemie-Referenz).

Für jede Reise UND jeden Wohnsitz wird geprüft:
  - Welche Ausbrüche/Endemien waren in dieser Region aktiv?
  - Zeitlicher Überlapp mit dem Aufenthalt?
  - Welche Syndrome sollten berücksichtigt werden?

Wohnsitze (is_home=1) fließen bewusst mit ein, nicht nur Reisen: lokal
übertragene Ausbrüche ohne eigene Reise (z.B. "Flughafenmalaria" durch
eingeschleppte Mücken in Flughafennähe) würden sonst nicht erfasst, da eine
positive Reiseanamnese in der Praxis oft der einzige Trigger ist, an sowas
überhaupt zu denken.

@tier        heuristic
@refs        Kulldorff M (1997). A spatial scan statistic. Communications in Statistics - Theory and Methods, 26(6), 1481-1496. doi:10.1080/03610929708831995
             Brownstein JS, Freifeld CC, Reis BY, Mandl KD (2008). Surveillance Sans Frontières: Internet-based emerging infectious disease intelligence and the HealthMap project. PLoS Medicine, 5(7), e151. doi:10.1371/journal.pmed.0050151
@relevance.de Unterstützt die infektionsbezogene Datenanalyse und Entscheidungsfindung durch systematische Aufbereitung von Wearable- und Symptomdaten
@relevance.en Supports infection-related data analysis and decision-making through systematic processing of wearable and symptom data
@purpose.de  Korreliert Reiseverlauf und Wohnsitze (travel_history.json + location_stays, is_home=0/1) mit Ausbruchs- und Endemie-Daten aus der DB und erstellt eine expositionsbasierte Liste.
@purpose.en  Correlates travel history and home residences (travel_history.json + location_stays, is_home=0/1) with outbreak and endemic patterns data from DB, generating an exposure-based differential assessment list.
@method.de   Geografisches ISO-Länder- und Koordinaten-Radius-Matching (Haversine, GEO_RADIUS_KM_ENDEMIC=200 km, GEO_RADIUS_KM_EXACT=100 km); zeitlicher Überlapp mit Datums-Unschärfe-Puffer (±0/45/180 Tage je nach Präzision des Reisedatums) für Reisen; für Wohnsitze eigene Score-Formel relativ zur Ausbruchsdauer statt zur (oft mehrjährigen) Aufenthaltsdauer; heuristischer Expositions-Score.
@method.en   Geographic ISO-country and coordinate-radius matching (Haversine, GEO_RADIUS_KM_ENDEMIC=200 km, GEO_RADIUS_KM_EXACT=100 km); temporal overlap with date-fuzz buffer (±0/45/180 days depending on trip date precision) for trips; home residences use a separate score formula relative to outbreak duration instead of (often multi-year) residence duration; heuristic exposure score.
@scoring     Expositions-Score (heuristisch, projektintern):
               Reisen:    score = overlap_days / trip_duration  (0.0–1.0)
               Wohnsitze: score = overlap_days / outbreak_duration  (0.0–1.0, s. _temporal_overlap_residence())
               Geografische Radien (Haversine): GEO_RADIUS_KM_ENDEMIC=200 km (Endemie-Referenz, Länder-Zentroid),
                                                GEO_RADIUS_KM_EXACT=100 km (konkreter Ausbruch)
               Datums-Unschärfe (nur Reisen): YYYY-MM-DD=±0 Tage, YYYY-MM=±45 Tage, YYYY=±180 Tage
               Basis: projektintern, keine epidemiologische Validierung.
@limits.de   Heuristische Methode: Koordinaten-Matching via Haversine; Ausbruchsdaten müssen manuell in outbreak_events gepflegt werden; kein Serologienachweis ersetzbar; Ergebnisse nur als Hypothesengeneration zu verstehen; Inkubationspuffer (60 Tage) deckt die meisten Erkrankungen ab, ist aber nicht krankheitsspezifisch kalibriert. Wohnsitz-Score ist eine eigene, unvalidierte Heuristik (Anteil der Ausbruchsdauer, der in die Wohnsitzzeit fällt), nicht direkt mit dem Reise-Score vergleichbar.
@limits.en   Heuristic method: Coordinate matching uses Haversine formula; outbreak data must be manually maintained in outbreak_events; no substitute for serological confirmation; results to be interpreted as hypothesis generation only; incubation buffer (60 days) covers most diseases but is not calibrated per pathogen. Home-residence score is a separate, unvalidated heuristic (share of outbreak duration falling within the residence period), not directly comparable to the trip score.
@reads       outbreak_events, endemic_ref, location_stays
@writes      analyses/infectious/outbreak_exposure_*.{md,txt}

Bekannte Vorinfektionen aus clinical.events (type=infection/reinfection) werden
automatisch in den Bericht einbezogen — kein separates Feld nötig.

Ohne --infection-date: epidemiologisch-forensischer LLM-Prompt (kein Akut-Framing).
Mit --infection-date: akuter/subakuter LLM-Prompt mit Inkubationszeitfilterung.

Usage:
  python3 analyse_outbreak_exposure.py
  python3 analyse_outbreak_exposure.py --from 2020-01-01 --no-llm
  python3 analyse_outbreak_exposure.py --update-db
  python3 analyse_outbreak_exposure.py --infection-date 2023-10-15

@prompt-classification  LLM:Analysis
@prompt.de             SYSTEM_PROMPT_EPIDEMIOLOGICAL (de_only), SYSTEM_PROMPT_ACUTE (de_only)
@prompt.en             -

@usage
    python analyse_outbreak_exposure.py
    python analyse_outbreak_exposure.py --infection-date 2023-10-15
    python analyse_outbreak_exposure.py --from 2024-01-01 --no-llm
"""
import argparse
import math
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from health_config import Config as _Cfg, OWN_PERSON_ID
from modules.db import open_db, DB_ERRORS
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from modules.airport_proximity import home_airport_risk_exposures
from modules.endemic_matching import (
    geo_dist_km as _geo_dist, resolve_radius_km, since_floor_ok,
    TIMELESS_SOURCES as _TIMELESS_SOURCES,
    RADIUS_KM_EVENT_DEFAULT,
)

_cfg = _Cfg()
OUT_DIR = _cfg.analyses_dir / "infectious"

# Datum-Unschärfe: Wenn ein Reisedatum nur auf Monat/Jahr bekannt ist,
# wird das Reisefenster entsprechend ausgedehnt (nicht das Ausbruchsfenster).
DATE_FUZZ_DAY   =   0   # exaktes Datum (YYYY-MM-DD) → kein Extra-Puffer
DATE_FUZZ_MONTH =  45   # nur Monat bekannt (YYYY-MM) → ±45 Tage
DATE_FUZZ_YEAR  = 180   # nur Jahr bekannt (YYYY)     → ±180 Tage


# ── Helferfunktionen ────────────────────────────────────────────────────────

def _parse_date_flexible(date_str: str | None) -> tuple[datetime | None, str]:
    """Parsed verschiedene Datumsformate. Gibt (datetime, precision) zurück.

    precision ist 'day' | 'month' | 'year' — zeigt an, wie unscharf das Datum ist.
    Gibt den 15. des Monats zurück, falls nur Monat/Jahr angegeben (Mitte des Monats).
    Gibt den 15. Juni zurück, falls nur Jahr angegeben (Mitte des Jahres).
    """
    if not date_str:
        return None, "day"

    date_str = date_str.strip()

    # Format: YYYY-MM-DD
    try:
        return datetime.strptime(date_str, "%Y-%m-%d"), "day"
    except ValueError:
        pass

    # Format: YYYY-MM (z.B. 1994-05) -> 15. des Monats
    try:
        parts = date_str.split("-")
        if len(parts) == 2:
            year, month = parts
            return datetime(int(year), int(month), 15), "month"
    except (ValueError, IndexError):
        pass

    # Format: MM/YYYY (z.B. 05/1994) -> 15. des Monats
    try:
        if "/" in date_str:
            parts = date_str.split("/")
            if len(parts) == 2:
                month, year = parts
                return datetime(int(year), int(month), 15), "month"
    except (ValueError, IndexError):
        pass

    # Format: YYYY (ganzes Jahr) -> 15. Juni
    try:
        year = int(date_str)
        return datetime(year, 6, 15), "year"
    except (ValueError, TypeError):
        pass

    return None, "day"


def _date_fuzz(precision: str) -> int:
    """Gibt den Datums-Unschärfe-Puffer in Tagen für eine gegebene Präzision zurück."""
    return {
        "day":   DATE_FUZZ_DAY,
        "month": DATE_FUZZ_MONTH,
        "year":  DATE_FUZZ_YEAR,
    }.get(precision, DATE_FUZZ_MONTH)


def _date_within_tolerance(date1: datetime | None, date2: datetime | None,
                           tolerance_days: int) -> bool:
    """Prüft ob zwei Daten innerhalb der Toleranz liegen."""
    if not date1 or not date2:
        return True
    return abs((date1 - date2).days) <= tolerance_days


# ── Geo-Matching ──────────────────────────────────────────────────────────────
# _geo_dist, resolve_radius_km, since_floor_ok, _TIMELESS_SOURCES kommen jetzt
# aus modules.endemic_matching (s. Imports oben) statt hier dupliziert zu sein.


def _region_match(trip: dict, outbreak: dict) -> bool:
    """Prüft ob Ausbruch geografisch zum Reiseziel passt.
    
    Priorität: Region > Subregion > Koordinaten > Land (nur als Fallback)
    
    WICHTIG: Trennt klar zwischen Inselgruppen (z.B. Kanaren vs. Balearen),
    um Fehlzuordnungen wie "Teneriffa -> Mallorca-Ausbrüche" zu vermeiden.
    """
    # Normalisierte Felder
    t_country = (trip.get("country") or "").lower()
    t_iso = (trip.get("country_iso") or "").lower()
    t_region = (trip.get("region") or "").lower()
    t_subregion = (trip.get("subregion") or "").lower()
    t_city = (trip.get("city") or "").lower()
    t_name = (trip.get("name") or "").lower()
    
    o_country = (outbreak.get("country") or "").lower()
    o_iso = (outbreak.get("country_iso") or "").lower()
    o_region = (outbreak.get("region") or "").lower()
    
    # 1. EXAKTE REGION-ÜBEREINSTIMMUNG (höchste Priorität)
    #    z.B. "Mallorca" == "Mallorca" oder "Teneriffa" == "Teneriffa"
    if o_region:
        region_fields = [t_region, t_subregion, t_city, t_name]
        for field in region_fields:
            if field and field == o_region:
                return True
        
        # Fuzzy: trip-Region in outbreak-Region oder umgekehrt
        for field in region_fields:
            if field and o_region and (field in o_region or o_region in field):
                return True
    
    # 2. INSELGRUPPEN: Kanaren vs. Balearen sind UNTERSCHIEDLICH!
    #    Verhindert Fehlzuordnung von Kanarischen Inseln zu Balearen (und umgekehrt)
    kanarische_inseln = {"teneriffa", "fuerteventura", "gran canaria", "lanzarote", 
                        "la palma", "la gomera", "el hierro", "kanarische inseln", 
                        "kanaren", "canary islands", "canaries"}
    balearen = {"mallorca", "ibiza", "menorca", "formentera", "cabrera",
               "balearen", "balearic islands", "balearics"}
    
    # Extrahiere Insel-Keywords aus beiden Seiten
    trip_inseln = {t_region, t_subregion, t_city, t_name}
    outbreak_inseln = {o_region}
    
    # Wenn trip zu Kanaren gehört und outbreak zu Balearen (oder umgekehrt) -> NO MATCH
    trip_ist_kanarisch = any(k in w for w in trip_inseln for k in kanarische_inseln if w)
    outbreak_ist_kanarisch = any(k in w for w in outbreak_inseln for k in kanarische_inseln if w)
    trip_ist_balearisch = any(b in w for w in trip_inseln for b in balearen if w)
    outbreak_ist_balearisch = any(b in w for w in outbreak_inseln for b in balearen if w)
    
    if (trip_ist_kanarisch and outbreak_ist_balearisch) or \
       (trip_ist_balearisch and outbreak_ist_kanarisch):
        return False  # Kanaren und Balearen sind GEOGRAFISCH GETRENNT
    
    # 3. SUBREGION / CITY MATCH
    #    z.B. "Can Picafort" (Mallorca) vs. "S'Albufera Mallorca"
    if t_subregion and o_region:
        if t_subregion == o_region or o_region in t_subregion or t_subregion in o_region:
            return True
    
    if t_city and o_region:
        if t_city == o_region or o_region in t_city or t_city in o_region:
            return True
    
    # 4. KOORDINATEN-RADIUS (falls beide lat/lon haben)
    #    ISO-Code oder Länder-Text müssen übereinstimmen, wenn beide vorhanden —
    #    kein grenzüberschreitendes Match (z.B. Bayern → Norditalien).
    #    Fehlt die Länder-Info auf Reiseseite, wird ein engerer Radius verwendet.
    t_lat = trip.get("lat") or trip.get("_lat")
    t_lon = trip.get("lon") or trip.get("_lon")
    o_lat = outbreak.get("lat")
    o_lon = outbreak.get("lon")
    if t_lat and o_lat:
        has_t_country = bool(t_iso or t_country)
        has_o_country = bool(o_iso or o_country)
        if has_t_country and has_o_country:
            iso_match     = t_iso and o_iso and t_iso == o_iso
            country_match = t_country and o_country and (t_country in o_country or o_country in t_country)
            if not iso_match and not country_match:
                pass  # Länder inkompatibel → kein Koordinaten-Match
            else:
                radius = resolve_radius_km(outbreak)
                if _geo_dist(float(t_lat), float(t_lon), float(o_lat), float(o_lon)) <= radius:
                    return True
        else:
            # Keine Länder-Info vorhanden (z.B. ungeocodete Wohnsitz-Aufenthalte)
            # → enger Radius als Sicherheitsnetz, ABER ein landkreisgenauer
            # radius_km-Override auf dem Eintrag selbst gilt weiterhin: das
            # Fehlen von Länder-Info auf der Reiseseite darf eine bewusst eng
            # gesetzte Praezision nicht wieder aufweiten (sonst matcht z.B. ein
            # 38 km entfernter, nie geocodeter Wohnsitz faelschlich gegen einen
            # Landkreis-Eintrag mit radius_km=20).
            radius = outbreak.get("radius_km") or min(RADIUS_KM_EVENT_DEFAULT, 50.0)
            if _geo_dist(float(t_lat), float(t_lon), float(o_lat), float(o_lon)) <= radius:
                return True
    
    # 5a. "Gesamt*"-Einträge treffen immer das gesamte Land (ISO-Match reicht)
    #     z.B. "Gesamtkroatien", "Gesamtdeutschland" — subregion der Reise egal
    if o_region and o_region.startswith("gesamt"):
        if t_iso and o_iso and t_iso == o_iso:
            return True
        if t_country and o_country and (t_country in o_country or o_country in t_country):
            return True

    # 5b. LANDESWEITES MATCHING (niedrigste Priorität - nur wenn keine Region-Info)
    #     Nur anwenden, wenn KEINE spezifische Region/Subregion vorhanden ist
    if not o_region and not t_region and not t_subregion:
        # ISO-Code Match
        if t_iso and o_iso and t_iso == o_iso:
            return True

        # Länder-Name fuzzy (nur wenn ISO fehlt)
        if t_country and o_country and (t_country in o_country or o_country in t_country):
            return True

    return False


def _temporal_overlap(trip_from: str, trip_to: str,
                      outbreak_start: str | None,
                      outbreak_end: str | None,
                      outbreak_date: str) -> tuple[int, float]:
    """Berechnet Überlapp in Tagen und Score (0–1).

    Das Reisefenster wird je nach Datums-Präzision ausgedehnt (Datums-Unschärfe):
      - exaktes Datum (YYYY-MM-DD): kein Puffer
      - Monatsangabe (YYYY-MM):     ±45 Tage
      - Jahresangabe (YYYY):        ±180 Tage
    Das Ausbruchsfenster bleibt unverändert wie in der DB gespeichert.
    """
    # Parse Reise-Daten + Präzision
    t0, prec_from = _parse_date_flexible(trip_from)
    t1, prec_to   = _parse_date_flexible(trip_to)
    if not t0 or not t1:
        return 0, 0.0

    # Reisefenster nach Datums-Unschärfe aufblähen
    fuzz = max(_date_fuzz(prec_from), _date_fuzz(prec_to))
    t0 = t0 - timedelta(days=fuzz)
    t1 = t1 + timedelta(days=fuzz)

    # Falls gleicher Mittelpunkt (z.B. Einzel-Tag), mindestens 1 Tag
    if t0 == t1:
        t1 = t0 + timedelta(days=1)

    # Parse Ausbruch-Daten (unverändert, kein künstlicher Puffer)
    o_ref = outbreak_start or outbreak_date
    o0, _ = _parse_date_flexible(o_ref)

    if outbreak_end:
        o1, _ = _parse_date_flexible(outbreak_end)
    else:
        o1 = None

    if o0:
        if not o1:
            o1 = o0 + timedelta(days=365)  # kein End-Datum: 1 Jahr annehmen
    else:
        o0_fb, _ = _parse_date_flexible(outbreak_date)
        if o0_fb:
            o0 = o0_fb
            o1 = o0_fb + timedelta(days=365)
        else:
            return 0, 0.0

    if not o0 or not o1:
        return 0, 0.0

    # Schnittmenge
    overlap_start = max(t0, o0)
    overlap_end   = min(t1, o1)
    days = max(0, (overlap_end - overlap_start).days)

    trip_dur = max(1, (t1 - t0).days)
    score = min(1.0, days / trip_dur)
    return days, round(score, 3)


def _temporal_overlap_residence(res_from: str, res_to: str,
                                outbreak_start: str | None,
                                outbreak_end: str | None,
                                outbreak_date: str) -> tuple[int, float]:
    """Wie _temporal_overlap(), aber für dauerhafte Wohnsitze statt Reisen.

    Ein Wohnsitz-Zeitraum kann viele Jahre umfassen, während ein Ausbruch meist
    nur Wochen/Monate aktiv ist. score = überlappende Tage / trip_duration
    (wie bei Reisen) würde hier fast immer nahe 0 liegen, selbst bei voller
    Deckung des Ausbruchs — das Maß wäre für die Fragestellung "war ich während
    des gesamten Ausbruchs an diesem Ort wohnhaft" bedeutungslos. Score daher
    stattdessen relativ zur AUSBRUCHS-Dauer: Anteil des Ausbruchszeitraums,
    der in die Wohnsitzzeit fällt (1.0 = während der gesamten aktiven
    Ausbruchsphase dort wohnhaft).
    """
    r0, _ = _parse_date_flexible(res_from)
    r1, _ = _parse_date_flexible(res_to)
    if not r0 or not r1:
        return 0, 0.0
    if r0 == r1:
        r1 = r0 + timedelta(days=1)

    o_ref = outbreak_start or outbreak_date
    o0, _ = _parse_date_flexible(o_ref)
    if outbreak_end:
        o1, _ = _parse_date_flexible(outbreak_end)
    else:
        o1 = None
    if o0:
        if not o1:
            o1 = o0 + timedelta(days=365)  # kein End-Datum: 1 Jahr annehmen
    else:
        o0_fb, _ = _parse_date_flexible(outbreak_date)
        if o0_fb:
            o0 = o0_fb
            o1 = o0_fb + timedelta(days=365)
        else:
            return 0, 0.0
    if not o0 or not o1:
        return 0, 0.0

    overlap_start = max(r0, o0)
    overlap_end   = min(r1, o1)
    days = max(0, (overlap_end - overlap_start).days)

    outbreak_dur = max(1, (o1 - o0).days)
    score = min(1.0, days / outbreak_dur)
    return days, round(score, 3)


# ── DB-Funktionen ─────────────────────────────────────────────────────────────

def load_outbreaks(conn: sqlite3.Connection, dfrom: str = "2010-01-01") -> list[dict]:
    rows = conn.execute("""
        SELECT id, source, disease, syndrome_slug, country, country_iso,
               region, lat, lon, date_reported, date_start, date_end, severity, title,
               radius_km, note, since_date
        FROM outbreak_events
        WHERE date_reported >= ?
        ORDER BY date_reported DESC
    """, (dfrom,)).fetchall()
    cols = ["id", "source", "disease", "syndrome_slug", "country", "country_iso",
            "region", "lat", "lon", "date_reported", "date_start", "date_end",
            "severity", "title", "radius_km", "note", "since_date"]
    return [dict(zip(cols, r)) for r in rows]


def load_gps_stays(conn: sqlite3.Connection, dfrom: str = "2010-01-01") -> list[dict]:
    """Nicht-Heimaufenthalte aus location_stays mit Geocoding-Info.

    GPS-Punkte innerhalb derselben Geocoding-Region und desselben Monats werden
    zu einem einzigen Eintrag geclustert — verhindert n-fache Wiederholung
    identischer Endemie-Treffer für denselben Aufenthaltsort.
    """
    rows = conn.execute("""
        SELECT ls.id, ls.start_ts, ls.end_ts, ls.lat, ls.lon,
               COALESCE(g.country, '') as country,
               COALESCE(g.country_iso, '') as country_iso,
               COALESCE(g.subregion, '') as subregion,
               COALESCE(g.city, '') as city
        FROM location_stays ls
        LEFT JOIN location_stays_geocoded g ON g.stay_id = ls.id
        WHERE ls.is_home = 0 AND ls.start_ts >= ?
        ORDER BY ls.start_ts
    """, (dfrom,)).fetchall()

    # Cluster nach (country_iso, subregion, YYYY-MM)
    clusters: dict[str, dict] = {}
    for r in rows:
        lat, lon  = r[3], r[4]
        country   = r[5] or ""
        iso       = r[6] or ""
        subregion = r[7] or ""
        city      = r[8] or ""
        date_from = r[1][:10] if r[1] else ""
        date_to   = r[2][:10] if r[2] else date_from
        month     = date_from[:7]  # YYYY-MM

        key = f"{iso}|{subregion or city}|{month}"
        if key not in clusters:
            label = city or subregion or iso or f"GPS {float(lat):.2f},{float(lon):.2f}"
            clusters[key] = {
                "name":        label,
                "date_from":   date_from,
                "date_to":     date_to,
                "_lat":        lat,
                "_lon":        lon,
                "country":     country,
                "country_iso": iso,
                "subregion":   subregion,
                "source_type": "gps",
                "_n":          1,
            }
        else:
            c = clusters[key]
            if date_from and date_from < c["date_from"]:
                c["date_from"] = date_from
            if date_to and date_to > c["date_to"]:
                c["date_to"] = date_to
            c["_n"] += 1

    # n > 1 → Zähler in den Namen einbauen
    result = []
    for c in clusters.values():
        n = c.pop("_n")
        if n > 1:
            c["name"] = f"{c['name']} ({n} Aufenthalte)"
        result.append(c)

    result.sort(key=lambda x: x["date_from"])
    return result


def load_home_stays(conn: sqlite3.Connection, dfrom: str = "2010-01-01") -> list[dict]:
    """Heimaufenthalte (is_home=1) aus location_stays mit Geocoding-Info.

    Anders als load_gps_stays(): Wohnort-Zeiträume sind dauerhaft (nicht auf
    eine kurze Reise begrenzt), daher kein "trip_duration" für den Score
    verfügbar — die Auswertung nutzt stattdessen _temporal_overlap_residence()
    (Score relativ zur Ausbruchsdauer statt zur Aufenthaltsdauer).
    Ohne Ende (noch aktueller Wohnsitz) wird end_ts auf "heute" gesetzt.

    Clustert nach gerundeter Koordinate (3 Nachkommastellen ≈ 111m), aber NUR
    über zeitlich AUFEINANDERFOLGENDE Zeilen (Verarbeitung in start_ts-
    Reihenfolge) — nicht global über die gesamte Historie. location_stays kann
    denselben Wohnort-Zeitraum als viele (nahezu) identische Zeilen enthalten
    (z.B. wiederholte Home-Assistant-Snapshots); ohne Clustering würde jede
    dieser Zeilen einen eigenen, redundanten Expositions-Treffer erzeugen
    (s. load_gps_stays(), dasselbe Muster dort schon gegen wiederholte
    Endemie-Treffer gelöst). Ein rein globales Koordinaten-Clustering (ohne
    Zeit-Kontiguität) wuerde dagegen einen Wegzug und eine spaetere Rueckkehr
    an denselben Ort faelschlich zu einem einzigen durchgehenden Zeitraum
    verschmelzen und die dazwischenliegende, andernorts verbrachte Zeit
    verschlucken — relevant sobald Wohnsitz-Historie ueber mehrere,
    nicht zwingend chronologisch sortierte Lebensabschnitte hinweg erfasst wird.
    """
    rows = conn.execute("""
        SELECT ls.id, ls.start_ts, ls.end_ts, ls.lat, ls.lon,
               COALESCE(g.country, '') as country,
               COALESCE(g.country_iso, '') as country_iso,
               COALESCE(g.subregion, '') as subregion,
               COALESCE(g.city, '') as city
        FROM location_stays ls
        LEFT JOIN location_stays_geocoded g ON g.stay_id = ls.id
        WHERE ls.is_home = 1 AND (ls.end_ts IS NULL OR ls.end_ts >= ?)
        ORDER BY ls.start_ts
    """, (dfrom,)).fetchall()

    today = datetime.now().strftime("%Y-%m-%d")
    result: list[dict] = []
    current: dict | None = None
    current_key: tuple | None = None
    for r in rows:
        lat, lon  = r[3], r[4]
        country   = r[5] or ""
        iso       = r[6] or ""
        subregion = r[7] or ""
        city      = r[8] or ""
        date_from = r[1][:10] if r[1] else ""
        date_to   = r[2][:10] if r[2] else today
        if not date_from or lat is None or lon is None:
            continue
        key = (round(float(lat), 3), round(float(lon), 3))
        if current is not None and key == current_key:
            if date_from < current["date_from"]:
                current["date_from"] = date_from
            if date_to > current["date_to"]:
                current["date_to"] = date_to
            continue
        if current is not None:
            result.append(current)
        label = city or subregion or iso or f"Wohnsitz {float(lat):.2f},{float(lon):.2f}"
        current = {
            "name":        f"Wohnsitz {label}",
            "date_from":   date_from,
            "date_to":     date_to,
            "_lat":        lat,
            "_lon":        lon,
            "country":     country,
            "country_iso": iso,
            "subregion":   subregion,
            "source_type": "home_residence",
        }
        current_key = key
    if current is not None:
        result.append(current)

    result.sort(key=lambda x: x["date_from"])
    return result


def compute_exposures(conn: sqlite3.Connection,
                      dfrom: str = "2010-01-01") -> list[dict]:
    """Berechnet alle Expositions-Treffer und speichert sie."""
    outbreaks = load_outbreaks(conn, dfrom)
    if not outbreaks:
        return []

    travel  = _cfg.travel_history
    gps     = load_gps_stays(conn, dfrom)
    home    = load_home_stays(conn, dfrom)
    all_trips = [
        {**trip, "source_type": "travel_history"} for trip in travel
    ] + gps + home

    now    = datetime.now().isoformat()
    found  = []
    conn.execute("DELETE FROM outbreak_exposure WHERE computed_at >= ?",
                 (dfrom,))

    for trip in all_trips:
        t_from = trip.get("date_from", "")
        t_to   = trip.get("date_to") or t_from
        if not t_from:
            continue
        
        # Parse Reise-Datum (Handhabung verschiedener Formate wie "05/1994", "1994-05", "1994-05-15")
        trip_date, trip_prec = _parse_date_flexible(t_from)
        if not trip_date:
            continue

        for ob in outbreaks:
            # 1. GEOGRAFISCHES MATCHING (Region > Land)
            if not _region_match(trip, ob):
                continue

            is_home = trip.get("source_type") == "home_residence"

            # 1b. SINCE-FLOOR (nur fuer juengere, aktiv expandierende Endemie-
            #     Risiken gesetzt, z.B. Tigermuecken-Landkreise — NICHT fuer
            #     seit jeher endemische Risiken wie FSME/Malariazonen, deren
            #     since_date NULL bleibt). Ein Aufenthalt, der komplett vor
            #     since_date endete, kann dieses Risiko nicht betroffen haben.
            if ob.get("source") in _TIMELESS_SOURCES:
                stay_end_dt, _ = _parse_date_flexible(t_to)
                if not stay_end_dt:
                    stay_end_dt, _ = _parse_date_flexible(t_from)
                if not since_floor_ok(ob.get("since_date"), stay_end_dt):
                    continue  # Aufenthalt lag vor der dokumentierten Entstehung des Risikos

            # 2. ZEITLICHES MATCHING
            #    Für konkrete Ausbrüche (nicht endemic_ref): Grob-Filter ob Ausbruchs-
            #    datum überhaupt in der Nähe des Reisedatums liegt. Das Reisefenster
            #    wird dabei um die Datums-Unschärfe erweitert (±45 Tage bei Monats-,
            #    ±180 Tage bei Jahresangabe).
            #    Bei Wohnsitzen (is_home) entfällt dieser Grob-Filter: Der Zeitraum
            #    ist ein dauerhafter Aufenthalt statt eines Einzeldatums, der Filter
            #    würde Ausbrüche Jahre nach Einzugsdatum fälschlich ausschließen —
            #    _temporal_overlap_residence() prüft die volle Zeitspanne ohnehin exakt.
            if ob.get("source") not in _TIMELESS_SOURCES and not is_home:
                outbreak_ref = ob.get("date_reported") or ob.get("date_start") or ob.get("date_end") or ""
                outbreak_date, _ = _parse_date_flexible(outbreak_ref)
                if outbreak_date and trip_date:
                    fuzz = _date_fuzz(trip_prec)
                    if not _date_within_tolerance(trip_date, outbreak_date, fuzz + 365):
                        continue  # Ausbruch weit außerhalb des gefuzzten Reisefensters

            if is_home:
                days, score = _temporal_overlap_residence(
                    t_from, t_to, ob["date_start"], ob["date_end"], ob["date_reported"])
            else:
                days, score = _temporal_overlap(
                    t_from, t_to, ob["date_start"], ob["date_end"], ob["date_reported"])

            if score == 0 and ob["source"] not in _TIMELESS_SOURCES:
                continue  # Endemie-Referenz/FSME immer relevant wenn geo-match

            exposure = {
                "trip_name":     trip.get("name", ""),
                "trip_country":  trip.get("country", ""),
                "trip_region":   trip.get("subregion", ""),
                "trip_date_from": t_from,
                "trip_date_to":   t_to,
                "outbreak":      ob,
                "overlap_days":  days,
                "exposure_score": score,
                "source":        trip.get("source_type", "travel_history"),
            }
            found.append(exposure)

            try:
                conn.execute("""
                    INSERT INTO outbreak_exposure
                    (trip_name, trip_country, trip_region, trip_date_from, trip_date_to,
                     outbreak_id, overlap_days, exposure_score, source, computed_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?)
                """, (trip.get("name"), trip.get("country"), trip.get("subregion"),
                      t_from, t_to, ob["id"], days, score,
                      trip.get("source_type"), now))
            except DB_ERRORS:
                pass

    conn.commit()
    return found


# ── Bericht ───────────────────────────────────────────────────────────────────

# ── Bekannte Vorinfektionen aus clinical.events ───────────────────────────────

# Mapping: Textfragmente in event["name"] → syndrome_slug
_KNOWN_INFECTION_SLUG_MAP: list[tuple[str, str]] = [
    ("windpocken", "vzv"), ("varizell", "vzv"), ("zoster", "vzv"),
    ("masern", "masern"), ("morbilli", "masern"),
    ("mumps", "post_mumps"), ("parotitis", "post_mumps"),
    ("ebv", "ebv"), ("epstein", "ebv"), ("pfeiffersches", "ebv"), ("mononukleose", "ebv"),
    ("influenza", "influenza"), ("grippe", "influenza"),
    ("covid", "post_covid"), ("sars-cov", "post_covid"),
    ("borreli", "borreliose"), ("lyme", "borreliose"),
    ("cmv", "cmv"), ("zytomegalie", "cmv"),
    ("dengue", "dengue"),
    ("chikungunya", "chikungunya"),
    ("hepatitis a", "hepatitis_a"), ("hepatitis b", "hepatitis_b"), ("hepatitis c", "generic"),
    ("scharlach", "post_strep"), ("streptokokken", "post_strep"),
    ("q-fieber", "q_fieber"), ("coxiella", "q_fieber"),
    ("röteln", "generic"), ("rubeola", "generic"), ("rubella", "generic"),
    ("keuchhusten", "generic"), ("pertussis", "generic"),
    ("typhus", "typhus"), ("typhoid", "typhus"),
    ("mpox", "mpox"), ("affenpocken", "mpox"), ("monkeypox", "mpox"),
    ("malaria", "malaria"),
]


def _slug_for_event(name: str) -> str:
    """Gibt den besten Syndrom-Slug für ein klinisches Ereignis zurück."""
    lower = name.lower()
    for fragment, slug in _KNOWN_INFECTION_SLUG_MAP:
        if fragment in lower:
            return slug
    return "generic"


def _load_known_infections() -> list[dict]:
    """Liest alle Infektionsereignisse aus clinical.events (type infection/reinfection)."""
    events = _cfg.events_of_type("infection", "reinfection")
    result = []
    for e in events:
        result.append({
            "name":  e.get("name", ""),
            "date":  e.get("date", ""),
            "type":  e.get("type", "infection"),
            "slug":  _slug_for_event(e.get("name", "")),
            "notes": e.get("notes", ""),
        })
    return result


def _load_known_risk_exposures() -> list[dict]:
    """Liest persönliche Dauerrisiko-Expositionen aus known_risk_exposures.json."""
    return _cfg.known_risk_exposures


def _load_all_risk_exposures(conn: sqlite3.Connection | None) -> list[dict]:
    """Manuell gepflegte + automatisch erkannte Dauerrisiko-Expositionen zusammengeführt.

    Manuell: known_risk_exposures.json. Automatisch: aktuell nur
    Flughafennähe des Wohnorts (modules/airport_proximity.py) — strukturelles
    Risiko unabhängig von einem konkret gemeldeten Ausbruch.
    """
    result = list(_load_known_risk_exposures())
    if conn is not None:
        try:
            result += home_airport_risk_exposures(conn)
        except Exception:
            pass  # Fehlende Geocoding-Daten o.ä. dürfen den Bericht nicht abbrechen
    return result


def build_report(exposures: list[dict], conn: sqlite3.Connection | None = None) -> str:
    # Strukturelle Standortrisiken (z.B. Flughafennähe) sind unabhängig von
    # konkreten Ausbruchs-Treffern — deshalb NICHT Teil des frühen "keine
    # Treffer"-Abbruchs unten, sondern vorab geprüft, damit der Bericht bei
    # 0 Reise-/Ausbruchs-Treffern trotzdem weiterläuft statt abzubrechen.
    try:
        structural_risks = home_airport_risk_exposures(conn) if conn is not None else []
    except Exception:
        structural_risks = []

    if not exposures and not structural_risks:
        return (
            "## Expositionsanalyse: Reise/Wohnsitz × Ausbrüche\n\n"
            "Keine Treffer — entweder keine Reise-/Wohnsitzdaten in "
            "travel_history.json bzw. location_stays oder keine passenden "
            "Ausbrüche in der Datenbank.\n"
            "Tipp: `python3 importers/import_outbreak_data.py` ausführen.\n"
        )

    # Nach Reise gruppieren
    by_trip: dict[str, list] = defaultdict(list)
    for ex in exposures:
        key = f"{ex['trip_name']} ({ex['trip_date_from'][:7]})"
        by_trip[key].append(ex)

    # ── Erster Pass: slug_trips für Zusammenfassung am Anfang aggregieren ────
    slug_trips: dict[str, list[str]] = defaultdict(list)
    detail_lines: list[str] = []

    today_str = datetime.now().strftime("%Y-%m-%d")
    for trip_key, exs in sorted(by_trip.items()):
        trip_date = exs[0]["trip_date_from"][:10] if exs else ""
        time_tag = "[GEPLANT]" if trip_date > today_str else "[VERGANGENHEIT]"
        detail_lines.append(f"### {trip_key} {time_tag}\n")

        exs_sorted = sorted(exs, key=lambda x: (
            x["outbreak"]["source"] in _TIMELESS_SOURCES,
            -x["exposure_score"]
        ))

        for ex in exs_sorted:
            ob    = ex["outbreak"]
            slug  = ob.get("syndrome_slug") or "generic"
            src   = ob["source"]
            sev   = ob.get("severity", "")
            score = ex["exposure_score"]
            days  = ex["overlap_days"]

            sev_icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(sev, "⚪")
            src_icon = {
                "who_don":    "WHO",
                "ecdc":       "ECDC",
                "promedmail": "ProMED",
                "endemic_ref":"Endemie",
                "lgl_fsme":   "FSME",
            }.get(src, src)

            if src in _TIMELESS_SOURCES:
                if ob.get("since_date"):
                    timing = f"endemisch seit {ob['since_date'][:4]} (kein Enddatum)"
                else:
                    timing = "endemisch (kein Zeitlimit)"
            elif days > 0:
                timing = f"Überlapp: {days} Tage (Score {score:.2f})"
            else:
                timing = f"kein direkter Überlapp (Score {score:.2f})"

            detail_lines.append(
                f"  [{src_icon}] {sev_icon} **{ob['disease']}** — "
                f"{ob.get('region') or ob.get('country', '')}"
                f"  →  `{slug}`  |  {timing}"
            )
            if ob.get("title") and ob["title"] != ob["disease"]:
                detail_lines.append(f"       _{ob['title']}_")
            if ob.get("note"):
                detail_lines.append(f"       {ob['note']}")

            if slug != "generic":
                slug_trips[slug].append(ex["trip_name"])

        detail_lines.append("")

    # ── Zusammenfassung: steht VOR dem geografischen Detail ──────────────────
    # So landet sie im top-25-Zeilen-Fenster der Synthese und geht nicht verloren.
    lines: list[str] = [
        "## Expositionsanalyse: Reise/Wohnsitz × Ausbrüche / Endemien\n",
        f"Aufenthalte analysiert: {len(by_trip)}  |  Expositions-Treffer: {len(exposures)}\n",
        "⚠ Zeitliche/geografische Nähe ≠ kausale Exposition. Hypothesengenerierend.\n",
    ]

    # ── Bekannte Vorinfektionen aus clinical.events ──────────────────────────
    known = _load_known_infections()
    known_slugs: set[str] = set()
    if known:
        lines += [
            "### Bekannte Vorinfektionen (aus klinischen Ereignissen)\n",
            "Einträge aus `clinical.events` mit type=infection/reinfection:\n",
        ]
        for ki in known:
            tag = "[REINFEKTION]" if ki["type"] == "reinfection" else ""
            lines.append(
                f"  - **{ki['name']}** ({ki['date']}) {tag}"
                f"  →  `{ki['slug']}`"
                + (f"  — {ki['notes']}" if ki["notes"] else "")
            )
            if ki["slug"] != "generic":
                known_slugs.add(ki["slug"])
        lines.append("")

    # ── Persönliche Dauerrisiko-Expositionen (manuell + automatisch erkannt) ──
    risk_exposures = _load_all_risk_exposures(conn)
    risk_slugs: set[str] = set()
    if risk_exposures:
        level_icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}
        lines += [
            "### Persönliche Dauerrisiko-Expositionen\n",
            "Chronische/kumulative Expositionen (manuell aus `known_risk_exposures` "
            "und automatisch erkannt, z.B. Flughafennähe) — erhöhen die "
            "Vortest-Wahrscheinlichkeit gegenüber Populationsdurchschnitt:\n",
        ]
        for rx in risk_exposures:
            slug   = rx.get("slug", "generic")
            icon   = level_icon.get(rx.get("level", "medium"), "⚪")
            desc   = rx.get("description", "")
            notes  = rx.get("notes", "")
            origin = "🤖 automatisch erkannt" if rx.get("auto") else "✍️ manuell (known_risk_exposures.json)"
            lines.append(
                f"  {icon} `{slug}` [{origin}] — {desc}"
                + (f"  ({notes})" if notes else "")
            )
            if slug != "generic":
                risk_slugs.add(slug)
        lines.append("")

        # Slugs die SOWOHL in Reise/Vorinfektionen ALS AUCH in Dauerrisiken auftauchen
        overlap = risk_slugs & (slug_trips.keys() | known_slugs)
        if overlap:
            lines += [
                f"⚠️ **Erhöhte Priorität** (Reise/Vorinfektion + Dauerrisiko überlappen): "
                f"`{'`, `'.join(sorted(overlap))}`\n",
                "→ Diese Syndrome haben aufgrund der persönlichen Expositionsbiografie "
                "eine deutlich höhere Vortest-Wahrscheinlichkeit als Populationswerte.\n",
            ]

    # Nicht nur bei Reise-Treffern (slug_trips) zeigen — ein rein strukturelles
    # Dauerrisiko (z.B. automatisch erkannte Flughafennähe) oder eine bekannte
    # Vorinfektion ohne passenden Reise-Treffer soll ebenfalls einen konkreten
    # --syndrome-Befehl liefern, nicht stillschweigend übergangen werden.
    if slug_trips or risk_slugs or known_slugs:
        ranked = sorted(slug_trips.items(), key=lambda x: -len(x[1]))
        # Slugs aus Reise + Vorinfektionen + Dauerrisiken zusammenführen.
        # Reihenfolge: Overlap zuerst (höchste Priorität), dann Dauerrisiken
        # (aktives Standing-Risiko, inkl. automatisch erkannter wie Flughafen-
        # nähe) VOR bereits abgeschlossenen Vorinfektionen — sonst kann eine
        # lange known_infections-Historie ein neu erkanntes Dauerrisiko aus der
        # Kappung unten verdrängen, obwohl das gerade der wichtigste neue
        # Hinweis wäre.
        overlap_first = sorted(risk_slugs & (slug_trips.keys() | known_slugs))
        all_slugs = list(dict.fromkeys(
            overlap_first
            + sorted(risk_slugs)
            + [s for s, _ in ranked[:6]]
            + sorted(known_slugs)
        ))
        slug_args = " ".join(all_slugs[:10])
        lines += [
            "### Empfohlene Syndrome für Differenzialdiagnose\n",
            "Basierend auf Reiseexposition, Vorinfektionen und Dauerrisiken "
            "(inkl. automatisch erkannter) — direkt an "
            "`analyse_postinfectious_diagnose.py` übergeben:\n",
        ]
        for slug, trips in ranked:
            unique_trips = list(dict.fromkeys(trips))[:3]
            lines.append(f"  - `{slug}`: {', '.join(unique_trips)}")
        lines += [
            "",
            "```bash",
            "python3 analyse_postinfectious_diagnose.py \\",
            "  --infection-date <DATUM> \\",
            f"  --syndrome {slug_args}",
            "```",
            "",
        ]

    lines.append("### Geografisches Detail\n")
    lines += detail_lines

    return "\n".join(lines)


# ── LLM-Integration ───────────────────────────────────────────────────────────

def _run_llm(report: str, infection_date: str | None = None,
             max_tokens: int = 4000) -> str:
    try:
        from modules.llm import call_llm
        today = datetime.now().strftime("%Y-%m-%d")
        # Prüft den tatsächlichen Berichtsinhalt (manuelle + automatisch erkannte
        # Dauerrisiken), nicht nur die manuelle Config-Datei — sonst würde z.B.
        # eine automatisch erkannte Flughafennähe die Gewichtungsregel nicht auslösen.
        risk_weighting = _RISK_WEIGHTING_INSTRUCTION if "Persönliche Dauerrisiko-Expositionen" in report else ""
        if infection_date:
            prompt = SYSTEM_PROMPT_ACUTE.format(
                today=today, infection_date=infection_date, risk_weighting=risk_weighting)
        else:
            prompt = SYSTEM_PROMPT_EPIDEMIOLOGICAL.format(
                today=today, risk_weighting=risk_weighting)
        print(t("\nLLM analysiert ...", "\nLLM analysing ..."))
        return call_llm(report, system=prompt, max_tokens=max_tokens)
    except Exception as e:
        print(t(f"LLM nicht verfügbar: {e}", f"LLM not available: {e}"))
        return ""


_RISK_WEIGHTING_INSTRUCTION = """
**Gewichtungsregel für Dauerrisiko-Expositionen:**
Der Bericht enthält einen Abschnitt "Persönliche Dauerrisiko-Expositionen" mit
chronischen, kumulativen Expositionen (Tierhaltung, Berufsexposition, Wohnort
in Endemiegebiet). Diese Einträge verschieben die Vortest-Wahrscheinlichkeit
eines Erregers deutlich über den Populationsdurchschnitt hinaus.

Regel: Wenn ein Syndrom-Slug sowohl in den Reiseexpositions- oder
Vorinfektionsdaten ALS AUCH in den Dauerrisiko-Expositionen erscheint
(Abschnitt "Erhöhte Priorität"), dann ist dieses Syndrom **mindestens eine
Prioritätsstufe höher** zu bewerten als bei reiner Populationswahrscheinlichkeit.
Benenne diesen Effekt explizit in der Analyse.
"""

# Import der Template-Prompts
from modules.prompts.analysis_infectious import (
    SYSTEM_PROMPT_ANALYSE_OUTBREAK_EXPOSURE_EPIDEMIOLOGICAL_STR as SYSTEM_PROMPT_EPIDEMIOLOGICAL,
    SYSTEM_PROMPT_ANALYSE_OUTBREAK_EXPOSURE_ACUTE_STR as SYSTEM_PROMPT_ACUTE
)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(
        description="Reiseverlauf × Ausbruchsdaten — Expositionsanalyse")
    ap.add_argument("--from", dest="dfrom", default=_cfg.birthdate or "1900-01-01",
                    help="Ältestes Reisedatum (Standard: Geburtsdatum — dies ist eine "
                         "Lebenszeit-Expositionsanalyse; clinical.data_start ist NICHT "
                         "geeignet, da es die Baseline-Periode fuer Wearable-Daten meint, "
                         "keine strukturellen Endemie-/Wohnsitz-Risiken)")
    ap.add_argument("--update-db", action="store_true",
                    help="Ausbruchsdaten zuerst aktualisieren")
    ap.add_argument("--infection-date", dest="infection_date", default=None,
                    help="Infektionsdatum YYYY-MM-DD — aktiviert Akut-Framing im LLM-Prompt")
    ap.add_argument("--no-llm", action="store_true")
    ap.add_argument("--person", default=OWN_PERSON_ID,
                    help=t("Person (Standard: selbst)", "Person (default: self)"))
    ap.add_argument("--max-tokens", dest="max_tokens", type=int, default=4000,
                    help="Maximale Token-Anzahl für LLM-Output (Standard: 4000)")
    ap.add_argument("--plot", action="store_true")
    add_lang_arg(ap)
    args, _ = ap.parse_known_args()
    apply_lang_from_args(args)

    conn = open_db()

    if args.update_db:
        print("Ausbruchsdaten aktualisieren...")
        sys.path.insert(0, str(Path(__file__).parent.parent.parent / "importers"))
        from import_outbreak_data import run as fetch_outbreaks
        fetch_outbreaks(conn=conn)

    # Prüfen ob Ausbruchsdaten vorhanden
    # KEIN früher return bei 0 Einträgen: die strukturelle Flughafennähe-
    # Prüfung (build_report()) ist unabhängig von outbreak_events und soll
    # auch dann laufen, wenn noch nie ein Ausbruch importiert wurde.
    n_outbreaks = conn.execute(
        "SELECT COUNT(*) FROM outbreak_events").fetchone()[0]
    if n_outbreaks == 0:
        print("Keine Ausbruchsdaten in DB — Reise-/Ausbruchs-Treffer werden "
              "übersprungen, strukturelle Standortrisiken (z.B. Flughafennähe) "
              "laufen trotzdem.")
        print("Tipp: python3 importers/import_outbreak_data.py")
    else:
        print(f"Ausbruchs-DB: {n_outbreaks} Einträge")

    # Travel history + Wohnsitze prüfen
    travel = _cfg.travel_history
    n_gps  = conn.execute(
        "SELECT COUNT(*) FROM location_stays WHERE is_home=0").fetchone()[0]
    n_home = conn.execute(
        "SELECT COUNT(*) FROM location_stays WHERE is_home=1").fetchone()[0]
    print(f"Reisen: {len(travel)} (travel_history) + {n_gps} GPS-Aufenthalte "
          f"+ {n_home} Wohnsitz(e)")

    if not travel and n_gps == 0 and n_home == 0:
        print("Keine Reise-/Wohnsitzdaten. Tipp:")
        print("  python3 manage_travel_history.py add")
        print("  python3 utils/geocode_stays.py   (für GPS-Aufenthalte + Wohnsitz)")
        conn.close()
        return

    print("Expositionsanalyse läuft...")
    exposures = compute_exposures(conn, dfrom=args.dfrom)
    report   = build_report(exposures, conn=conn)
    print("\n" + report)

    llm_text = "" if args.no_llm else _run_llm(report, args.infection_date, args.max_tokens)

    # Speichern
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    from datetime import datetime as _dt
    ts  = _dt.now().strftime("%Y%m%d_%H%M")
    out = OUT_DIR / f"outbreak_exposure_{ts}.md"
    content = f"# Expositionsanalyse: Reise × Ausbrüche\n\n{report}\n"
    if llm_text:
        content += f"\n## Klinische Einschätzung\n\n{llm_text}\n"
    out.write_text(content, encoding="utf-8")
    print(f"Bericht: {out}")

    conn.close()


if __name__ == "__main__":
    main()
