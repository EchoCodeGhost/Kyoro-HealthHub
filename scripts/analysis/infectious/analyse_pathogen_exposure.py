#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Lifetime-Pathogen-Expositionsanalyse

Ermittelt, mit welchen Erregern man im Laufe des Lebens in Kontakt
gekommen sein könnte — basierend auf allen verfügbaren Aufenthalts-
und GPS-Daten.

Datenquellen (automatisch erkannt, alle optional):
  travel_history.json       Manuelle Reiseeinträge (~/.config/travel_history.json)
  location_stays (DB)       GPS-Cluster aus Home Assistant / iPhone (Reisen UND Wohnsitz,
                            is_home=0/1 — sonst würde ein lokal übertragener Ausbruch am
                            eigenen Wohnort, z.B. "Flughafenmalaria" ohne eigene Reise,
                            nie erfasst)
  Google Takeout            Semantic Location History (YYYY_MONTH.json)
                            oder Records.json (alt: timestampMs, neu: semanticSegments)
  GPX-Dateien               Polar Flow, Garmin Connect, Apple Watch Workout-Routen
  Apple Health Export       workout-routes/*.gpx aus dem Export-Ordner
  session_tracks (DB)       Garmin/Polar Trainings-GPS aus der DB

Kreuzt mit:
  outbreak_events (DB)      Aktive Ausbrüche (WHO, ECDC, RKI, LGL, CDC, ProMED) mit zeitlichem Überlapp
  endemic_ref (DB)          Endemische Erkrankungen nach Region
  Klimazonen-Risikomodell   Erreger nach Klimazone, Saison, Habitat
  FSME-Risikogebiete (DB)   LGL Bayern / RKI-Daten für Tick-TBE

Ausgabe:
  Aufenthaltszeitlinie, Erreger-Rangliste (lifetime score),
  empfohlene Serologie für Arzt-Gespräch

Konfiguration (optional in ~/.config/kyoro/health_config.json):
  paths.google_timeline     Pfad zum Takeout-Ordner oder Records.json
  paths.gpx_analysis_dir    Verzeichnis mit GPX-Dateien

@tier        heuristic
@refs        Brownstein JS, Freifeld CC, Reis BY, Mandl KD (2008). Surveillance Sans Frontières: Internet-based emerging infectious disease intelligence and the HealthMap project. PLoS Medicine, 5(7), e151. doi:10.1371/journal.pmed.0050151
             Aarestrup FM, Brown EW, Detter C, et al. (2012). Integrating genome-based informatics to modernize global disease monitoring, information sharing, and response. Emerging Infectious Diseases, 18(11), e1. doi:10.3201/eid1811.120453
@relevance.de Unterstützt die infektionsbezogene Datenanalyse und Entscheidungsfindung durch systematische Aufbereitung von Wearable- und Symptomdaten
@relevance.en Supports infection-related data analysis and decision-making through systematic processing of wearable and symptom data
@purpose.de  Ermittelt Lifetime-Pathogen-Expositionsrisiken aus Reiseverlauf, GPS-Clustern und GPX-Routen durch Abgleich mit Ausbruchs- und Endemie-Daten sowie Klimazonen-Risikomodellen.
@purpose.en  Estimates lifetime pathogen exposure risks from travel history, GPS clusters and GPX routes by matching against outbreak and endemic patterns data and climate zone risk models.
@method.de   Geo-Matching (ISO-Land, Koordinaten-Radius, Region-Text) kombiniert mit zeitlichem Überlapp-Score; Aggregation über alle verfügbaren Aufenthaltsquellen (JSON, DB, Google Takeout, GPX).
@method.en   Geo-matching (ISO country, coordinate radius, region text) combined with temporal overlap score; aggregation over all available stay sources (JSON, DB, Google Takeout, GPX).
@scoring     Expositions-Score je Pathogen (heuristisch, projektintern):
               Schweregewichte: {"hoch": 1.0, "mittel": 0.6, "niedrig": 0.25}
               Aufenthaltsdauer-Faktor: dur = min(days, 30) / 30
               Komponent-Score: w × (0.3 + 0.7 × dur)
               Lifetime-Score: Summe aller Komponent-Scores je Pathogen
               Basis: projektintern, keine epidemiologische Validierung.
@limits.de   Heuristische Methode: Heuristisches Geo- und Zeitfenster-Matching ohne epidemiologische Validierung; Schweregewichte (1.0/0.6/0.25) und Score-Formel projektintern; Ausbruchsdaten müssen manuell gepflegt werden; Klimazonen-Risikomodell vereinfacht (Gradbreitenklassen); Ergebnisse nur zur Hypothesengeneration für Arztgespräch (kein Serologieersatz).
@limits.en   Heuristic method: Heuristic geo and time-window matching without epidemiological validation; severity weights (1.0/0.6/0.25) and score formula are project-internal; outbreak data requires manual maintenance; climate zone risk model is simplified (latitude classes); results only for hypothesis generation in medical consultation (no substitute for serology).
@reads       outbreak_events, endemic_ref, location_stays, session_tracks
@writes      analyses/infectious/pathogen_exposure_*.{md,txt}

Usage:
  python3 analyse_pathogen_exposure.py
  python3 analyse_pathogen_exposure.py --from 2015-01-01
  python3 analyse_pathogen_exposure.py --sources travel gpx db
  python3 analyse_pathogen_exposure.py --no-llm --out /tmp/exposure.txt

@usage
    python analyse_pathogen_exposure.py
    python analyse_pathogen_exposure.py --help
    python analyse_pathogen_exposure.py --from 2024-01-01 --to 2024-12-31
"""
import argparse
import json
import math
import sqlite3
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from health_config import Config as _Cfg, OWN_PERSON_ID, KYORO_CONFIG_DIR
from modules.db import open_db, DB_OPERATIONAL_ERRORS
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from modules.endemic_matching import (
    geo_dist_km as _geo_dist_km, resolve_radius_km, since_floor_ok as _endemic_since_floor_ok,
    TIMELESS_SOURCES,
)
from modules.prompts.analysis_infectious import (
    SYSTEM_PROMPT_ANALYSE_PATHOGEN_EXPOSURE_DE as SYSTEM_PROMPT_DE,
    SYSTEM_PROMPT_ANALYSE_PATHOGEN_EXPOSURE_EN as SYSTEM_PROMPT_EN,
)


def _run_llm(report: str) -> str:
    try:
        from modules.llm import call_llm
        print(t("\nLLM analysiert ...", "\nLLM analysing ..."))
        return call_llm(report, system=t(SYSTEM_PROMPT_DE, SYSTEM_PROMPT_EN), max_tokens=800)
    except Exception as e:
        print(t(f"LLM nicht verfügbar: {e}", f"LLM not available: {e}"))
        return ""

_cfg = _Cfg()
OUT_DIR = _cfg.analyses_dir / "infectious"
TRAVEL_FILE = KYORO_CONFIG_DIR / "travel_history.json"
GEOCACHE_FILE = Path.home() / ".cache" / "kyoro_geocode.json"

# Zeitfenster für Ausbruchs-Matching (analog analyse_outbreak_exposure.py)
DAYS_BEFORE = 60
DAYS_AFTER  = 30
HOME_RADIUS = 0.5   # Grad (~50 km) — innerhalb = kein Auswärts-Aufenthalt


# ── Aufenthalt-Datenstruktur ──────────────────────────────────────────────────

@dataclass
class Stay:
    date_from:    str               # ISO-Datum
    date_to:      str               # ISO-Datum
    lat:          float | None = None
    lon:          float | None = None
    country:      str | None = None
    country_iso:  str | None = None
    subregion:    str | None = None
    city:         str | None = None
    climate_zone: str | None = None
    source:       str = "unknown"
    notes:        str | None = None
    duration_d:   int = 0

    def __post_init__(self):
        if not self.duration_d and self.date_from and self.date_to:
            try:
                d0 = datetime.strptime(self.date_from, "%Y-%m-%d")
                d1 = datetime.strptime(self.date_to,   "%Y-%m-%d")
                self.duration_d = max(1, (d1 - d0).days + 1)
            except ValueError:
                self.duration_d = 1

    @property
    def label(self) -> str:
        parts = [self.city or self.subregion or self.country or "Unbekannt"]
        if self.country_iso and self.country_iso not in (parts[0] or ""):
            parts.append(f"({self.country_iso})")
        return " ".join(parts)

    @property
    def month(self) -> int:
        try:
            return datetime.strptime(self.date_from, "%Y-%m-%d").month
        except ValueError:
            return 6


# ── Klimazonen-Risikomodell ───────────────────────────────────────────────────
# (Erreger, Risiko-Level, Notiz)

RISK_BY_CLIMATE: dict[str, list[tuple[str, str, str]]] = {
    "tropisch": [
        ("Malaria (P. falciparum/vivax)", "hoch",   "Anopheles-Mücken, ganzjährig"),
        ("Dengue",                         "hoch",   "Aedes aegypti/albopictus, ganzjährig"),
        ("Chikungunya",                    "hoch",   "Aedes, ganzjährig"),
        ("Hepatitis A",                    "mittel", "Kontaminiertes Wasser/Essen"),
        ("Typhus (Salmonella typhi)",       "mittel", "Hygiene, Wasser"),
        ("Cholera",                         "niedrig","Ausbruchs-abhängig"),
        ("Zika",                            "mittel", "Aedes, bes. 2015–2017"),
        ("Schistosomiasis",                 "mittel", "Süßwasserkontakt (sub-Saharan/SE-Asien)"),
        ("Leptospirose",                    "mittel", "Überschwemmungen, Süßwasser"),
        ("Yellow Fever",                    "niedrig","Vakzin-Pflicht oft, West-Afrika/Amazonas"),
    ],
    "subtropisch": [
        ("Dengue",                          "mittel", "Aedes, warme Monate"),
        ("Chikungunya",                     "mittel", "Aedes"),
        ("Hepatitis A",                     "mittel", "Wasser/Essen"),
        ("Leishmania (visceral/kutan)",     "mittel", "Sandmücken, dämmerungsaktiv"),
        ("Rickettsia (Spotted Fever Group)","mittel", "Zecken, warme Jahreszeit"),
        ("Brucellosis",                     "niedrig","Unpasteurisierte Milchprodukte"),
        ("Q-Fieber (Coxiella burnetii)",    "niedrig","Tier-Kontakt, Aerosolübertragung"),
        ("Leptospirose",                    "niedrig","Wasser/Boden-Kontakt"),
    ],
    "mediterran": [
        ("West-Nil-Virus",                  "niedrig","Culex-Mücken, Sommer"),
        ("Rickettsia (R. conorii)",         "mittel", "Zecken, Frühjahr-Sommer"),
        ("Leishmania (kutan/visceral)",     "mittel", "Sandmücken, Mittelmeerküste"),
        ("Brucellosis",                     "niedrig","Schaf-/Ziegenmilchkäse"),
        ("Hantavirus",                      "niedrig","Nagetier-Kontakt"),
        ("Hepatitis A",                     "niedrig","Unsauber verarbeitete Meeresfrüchte"),
        ("Krim-Kongo-HF",                   "niedrig","Zecken, Balkan/Türkei/Nordafrika"),
        ("Leptospirose",                    "niedrig","Süßwasser-Aktivitäten"),
    ],
    "kontinental": [
        ("Borreliose (Lyme)",               "mittel", "Ixodes-Zecken, Frühjahr-Herbst"),
        ("FSME",                            "mittel", "Ixodes ricinus, Risikogebiete"),
        ("Hantavirus (Puumala)",            "niedrig","Rötelmaus-Kontakt, Wald/Felder"),
        ("Q-Fieber",                        "niedrig","Schafe/Rinder, Aerosolübertragung"),
        ("Tularämie",                       "niedrig","Hasen/Nagetiere, Jagd"),
        ("Ornithose/Psittakose",            "niedrig","Vogelkontakt, Taubenmärkte"),
        ("Yersiniose",                      "niedrig","Schweinefleisch roh/nicht durchgegart"),
    ],
    "osteuropaeisch": [
        ("FSME (Siberian/Far-Eastern Subtyp)","mittel","Zecken, Wald"),
        ("Borreliose",                      "mittel", "Ixodes-Zecken"),
        ("Hantavirus (Dobrava)",            "niedrig","Brandmaus, Acker-/Waldnähe"),
        ("Tularämie",                       "niedrig","Nagetiere, Wasserquellen"),
        ("Rickettsia (R. sibirica)",        "niedrig","Zecken, Asien-Grenzbereich"),
    ],
    "skandinavisch": [
        ("Borreliose",                      "mittel", "Ixodes ricinus, Küstenbereiche"),
        ("FSME",                            "niedrig","Risikogebiete Schweden/Finnland"),
        ("Hantavirus (Puumala)",            "niedrig","Rötelmaus, Jahresschwankungen"),
    ],
    "nordafrikanisch": [
        ("Rickettsia (R. conorii)",         "mittel", "Zecken"),
        ("Leishmania",                      "mittel", "Sandmücken"),
        ("Brucellosis",                     "niedrig","Milchprodukte"),
        ("Hepatitis A",                     "mittel", "Wasser/Essen"),
        ("Typhus",                          "niedrig","Hygiene-abhängig"),
        ("Schistosomiasis",                 "niedrig","Nil/Oasen-Süßwasser"),
    ],
    "nahöstlich": [
        ("Brucellosis",                     "mittel", "Ziegen-/Kamelmilch, Schafe"),
        ("Leishmania",                      "mittel", "Sandmücken"),
        ("Rickettsia",                      "mittel", "Zecken"),
        ("MERS-CoV",                        "niedrig","Kamelkontakt, Arabische Halbinsel"),
        ("Krim-Kongo-HF",                   "niedrig","Zecken, ländlich"),
        ("Hepatitis A/E",                   "mittel", "Wasser/Essen"),
    ],
    "suedostasiatisch": [
        ("Dengue",                          "hoch",   "Aedes, ganzjährig"),
        ("Malaria (P. vivax/falciparum)",   "mittel", "Ländlich, Wald-Regionen"),
        ("Hepatitis A/E",                   "mittel", "Wasser/Essen"),
        ("Typhus",                          "mittel", "Hygiene"),
        ("Japanische Enzephalitis",         "niedrig","Culex, Reisfelder, Sommer"),
        ("Melioidose (Burkholderia pseu.)", "niedrig","Boden/Wasser, Thailand/Laos/Vietnam"),
        ("Scrub-Typhus",                    "niedrig","Trombiculid-Milben, Gras/Busch"),
        ("Strongyloides",                   "niedrig","Bodenkontakt (barfuss)"),
    ],
    "afrikanisch": [
        ("Malaria (P. falciparum)",         "hoch",   "Anopheles, ganzjährig, lebensgefährlich"),
        ("Typhus",                          "mittel", "Hygiene"),
        ("Schistosomiasis",                 "mittel", "Süßwasserkontakt"),
        ("Hepatitis A/E",                   "mittel", "Wasser/Essen"),
        ("Tuberculose",                     "mittel", "Aerogen, hohe Inzidenz"),
        ("Meningokokken (A/W135)",          "mittel", "Meningitis-Gürtel, Saison"),
        ("Dengue",                          "mittel", "Aedes, subsahar. Ausbrüche"),
        ("Rickettsia africae",              "mittel", "Zecken, Savanne, Safaris"),
        ("Rabies",                          "niedrig","Hunde/Fledermäuse, Bissverletzung"),
        ("Viral Hämorrhagische Fieber",     "niedrig","Regionen-spezifisch (Ebola-Gürtel)"),
        ("Afrikan. Trypanosomiasis",        "niedrig","Tsetsefliege, Nationalparks"),
    ],
    "lateinamerikanisch": [
        ("Dengue",                          "hoch",   "Aedes, ganzjährig"),
        ("Zika",                            "mittel", "Aedes, 2015–2018 Epidemie"),
        ("Chikungunya",                     "mittel", "Aedes"),
        ("Chagas (T. cruzi)",               "niedrig","Raubwanzen, ländlich/Risikogebiete"),
        ("Leishmania (mukokutan/kutan)",    "niedrig","Sandmücken, Regenwald"),
        ("Hantavirus (Americas)",           "niedrig","Nagetiere, Trockenregionen"),
        ("Yellow Fever",                    "niedrig","Amazonas, ländlich"),
        ("Leptospirose",                    "niedrig","Überschwemmungen, Wasser"),
    ],
}

# Länder-spezifische Zusatzrisiken (ISO → [(Erreger, Level, Notiz)])
RISK_BY_COUNTRY: dict[str, list[tuple[str, str, str]]] = {
    "IN": [("Tuberculose", "mittel", "Hohe TB-Inzidenz"),
           ("Japanische Enzephalitis", "niedrig", "Ländlich, Regenzeit")],
    "BD": [("Cholera", "mittel", "Überschwemmungen"), ("Dengue", "hoch", "")],
    "PK": [("Polio", "niedrig", "Endemie-Rest"), ("Typhus", "mittel", "")],
    "RU": [("FSME", "mittel", "Sibirischer/Fernost-Subtyp"),
           ("Hantavirus", "niedrig", "Ausbrüche in Perm, Tatarstan")],
    "CN": [("Japanische Enzephalitis", "niedrig", "Reisfelder"),
           ("Hantavirus", "niedrig", "Hemorrhagisches Fieber mit Nierensyndrom")],
    "AU": [("Ross River Fever", "niedrig", "Alphavirus, Mücken"),
           ("Q-Fieber", "niedrig", "Schafe/Rinder")],
    "US": [("Histoplasma capsulatum", "niedrig", "Ohio-/Mississippi-Tal, Fledermäuse"),
           ("Coccidioides", "niedrig", "Südwesten USA, Boden"),
           ("Rocky Mountain Spotted Fever", "mittel", "Zecken, Ost-/Süd-USA")],
    "MX": [("Coccidioides", "niedrig", "Nordbaja, trocken"),
           ("Chagas", "niedrig", "Ländlich")],
    "BR": [("Yellow Fever", "niedrig", "Amazonas-Region"),
           ("Tuberculose", "mittel", "Städte"),
           ("Leishmaniasis", "mittel", "Waldgebiete")],
    "ZA": [("Malaria", "niedrig", "Mpumalanga, Limpopo"),
           ("Tuberculose", "hoch",  "Hohe Inzidenz"),
           ("Rickettsia africae", "mittel", "Safari-Gebiete")],
    "DE": [("FSME", "mittel", "Risikogebiete Bayern/BaWü"),
           ("Borreliose", "mittel", "Deutschlandweit, Zecken")],
    "TR": [("Krim-Kongo-HF", "niedrig", "Zecken, Nordostanatolien"),
           ("Brucellosis", "niedrig", "Rohmilchprodukte")],
    "ES": [("Leishmania", "niedrig", "Hunde-Reservoir, Mittelmeer"),
           ("West-Nil-Virus", "niedrig", "Andalusien, Sommer")],
    "PT": [("West-Nil-Virus", "niedrig", "Alentejo/Algarve, Sommer"),
           ("Leishmania", "niedrig", "Hunde-Reservoir")],
    "GR": [("West-Nil-Virus", "niedrig", "Thessalien, Sommer"),
           ("Leishmania", "niedrig", "Inseln")],
}

# Serologie-Empfehlungen pro Erreger
SEROLOGY_MAP: dict[str, str] = {
    "Malaria":           "Blutausstrich + RDT (akut); bei Latenz: IIFT Plasmodium-IgG",
    "Dengue":            "Dengue NS1-Ag + IgM/IgG (akut); IgG-Seronarbe (nach Reise)",
    "Borreliose":        "Lyme-Stufentest: ELISA IgG/IgM → Blot",
    "FSME":              "FSME-IgG/IgM (ELISA); Impfstatus dokumentieren",
    "Hepatitis A":       "Anti-HAV IgG (Immunitäts-/Seronarben-Nachweis)",
    "Hepatitis E":       "HEV-IgG/IgM (häufig unterschätzt, bes. nach Asien-/Afrika-Reise)",
    "Leishmania":        "Leishmania-IgG (IIFT oder DAT); PCR Blut/KM wenn klinisch",
    "Rickettsia":        "Rickettsia-IgG/-IgM (Weil-Felix + ELISA); artspezifisch nach Region",
    "Brucellosis":       "Brucella-IgG/-IgM (ELISA + Rose Bengal Test)",
    "Schistosomiasis":   "Schistosoma-IgG (IIFT); Stuhluntersuchung (Eier)",
    "Q-Fieber":          "Coxiella burnetii Phase I+II IgG/IgM",
    "Leptospirose":      "Leptospira-IgG (MAT oder ELISA)",
    "Tularämie":         "Francisella-IgG (ELISA)",
    "Chikungunya":       "Chikungunya-IgG/-IgM (ELISA)",
    "West-Nil-Virus":    "WNV-IgG/-IgM (ELISA)",
    "Typhus":            "Salmonella typhi Widal-Test (veraltet) oder Vi-IgG",
    "Chagas":            "T. cruzi IgG (ELISA + IFT, mind. 2 Methoden)",
    "Strongyloides":     "Strongyloides-IgG; Stuhl-Untersuchung, Eosinophile",
    "Tuberculose":       "IGRA (QuantiFERON-TB Gold Plus) statt Tuberkulintest",
    "Hantavirus":        "Hantavirus-IgG/-IgM (ELISA) — Puumala/Dobrava spezifizieren",
    "Histoplasma":       "Histoplasma-Antigen (Urin/Serum); IgG-Komplement-Fixierung",
    "Coccidioides":      "Coccidioides-IgM/-IgG (Immunodiffusion + CF-Test)",
    "Japonische Enz.":   "JE-IgG/-IgM (ELISA, Plaque-Reduktion-Neutralisation)",
    "Ornithose":         "Chlamydia psittaci IgG (ELISA/MIF)",
    "Krim-Kongo-HF":     "CCHFV-IgG/-IgM (nur BSL-4-Labore; bei klinischem Verdacht)",
    "MERS-CoV":          "MERS-CoV-IgG (Neutralisationstest, Speziallabor)",
    "Rabies":            "Fluoreszenz-Antikörper-Nachweis (post exposure); IgG-Titer",
}


# ── Geo-Hilfsfunktionen ───────────────────────────────────────────────────────

def _geo_dist_deg(lat1, lon1, lat2, lon2) -> float:
    if None in (lat1, lon1, lat2, lon2):
        return float("inf")
    return math.sqrt((lat1 - lat2) ** 2 + (lon1 - lon2) ** 2)


# _geo_dist_km, resolve_radius_km, since_floor_ok, TIMELESS_SOURCES kommen aus
# modules.endemic_matching (s. Imports oben) statt hier dupliziert zu sein.
# _geo_dist_deg (oben) bleibt lokal -- wird fuer GPS-Cluster-Erkennung
# gebraucht, nicht Teil der Endemie-/FSME-Matching-Logik.


def _climate_zone(lat: float | None, lon: float | None,
                  iso: str = "") -> str | None:
    _SE = ("TH", "VN", "ID", "PH", "MY", "KH", "MM", "LA", "SG", "BN", "TL")
    _AF = ("KE", "TZ", "NG", "GH", "ET", "CD", "CM", "UG", "RW", "ZM", "ZW",
           "AO", "MZ", "MG", "CI", "SN", "ML", "BF", "NE", "TD")
    _NA = ("EG", "MA", "TN", "DZ", "LY")
    _ME = ("IL", "JO", "SA", "AE", "QA", "KW", "OM", "YE", "IQ", "IR", "LB",
           "SY", "PS")
    _LA = ("MX", "GT", "HN", "SV", "NI", "CR", "PA", "CO", "VE", "EC", "PE",
           "BO", "BR", "PY", "AR", "CL", "UY", "GY", "SR")
    if iso in _SE:
        return "suedostasiatisch"
    if iso in _AF:
        return "afrikanisch"
    if iso in _NA:
        return "nordafrikanisch"
    if iso in _ME:
        return "nahöstlich"
    if iso in _LA:
        return "lateinamerikanisch"
    if lat is None:
        return None
    if abs(lat) < 15:
        return "tropisch"
    if abs(lat) < 30:
        return "subtropisch"
    if 30 <= lat < 45 and (lon is None or lon > -15):
        return "mediterran"
    if lat >= 60:
        return "skandinavisch"
    if lat >= 45 and lon is not None and lon > 15:
        return "osteuropaeisch"
    return "kontinental"


# ── Nominatim-Geocoding mit lokalem Cache ─────────────────────────────────────

def _load_geocache() -> dict:
    if GEOCACHE_FILE.exists():
        try:
            return json.loads(GEOCACHE_FILE.read_text("utf-8"))
        except Exception:
            pass
    return {}


def _save_geocache(cache: dict) -> None:
    GEOCACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    GEOCACHE_FILE.write_text(json.dumps(cache, ensure_ascii=False, indent=2),
                             encoding="utf-8")


def _nominatim(lat: float, lon: float, cache: dict) -> dict:
    key = f"{round(lat,2)},{round(lon,2)}"
    if key in cache:
        return cache[key]
    params = urllib.parse.urlencode(
        {"lat": lat, "lon": lon, "format": "json", "addressdetails": 1, "zoom": 8}
    )
    req = urllib.request.Request(
        f"https://nominatim.openstreetmap.org/reverse?{params}",
        headers={"User-Agent": "Kyoro-HealthHub/1.0 (health-pipeline)"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read().decode("utf-8"))
        result = {
            "country":     data.get("address", {}).get("country", ""),
            "country_iso": data.get("address", {}).get("country_code", "").upper(),
            "state":       data.get("address", {}).get("state", ""),
            "city":        (data.get("address", {}).get("city")
                            or data.get("address", {}).get("town")
                            or data.get("address", {}).get("village", "")),
        }
        cache[key] = result
        time.sleep(1.1)   # Nominatim Rate-Limit
        return result
    except Exception:
        return {}


def _enrich_stay(stay: Stay, cache: dict) -> Stay:
    """Ergänzt Klimazone und ggf. Geocoding für Stays ohne Länderdaten."""
    if not stay.climate_zone and stay.country_iso:
        stay.climate_zone = _climate_zone(stay.lat, stay.lon, stay.country_iso)
    if stay.lat and not stay.country_iso:
        geo = _nominatim(stay.lat, stay.lon, cache)
        if geo:
            stay.country     = stay.country     or geo.get("country", "")
            stay.country_iso = stay.country_iso or geo.get("country_iso", "")
            stay.city        = stay.city        or geo.get("city", "")
            stay.climate_zone = _climate_zone(stay.lat, stay.lon,
                                              stay.country_iso or "")
    return stay


# ── GPS-Datenquellen ──────────────────────────────────────────────────────────

import csv as _csv
import zipfile as _zipfile


def _iso_date(ts: str | None) -> str | None:
    """Verschiedene Timestamp-Formate → YYYY-MM-DD."""
    if not ts:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%S%z",
                "%Y-%m-%dT%H:%M:%S.%fZ",  "%Y-%m-%dT%H:%M:%SZ",
                "%Y-%m-%d"):
        try:
            return datetime.strptime(ts[:26], fmt[:len(ts)]).strftime("%Y-%m-%d")
        except ValueError:
            pass
    if ts.isdigit() and len(ts) == 13:   # timestampMs
        return datetime.fromtimestamp(int(ts) / 1000,
                                      tz=timezone.utc).strftime("%Y-%m-%d")
    return ts[:10] if len(ts) >= 10 else None


def _load_travel_history(dfrom: str = "1990-01-01") -> list[Stay]:
    """Lädt manuelle Reiseeinträge aus travel_history.json."""
    if not TRAVEL_FILE.exists():
        return []
    try:
        entries = json.loads(TRAVEL_FILE.read_text("utf-8"))
    except Exception:
        return []
    stays = []
    for e in entries:
        d0 = e.get("date_from", "")[:10]
        d1 = e.get("date_to",   e.get("date_from", ""))[:10]
        if d0 < dfrom:
            continue
        stays.append(Stay(
            date_from    = d0,
            date_to      = d1,
            country      = e.get("country"),
            country_iso  = e.get("country_iso"),
            subregion    = e.get("subregion"),
            climate_zone = e.get("climate_zone"),
            source       = "travel_history",
            notes        = e.get("notes"),
        ))
    return stays


def _load_oura_location(oura_dir: Path | None,
                         home_lat: float | None,
                         home_lon: float | None,
                         dfrom: str = "1990-01-01") -> list[Stay]:
    """Oura rawlocation.csv → geclusterte Aufenthalte.

    Oura loggt das Telefon-GPS mit ~1–2s Auflösung.
    Sucht rawlocation.csv in:
      <oura_dir>/App Data/rawlocation.csv   (extrahiertes ZIP)
      <oura_dir>/rawlocation.csv
      <oura_dir>/data.zip                   (komprimiertes Archiv)
      <oura_dir>/*.zip                      (beliebiger ZIP-Name)
    Samplet auf 5-Minuten-Buckets runter, dann gleiches Tag-Clustering
    wie Google Takeout Records.json.
    """
    if not oura_dir or not oura_dir.is_dir():
        return []

    # rawlocation.csv finden
    content: str | None = None
    candidates = [
        oura_dir / "App Data" / "rawlocation.csv",
        oura_dir / "rawlocation.csv",
        oura_dir / "data_csv" / "App Data" / "rawlocation.csv",
    ]
    for candidate in candidates:
        if candidate.exists():
            content = candidate.read_text("utf-8", errors="replace")
            break

    if content is None:
        # Suche in ZIP-Dateien
        for zip_path in sorted(oura_dir.glob("*.zip")):
            try:
                with _zipfile.ZipFile(zip_path) as zf:
                    for name in zf.namelist():
                        if name.lower().endswith("rawlocation.csv"):
                            content = zf.read(name).decode("utf-8", errors="replace")
                            break
            except Exception:
                pass
            if content is not None:
                break

    if content is None:
        return []

    # Parsen — Semikolon-getrennt
    reader = _csv.DictReader(content.splitlines(), delimiter=";")

    # Downsample: 1 Punkt pro 5-Minuten-Bucket (ts // 300)
    buckets: dict[str, tuple[str, float, float]] = {}
    for row in reader:
        ts_raw = row.get("timestamp", "")
        try:
            lat = float(row.get("latitude",  "nan"))
            lon = float(row.get("longitude", "nan"))
        except (ValueError, TypeError):
            continue
        if lat != lat or lon != lon:   # NaN-Check
            continue
        d = _iso_date(ts_raw)
        if not d or d < dfrom:
            continue
        # Bucket-Key: Datum + 5-Min-Intervall
        try:
            epoch = int(datetime.fromisoformat(
                ts_raw.replace("Z", "+00:00")).timestamp())
            bucket = f"{d}_{epoch // 300}"
        except (ValueError, OSError):
            bucket = ts_raw[:15]           # Fallback: Minute-Präzision
        if bucket not in buckets:
            buckets[bucket] = (d, lat, lon)

    if not buckets:
        return []

    # Gleicher Tag-Clustering wie _parse_google_records_json
    by_day: dict[str, list[tuple[float, float]]] = defaultdict(list)
    for d, lat, lon in buckets.values():
        by_day[d].append((lat, lon))

    stays: list[Stay] = []
    sorted_days = sorted(by_day.keys())
    if not sorted_days:
        return []

    cluster_start  = sorted_days[0]
    cluster_coords = list(by_day[sorted_days[0]])
    prev_day       = sorted_days[0]

    def _flush_oura(start: str, end: str,
                    coords: list[tuple[float, float]]) -> None:
        if not coords:
            return
        avg_lat = sum(c[0] for c in coords) / len(coords)
        avg_lon = sum(c[1] for c in coords) / len(coords)
        if (home_lat and home_lon
                and _geo_dist_deg(avg_lat, avg_lon,
                                  home_lat, home_lon) < HOME_RADIUS):
            return
        stays.append(Stay(
            date_from = start,
            date_to   = end,
            lat       = avg_lat,
            lon       = avg_lon,
            source    = "oura_gps",
        ))

    for day in sorted_days[1:]:
        day_coords = by_day[day]
        day_avg_lat = sum(c[0] for c in day_coords) / len(day_coords)
        day_avg_lon = sum(c[1] for c in day_coords) / len(day_coords)
        c_avg_lat = sum(c[0] for c in cluster_coords) / len(cluster_coords)
        c_avg_lon = sum(c[1] for c in cluster_coords) / len(cluster_coords)

        gap = (datetime.strptime(day, "%Y-%m-%d") -
               datetime.strptime(prev_day, "%Y-%m-%d")).days
        moved = _geo_dist_deg(day_avg_lat, day_avg_lon,
                              c_avg_lat, c_avg_lon) > HOME_RADIUS

        if gap > 3 or moved:
            _flush_oura(cluster_start, prev_day, cluster_coords)
            cluster_start  = day
            cluster_coords = list(day_coords)
        else:
            cluster_coords.extend(day_coords)
        prev_day = day

    _flush_oura(cluster_start, prev_day, cluster_coords)
    return stays


def _load_db_stays(conn: sqlite3.Connection, dfrom: str = "1990-01-01") -> list[Stay]:
    """Lädt nicht-Heim-Aufenthalte aus location_stays + location_stays_geocoded.

    Clustert nach (country_iso, subregion, Monat) und fasst zu min(start)–
    max(end) zusammen — location_stays kann denselben Aufenthalt als viele
    (nahezu) identische Zeilen enthalten (z.B. wiederholte Home-Assistant-
    Snapshots, dasselbe Muster wie bei den Wohnsitz-Duplikaten in
    _load_home_stays_db()). Ohne Clustering würde _aggregate_exposure() den
    Klimazonen-/Länder-Score pro Duplikat-Zeile erneut aufaddieren und so
    Reiseziele mit vielen aufgezeichneten GPS-Punkten künstlich hochgewichten.
    """
    try:
        rows = conn.execute("""
            SELECT ls.start_ts, ls.end_ts, ls.lat, ls.lon,
                   g.country, g.country_iso, g.subregion, g.city, g.climate_zone
            FROM   location_stays ls
            LEFT JOIN location_stays_geocoded g ON g.stay_id = ls.id
            WHERE  ls.is_home = 0 AND ls.start_ts >= ?
            ORDER  BY ls.start_ts
        """, (dfrom,)).fetchall()
    except DB_OPERATIONAL_ERRORS:
        return []
    clusters: dict[tuple, dict] = {}
    for r in rows:
        d0 = (r[0] or "")[:10]
        d1 = (r[1] or d0)[:10]
        if not d0:
            continue
        iso       = r[5] or ""
        subregion = r[6] or ""
        month     = d0[:7]  # YYYY-MM
        key = (iso, subregion, month)
        if key not in clusters:
            clusters[key] = {
                "date_from": d0, "date_to": d1, "lat": r[2], "lon": r[3],
                "country": r[4] or None, "country_iso": r[5] or None,
                "subregion": r[6] or None, "city": r[7] or None,
                "climate_zone": r[8] or None,
            }
        else:
            c = clusters[key]
            if d0 < c["date_from"]:
                c["date_from"] = d0
            if d1 > c["date_to"]:
                c["date_to"] = d1
    return [
        Stay(date_from=c["date_from"], date_to=c["date_to"], lat=c["lat"], lon=c["lon"],
             country=c["country"], country_iso=c["country_iso"], subregion=c["subregion"],
             city=c["city"], climate_zone=c["climate_zone"], source="location_stays_db")
        for c in clusters.values()
    ]


def _load_home_stays_db(conn: sqlite3.Connection, dfrom: str = "1990-01-01") -> list[Stay]:
    """Lädt Wohnsitze (is_home=1) aus location_stays + location_stays_geocoded.

    Analog zu _load_db_stays(), aber für den Wohnort statt Reisen — sonst
    würde ein lokal übertragener Ausbruch am eigenen Wohnort (z.B.
    "Flughafenmalaria" durch eingeschleppte Mücken, ohne eigene Reise) nie
    erfasst, weil eine positive Reiseanamnese in der Praxis oft der einzige
    Trigger ist, an sowas überhaupt zu denken. _temporal_overlap() prüft
    ohnehin nur Intervall-Überlapp (kein Verhältnis zur Aufenthaltsdauer),
    _aggregate_exposure() deckelt den Dauerfaktor bei 30 Tagen — beides
    funktioniert unverändert korrekt auch für mehrjährige Wohnsitze.
    Ohne Ende (noch aktueller Wohnsitz) wird end_ts auf "heute" gesetzt.

    Clustert nach gerundeter Koordinate (3 Nachkommastellen ≈ 111m) und fasst
    zu min(start)–max(end) zusammen — location_stays kann denselben Wohnort-
    Zeitraum als viele (nahezu) identische Zeilen enthalten (z.B. wiederholte
    Home-Assistant-Snapshots). Ohne Clustering würde _aggregate_exposure()
    den Score für die Heimatregion pro Duplikat-Zeile erneut aufaddieren und
    so massiv verzerren, statt den Wohnsitz einmalig zu werten.
    """
    try:
        rows = conn.execute("""
            SELECT ls.start_ts, ls.end_ts, ls.lat, ls.lon,
                   g.country, g.country_iso, g.subregion, g.city, g.climate_zone
            FROM   location_stays ls
            LEFT JOIN location_stays_geocoded g ON g.stay_id = ls.id
            WHERE  ls.is_home = 1 AND (ls.end_ts IS NULL OR ls.end_ts >= ?)
            ORDER  BY ls.start_ts
        """, (dfrom,)).fetchall()
    except DB_OPERATIONAL_ERRORS:
        return []
    today = datetime.now().strftime("%Y-%m-%d")
    clusters: dict[tuple, dict] = {}
    for r in rows:
        d0 = (r[0] or "")[:10]
        d1 = (r[1] or today)[:10]
        lat, lon = r[2], r[3]
        if not d0 or lat is None or lon is None:
            continue
        key = (round(float(lat), 3), round(float(lon), 3))
        if key not in clusters:
            clusters[key] = {
                "date_from": d0, "date_to": d1, "lat": lat, "lon": lon,
                "country": r[4] or None, "country_iso": r[5] or None,
                "subregion": r[6] or None, "city": r[7] or None,
                "climate_zone": r[8] or None,
            }
        else:
            c = clusters[key]
            if d0 < c["date_from"]:
                c["date_from"] = d0
            if d1 > c["date_to"]:
                c["date_to"] = d1
    stays = [
        Stay(date_from=c["date_from"], date_to=c["date_to"], lat=c["lat"], lon=c["lon"],
             country=c["country"], country_iso=c["country_iso"], subregion=c["subregion"],
             city=c["city"], climate_zone=c["climate_zone"], source="home_residence_db")
        for c in clusters.values()
    ]
    return stays


def _load_db_session_tracks(conn: sqlite3.Connection,
                             home_lat: float | None, home_lon: float | None,
                             dfrom: str = "1990-01-01") -> list[Stay]:
    """Garmin/Polar Workout-GPS aus session_tracks — nur Nicht-Heim-Aktivitäten."""
    try:
        rows = conn.execute("""
            SELECT s.ts_start, s.ts_end, AVG(t.lat), AVG(t.lon)
            FROM   session_tracks t
            JOIN   sessions s ON s.id = t.session_id
            WHERE  s.ts_start >= ?
            GROUP  BY s.id
            HAVING COUNT(*) >= 10
            ORDER  BY s.ts_start
        """, (dfrom,)).fetchall()
    except DB_OPERATIONAL_ERRORS:
        return []
    stays = []
    for r in rows:
        lat, lon = r[2], r[3]
        if lat is None:
            continue
        if (home_lat and home_lon
                and _geo_dist_deg(lat, lon, home_lat, home_lon) < HOME_RADIUS):
            continue
        d0 = (r[0] or "")[:10]
        d1 = (r[1] or d0)[:10]
        if not d0:
            continue
        stays.append(Stay(
            date_from = d0,
            date_to   = d1 or d0,
            lat       = lat,
            lon       = lon,
            source    = "session_tracks_db",
        ))
    return stays


def _parse_gpx_file(path: Path,
                    home_lat: float | None, home_lon: float | None) -> Stay | None:
    """GPX-Datei (Polar, Garmin, Apple Watch) → Stay oder None."""
    try:
        tree = ET.parse(path)
    except ET.ParseError:
        return None
    root = tree.getroot()
    # Namespace-flexibel
    ns_uri = root.tag.split("}")[0].lstrip("{") if "}" in root.tag else ""
    ns_pfx = f"{{{ns_uri}}}" if ns_uri else ""

    points: list[tuple[str, float, float]] = []
    for trkpt in root.iter(f"{ns_pfx}trkpt"):
        lat = trkpt.get("lat")
        lon = trkpt.get("lon")
        time_el = trkpt.find(f"{ns_pfx}time")
        ts = time_el.text if time_el is not None else None
        if lat and lon:
            points.append((ts or "", float(lat), float(lon)))

    if not points:
        return None

    lats = [p[1] for p in points]
    lons = [p[2] for p in points]
    avg_lat = sum(lats) / len(lats)
    avg_lon = sum(lons) / len(lons)

    if (home_lat and home_lon
            and _geo_dist_deg(avg_lat, avg_lon, home_lat, home_lon) < HOME_RADIUS):
        return None

    timestamps = [p[0] for p in points if p[0]]
    d0 = _iso_date(min(timestamps)) if timestamps else None
    d1 = _iso_date(max(timestamps)) if timestamps else None
    if not d0:
        d0 = path.stem[:10] if len(path.stem) >= 10 else str(path.stat().st_mtime)[:10]
    if not d1:
        d1 = d0

    return Stay(
        date_from = d0,
        date_to   = d1,
        lat       = avg_lat,
        lon       = avg_lon,
        source    = f"gpx:{path.name}",
    )


def _load_gpx_directory(directory: Path | None,
                         home_lat: float | None,
                         home_lon: float | None,
                         dfrom: str = "1990-01-01") -> list[Stay]:
    """Alle GPX-Dateien aus einem Verzeichnis laden."""
    if not directory or not directory.is_dir():
        return []
    stays = []
    for gpx_file in sorted(directory.rglob("*.gpx")):
        stay = _parse_gpx_file(gpx_file, home_lat, home_lon)
        if stay and stay.date_from >= dfrom:
            stays.append(stay)
    return stays


def _load_apple_health_routes(export_dir: Path | None,
                               home_lat: float | None,
                               home_lon: float | None,
                               dfrom: str = "1990-01-01") -> list[Stay]:
    """Apple Health Export: workout-routes/*.gpx → Stays."""
    if not export_dir or not export_dir.is_dir():
        return []
    routes_dir = export_dir / "workout-routes"
    if not routes_dir.is_dir():
        routes_dir = export_dir  # manchmal direkt im Root
    return _load_gpx_directory(routes_dir, home_lat, home_lon, dfrom)


def _load_google_takeout(path: Path | None, dfrom: str = "1990-01-01") -> list[Stay]:
    """Google Takeout Location History (mehrere Formate) → Stays."""
    if not path or not path.exists():
        return []

    stays: list[Stay] = []

    # Semantic Location History: YYYY/YYYY_MONTH.json (bestes Format)
    semantic_dir = (path if path.is_dir() else path.parent) / "Semantic Location History"
    if not semantic_dir.is_dir():
        semantic_dir = path if path.is_dir() else None

    if semantic_dir and semantic_dir.is_dir():
        for json_file in sorted(semantic_dir.rglob("*.json")):
            stays.extend(_parse_google_semantic_json(json_file, dfrom))

    # Falls keine Semantic-Dateien: Records.json versuchen
    if not stays:
        records = path if path.is_file() else None
        if not records:
            for candidate in [path / "Records.json",
                              path / "Location History" / "Records.json"]:
                if candidate.exists():
                    records = candidate
                    break
        if records:
            stays.extend(_parse_google_records_json(records, dfrom))

    return stays


def _parse_google_semantic_json(path: Path, dfrom: str) -> list[Stay]:
    """Parst YYYY_MONTH.json (timelineObjects oder semanticSegments)."""
    try:
        data = json.loads(path.read_text("utf-8", errors="replace"))
    except Exception:
        return []

    stays: list[Stay] = []

    # Altes Format: timelineObjects[].placeVisit
    for obj in data.get("timelineObjects", []):
        pv = obj.get("placeVisit", {})
        if not pv:
            continue
        loc  = pv.get("location", {})
        dur  = pv.get("duration", {})
        d0   = _iso_date(dur.get("startTimestamp"))
        d1   = _iso_date(dur.get("endTimestamp")) or d0
        if not d0 or d0 < dfrom:
            continue
        lat_e7 = loc.get("latitudeE7")
        lon_e7 = loc.get("longitudeE7")
        lat = lat_e7 / 1e7 if lat_e7 else None
        lon = lon_e7 / 1e7 if lon_e7 else None
        addr   = loc.get("address", "")
        name   = loc.get("name", "")
        stays.append(Stay(
            date_from = d0, date_to = d1,
            lat = lat, lon = lon,
            notes = name or addr or None,
            source = "google_takeout_semantic",
        ))

    # Neueres Format (2024+): semanticSegments[].visit
    for seg in data.get("semanticSegments", []):
        visit = seg.get("visit", {})
        if not visit:
            continue
        d0  = _iso_date(seg.get("startTime"))
        d1  = _iso_date(seg.get("endTime")) or d0
        if not d0 or d0 < dfrom:
            continue
        # Koordinaten aus timelinePath
        path_pts = seg.get("timelinePath", [])
        lat, lon = None, None
        if path_pts:
            try:
                pt = path_pts[len(path_pts) // 2].get("point", "")
                # Format: "47.9999° N, 11.1234° E"
                nums = [float(x.split("°")[0].strip())
                        for x in pt.split(",") if "°" in x]
                if len(nums) == 2:
                    lat, lon = nums[0], nums[1]
            except (ValueError, IndexError):
                pass
        stays.append(Stay(
            date_from = d0, date_to = d1,
            lat = lat, lon = lon,
            source = "google_takeout_semantic",
        ))

    return stays


def _parse_google_records_json(path: Path, dfrom: str) -> list[Stay]:
    """Parst Records.json (rohes GPS-Log) → geclusterte Stays."""
    try:
        data = json.loads(path.read_text("utf-8", errors="replace"))
    except Exception:
        return []

    points: list[tuple[str, float, float]] = []
    for loc in data.get("locations", []):
        ts  = loc.get("timestamp") or loc.get("timestampMs")
        lat_raw = loc.get("latitudeE7") or loc.get("lat")
        lon_raw = loc.get("longitudeE7") or loc.get("lon")
        if ts and lat_raw and lon_raw:
            d = _iso_date(str(ts))
            if d and d >= dfrom:
                lat = float(lat_raw) / 1e7 if abs(float(lat_raw)) > 90 else float(lat_raw)
                lon = float(lon_raw) / 1e7 if abs(float(lon_raw)) > 180 else float(lon_raw)
                points.append((d, lat, lon))

    if not points:
        return []

    # Einfaches Tages-Clustering: pro Tag einen Durchschnitts-Aufenthaltsort
    by_day: dict[str, list[tuple[float, float]]] = defaultdict(list)
    for d, lat, lon in points:
        by_day[d].append((lat, lon))

    # Zu Aufenthalten zusammenführen: aufeinanderfolgende Tage in derselben Region
    stays: list[Stay] = []
    sorted_days = sorted(by_day.keys())
    cluster_start = sorted_days[0]
    cluster_coords: list[tuple[float, float]] = list(by_day[sorted_days[0]])
    prev_day = sorted_days[0]

    def _flush(start, end, coords):
        if not coords:
            return
        avg_lat = sum(c[0] for c in coords) / len(coords)
        avg_lon = sum(c[1] for c in coords) / len(coords)
        stays.append(Stay(
            date_from = start, date_to = end,
            lat = avg_lat, lon = avg_lon,
            source = "google_takeout_records",
        ))

    for day in sorted_days[1:]:
        day_coords = by_day[day]
        day_avg_lat = sum(c[0] for c in day_coords) / len(day_coords)
        day_avg_lon = sum(c[1] for c in day_coords) / len(day_coords)
        cluster_avg_lat = sum(c[0] for c in cluster_coords) / len(cluster_coords)
        cluster_avg_lon = sum(c[1] for c in cluster_coords) / len(cluster_coords)

        gap_days = (datetime.strptime(day, "%Y-%m-%d") -
                    datetime.strptime(prev_day, "%Y-%m-%d")).days
        moved = _geo_dist_deg(day_avg_lat, day_avg_lon,
                              cluster_avg_lat, cluster_avg_lon) > HOME_RADIUS

        if gap_days > 3 or moved:
            _flush(cluster_start, prev_day, cluster_coords)
            cluster_start  = day
            cluster_coords = list(day_coords)
        else:
            cluster_coords.extend(day_coords)
        prev_day = day

    _flush(cluster_start, prev_day, cluster_coords)
    return stays


# ── Exposure-Analyse ──────────────────────────────────────────────────────────

def _load_outbreak_events(conn: sqlite3.Connection,
                           dfrom: str) -> list[dict]:
    try:
        rows = conn.execute("""
            SELECT source, disease, syndrome_slug, country, country_iso,
                   region, lat, lon, date_reported, date_start, date_end, severity
            FROM   outbreak_events
            WHERE  date_reported >= ? AND source NOT IN ('endemic_ref', 'lgl_fsme')
            ORDER  BY date_reported
        """, (dfrom,)).fetchall()
    except DB_OPERATIONAL_ERRORS:
        return []
    cols = ["source", "disease", "syndrome_slug", "country", "country_iso",
            "region", "lat", "lon", "date_reported", "date_start", "date_end", "severity"]
    return [dict(zip(cols, r)) for r in rows]


def _load_endemic_ref(conn: sqlite3.Connection) -> list[dict]:
    """Laedt zeitlose strukturelle Risiken: endemic_ref UND lgl_fsme.

    lgl_fsme (FSME-Risikokreise) gehoert hierher, nicht zu den datumsgebundenen
    Ausbruchs-Events (_load_outbreak_events) -- FSME-Risiko ist eine dauerhafte
    Eigenschaft eines Kreises, kein Einzelereignis. Mit dem event-artigen
    _temporal_overlap() haette ein Wohnsitz aus der Vergangenheit gegen den
    hartcodierten date_start="<aktuelles Jahr>-01-01" der FSME-Eintraege
    faelschlich als "kein Ueberlapp" gegolten (gefunden beim Testlauf gegen
    echte Wohnsitz-Historie).
    """
    try:
        rows = conn.execute("""
            SELECT source, disease, syndrome_slug, country, country_iso,
                   region, lat, lon, severity, radius_km, note, since_date
            FROM   outbreak_events
            WHERE  source IN ('endemic_ref', 'lgl_fsme')
        """).fetchall()
    except DB_OPERATIONAL_ERRORS:
        return []
    cols = ["source", "disease", "syndrome_slug", "country", "country_iso",
            "region", "lat", "lon", "severity", "radius_km", "note", "since_date"]
    return [dict(zip(cols, r)) for r in rows]


def _temporal_overlap(trip_from: str, trip_to: str,
                       outbreak_ref: str) -> bool:
    fmt = "%Y-%m-%d"
    try:
        t0 = datetime.strptime(trip_from, fmt)
        t1 = datetime.strptime(trip_to,   fmt)
        o0 = datetime.strptime(outbreak_ref[:10], fmt) - timedelta(days=DAYS_BEFORE)
        o1 = datetime.strptime(outbreak_ref[:10], fmt) + timedelta(days=365)
        return t0 <= o1 and t1 >= o0
    except (ValueError, TypeError):
        return False


# Radius-/Zeitlos-Logik (resolve_radius_km, since_floor_ok, TIMELESS_SOURCES)
# kommt aus modules.endemic_matching statt hier dupliziert zu sein.

def _region_match(stay: Stay, ev: dict) -> bool:
    """Prueft, ob ein Aufenthalt geografisch zu einem Ausbruchs-/Endemie-Eintrag passt.

    ISO-/Laendername-Uebereinstimmung allein ist NIE hinreichend, sobald beide
    Seiten Koordinaten haben — sie entscheidet nur, ob ein Koordinaten-Match
    ueberhaupt zulaessig ist (keine Laendergrenzen-uebergreifenden Treffer).
    Ohne diese Regel wuerde z.B. jeder Aufenthalt irgendwo in Deutschland
    gegen jeden deutschlandweit getaggten Endemie-Eintrag treffen, unabhaengig
    von der tatsaechlichen Entfernung (frueherer Bug: ISO-Match allein gab
    sofort True zurueck, der anschliessende Koordinaten-Fallback nutzte zudem
    eine reine Grad-Differenz statt einer echten km-Distanz).
    """
    s_iso = (stay.country_iso or "").upper()
    e_iso = (ev.get("country_iso") or "").upper()
    iso_match = bool(s_iso and e_iso and s_iso == e_iso)
    s_c = (stay.country or "").lower()
    e_c = (ev.get("country") or "").lower()
    country_match = bool(s_c and e_c and (s_c in e_c or e_c in s_c))

    if stay.lat and ev.get("lat"):
        if not (iso_match or country_match):
            return False  # unterschiedliche Laender -> kein Koordinaten-Match
        radius_km = resolve_radius_km(ev)
        return _geo_dist_km(stay.lat, stay.lon, ev["lat"], ev["lon"]) <= radius_km

    return iso_match or country_match


def _since_floor_ok(stay: Stay, ev: dict) -> bool:
    """Schliesst juengere, aktiv expandierende Endemie-Risiken (since_date
    gesetzt, z.B. Tigermuecken-Landkreise) fuer Aufenthalte aus, die komplett
    vor der dokumentierten Entstehung dieses Risikos endeten. Seit jeher
    endemische Risiken (since_date NULL, z.B. FSME/Malariazonen) sind davon
    unberuehrt."""
    try:
        stay_end_dt = datetime.strptime((stay.date_to or stay.date_from)[:10], "%Y-%m-%d")
    except (ValueError, TypeError):
        stay_end_dt = None
    return _endemic_since_floor_ok(ev.get("since_date"), stay_end_dt)


def analyse_stays(stays: list[Stay],
                  outbreaks: list[dict],
                  endemic: list[dict]) -> list[dict]:
    """Verknüpft jeden Aufenthalt mit passenden Ausbrüchen und endemischen Risiken."""
    results = []
    for stay in stays:
        matched_outbreaks = [
            ev for ev in outbreaks
            if _region_match(stay, ev)
            and _temporal_overlap(stay.date_from, stay.date_to,
                                  ev["date_reported"])
        ]
        matched_endemic = [
            ev for ev in endemic
            if _region_match(stay, ev) and _since_floor_ok(stay, ev)
        ]
        results.append({
            "stay":      stay,
            "outbreaks": matched_outbreaks,
            "endemic":   matched_endemic,
        })
    return results


# ── Lifetime-Aggregation ──────────────────────────────────────────────────────

_SEV_WEIGHT = {"hoch": 1.0, "high": 1.0,
               "mittel": 0.6, "medium": 0.6,
               "niedrig": 0.25, "low": 0.25}

import re as _re


_DISEASE_CANONICAL: dict[str, str] = {
    # CCHF — verschiedene Schreibweisen
    "krim-kongo-hf":                         "cchf",
    "krim-kongo-hämorrhagisches":            "cchf",
    "crimean-congo":                          "cchf",
    "krim kongo":                             "cchf",
    # West-Nil (Ziel = Slug der tatsächlichen Syndrom-Datei west_nile.json,
    # sonst fragmentiert die Lifetime-Aggregation Klimazonen- und
    # Ausbruchsdaten-Treffer für dieselbe Krankheit in zwei Keys)
    "west-nil-virus":                         "west_nile",
    "west nile":                              "west_nile",
    "wnv":                                    "west_nile",
    # Hepatitis A/E zusammenfassen
    "hepatitis a":                            "hepatitis_a",
    "hepatitis e":                            "hepatitis_e",
    "hepatitis a/e":                          "hepatitis_a",
    # Fleckfieber (alle Rickettsia-Stämme → gemeinsamer Serologie-Key)
    "rickettsia conorii":                     "rickettsia",
    "rickettsia (r. conorii)":               "rickettsia",
    "mittelmeerfleckfieber":                  "rickettsia",
    "spotted fever":                          "rickettsia",  # deckt auch "Rocky Mountain Spotted Fever" (Substring-Match)
    "rickettsia africae":                     "rickettsia",
    "rickettsia (spotted":                    "rickettsia",
    # Scrub-Typhus (Orientia tsutsugamushi, eigene Gattung, aber klinisch/
    # praktisch der Fleckfieber-Gruppe zugeordnet — kein eigener File nötig)
    "scrub-typhus":                            "rickettsia",
    "scrub typhus":                            "rickettsia",
    # Ross-River-Fieber — eigene Syndrom-Datei existiert bereits
    "ross river":                              "ross_river",
    # Weitere Sprach-/Schreibweisen-Fragmentierungen gefunden durch Testlauf
    # gegen RISK_BY_CLIMATE/RISK_BY_COUNTRY (2026-09-21): Substring-Check
    # "alias in d" schlägt fehl, wenn der Alias LÄNGER als der normalisierte
    # Krankheitsname ist (z.B. "leishmaniose" passt nicht in "leishmania") —
    # deshalb hier die tatsächlich in den Risiko-Modellen vorkommende
    # (kürzere/andere) Schreibweise als eigener Alias-Key.
    "brucellosis":                             "brucellose",
    "coccidioides":                            "coccidioidomykose",
    "histoplasma":                             "histoplasmose",
    "japanische enzephalitis":                 "japanische_enzephalitis",
    "leishmania":                              "leishmaniose",
    "mers-cov":                                "mers",
    "q-fieber":                                "q_fieber",
    "strongyloides":                           "strongyloidiasis",
    "tuberculose":                             "tuberkulose",
    "yellow fever":                            "yellow_fever",
    # Borreliose
    "lyme-borreliose":                        "borreliose",
    "borreliose (lyme)":                      "borreliose",
    # Ziel = Slug der tatsächlichen Syndrom-Datei (s. scripts/analysis/syndromes/),
    # nicht der englische/lateinische Name — sonst dieselbe Fragmentierung wie
    # oben bei West-Nil.
    "leishmaniose":                           "leishmaniose",
    "leishmaniasis":                          "leishmaniose",
    "schistosomiasis":                        "schistosomiasis",
    "toxoplasmose":                           "toxoplasmose",
    "trypanosomiasis":                        "trypanosomiasis",
    "amöbiasis":                              "entamoeba",   # keine eigene Syndrom-Datei (Stand jetzt)
    "brucellose":                             "brucellose",
    "leptospirose":                           "leptospirose",
    "tularaemie":                             "tularaemie",
    "tularämie":                              "tularaemie",
}


def _disease_key(disease: str, slug: str | None = None) -> str:
    """Kanonischer Schlüssel für Deduplication.

    Priorität: syndrome_slug > Alias-Tabelle > normalisierter Name.
    """
    # "generic" ist nur ein Fallback-Slug — nicht als Deduplications-Key verwenden
    if slug and slug.strip().lower() not in ("generic", "other", ""):
        return slug.strip().lower()
    d = disease.lower().strip()
    # Zuerst Alias prüfen (Präfix-Match)
    for alias, canonical in _DISEASE_CANONICAL.items():
        if d.startswith(alias) or alias in d:
            return canonical
    # Klammern und Einschübe entfernen
    d = _re.sub(r'\s*\([^)]{1,60}\)\s*', ' ', d)
    d = _re.sub(r'\s*/.*$', '', d)
    d = _re.sub(r'\s+', ' ', d).strip()
    # Maximal 3 Worte (Hauptname)
    return ' '.join(d.split()[:3])


def _aggregate_exposure(analysis: list[dict]) -> list[dict]:
    """Akkumuliert Expositions-Score pro Erreger über alle Aufenthalte.

    Verwendet syndrome_slug (wenn vorhanden) als Deduplication-Key,
    damit endemic_ref und Klimazonen-Modell denselben Erreger nicht
    doppelt führen.
    """
    scores: dict[str, dict] = {}

    def _add(disease: str, level: str, source_tag: str,
             days: int = 1, slug: str | None = None):
        key  = _disease_key(disease, slug)
        w    = _SEV_WEIGHT.get(level, 0.3)
        dur  = min(days, 30) / 30
        inc  = w * (0.3 + 0.7 * dur)
        if key not in scores:
            scores[key] = {"score": 0.0, "level": level,
                           "sources": set(), "stay_count": 0,
                           "disease": disease, "slug": slug or key}
        scores[key]["score"]      += inc
        scores[key]["stay_count"] += 1
        scores[key]["sources"].add(source_tag)
        # Höchstes Level und aussagekräftigster Name gewinnen
        cur_lvl = scores[key]["level"]
        if _SEV_WEIGHT.get(level, 0) > _SEV_WEIGHT.get(cur_lvl, 0):
            scores[key]["level"]   = level
            scores[key]["disease"] = disease

    for item in analysis:
        stay = item["stay"]
        days = stay.duration_d

        # Klimazonen-Basisrisiko
        zone = stay.climate_zone or _climate_zone(stay.lat, stay.lon,
                                                   stay.country_iso or "")
        if zone:
            for disease, level, _ in RISK_BY_CLIMATE.get(zone, []):
                _add(disease, level, f"klimazone:{zone}", days)

        # Länder-spezifische Zusatzrisiken
        iso = (stay.country_iso or "").upper()
        for disease, level, _ in RISK_BY_COUNTRY.get(iso, []):
            _add(disease, level, f"land:{iso}", days)

        # Aktive Ausbrüche
        for ev in item["outbreaks"]:
            sev = ev.get("severity", "medium")
            _add(ev["disease"], sev, f"ausbruch:{ev['source']}", days,
                 slug=ev.get("syndrome_slug"))

        # Endemie-Referenz
        for ev in item["endemic"]:
            sev = ev.get("severity", "low")
            _add(ev["disease"], sev, f"endemie:{ev.get('country_iso','')}", days,
                 slug=ev.get("syndrome_slug"))

    ranked = sorted(scores.values(), key=lambda x: -x["score"])
    for r in ranked:
        r["sources"] = sorted(r["sources"])
    return ranked


def save_to_db(conn: sqlite3.Connection, exposure: list[dict],
               dfrom: str, person: str = OWN_PERSON_ID) -> None:
    """Speichert Lifetime-Expositions-Zusammenfassung in pathogen_exposure_summary."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS pathogen_exposure_summary (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            person      TEXT    NOT NULL DEFAULT 'unknown',
            disease     TEXT    NOT NULL,
            slug        TEXT,
            risk_level  TEXT,
            score       REAL,
            stay_count  INTEGER,
            sources     TEXT,
            dfrom       TEXT,
            computed_at TEXT    NOT NULL
        )
    """)
    conn.execute(
        "DELETE FROM pathogen_exposure_summary WHERE person = ? AND dfrom = ?",
        (person, dfrom)
    )
    now = datetime.now(timezone.utc).isoformat()
    conn.executemany("""
        INSERT INTO pathogen_exposure_summary
            (person, disease, slug, risk_level, score, stay_count, sources,
             dfrom, computed_at)
        VALUES (?,?,?,?,?,?,?,?,?)
    """, [
        (person,
         r["disease"], r.get("slug"), r["level"],
         round(r["score"], 4), r["stay_count"],
         ",".join(r["sources"]),
         dfrom, now)
        for r in exposure
    ])
    conn.commit()


# ── Berichts-Ausgabe ──────────────────────────────────────────────────────────

_LEVEL_ICON = {"hoch": "██", "high": "██",
               "mittel": "▓░", "medium": "▓░",
               "niedrig": "░░", "low": "░░"}


def _render_report(stays: list[Stay],
                   analysis: list[dict],
                   exposure: list[dict],
                   sources_used: list[str]) -> str:
    lines = []
    today = datetime.now().strftime("%Y-%m-%d")

    lines += [
        "=" * 72,
        "LIFETIME PATHOGEN-EXPOSITIONSANALYSE",
        f"Erstellt: {today}",
        f"Quellen:  {', '.join(sources_used) or 'keine'}",
        f"Aufenthalte analysiert: {len(stays)}",
        "=" * 72,
        "",
    ]

    # 1. Aufenthaltszeitlinie
    lines += ["── AUFENTHALTE (Zeitlinie, chronologisch) " + "─" * 32, ""]
    non_home = [s for s in stays if s.duration_d >= 2]
    for stay in sorted(non_home, key=lambda s: s.date_from):
        item = next((x for x in analysis if x["stay"] is stay), None)
        ob_count = len(item["outbreaks"]) if item else 0
        en_count = len(item["endemic"])   if item else 0
        marker = " ⚠" if ob_count else ""
        lines.append(
            f"  {stay.date_from} – {stay.date_to}  "
            f"{stay.label:<28}  {stay.duration_d:>3}d  "
            f"[{stay.climate_zone or '?':>18}]  "
            f"{ob_count} Ausbrüche / {en_count} Endemien{marker}"
        )
    lines.append("")

    # 2. Aktive Ausbrüche die mit Aufenthalten überlappen
    outbreak_hits = [x for x in analysis if x["outbreaks"]]
    if outbreak_hits:
        lines += ["── AUSBRUCHS-ÜBERLAPPUNGEN " + "─" * 45, ""]
        for item in outbreak_hits:
            stay = item["stay"]
            lines.append(f"  {stay.date_from} {stay.label}:")
            for ev in item["outbreaks"][:5]:
                lines.append(
                    f"    • {ev['disease']:<40} "
                    f"[{ev.get('severity','?'):>6}]  "
                    f"Quelle: {ev.get('source','?')}"
                )
        lines.append("")

    # 3. Lifetime-Expositions-Rangliste
    lines += ["── LIFETIME ERREGER-EXPOSITIONSRANGLISTE " + "─" * 31, ""]
    lines.append(
        f"  {'Erreger':<42} {'Risiko':<8} {'Score':>6}  "
        f"{'Aufenthalte':>11}  Quellen"
    )
    lines.append("  " + "-" * 68)
    for exp in exposure[:40]:
        icon  = _LEVEL_ICON.get(exp["level"], "░░")
        srcs  = ", ".join(exp["sources"])[:30]
        name  = exp.get("disease", exp.get("slug", "?"))
        lines.append(
            f"  {icon} {name:<40} {exp['level']:<8} "
            f"{exp['score']:>6.2f}  "
            f"{exp['stay_count']:>4} Aufenth.  {srcs}"
        )
    lines.append("")

    # 4. Serologie-Empfehlungen (Top-20 mit Testhinweis)
    lines += ["── EMPFOHLENE SEROLOGIE (Arzt-Gespräch) " + "─" * 32, ""]
    recommended = []
    for exp in exposure:
        name = exp.get("disease", "")
        for key, test in SEROLOGY_MAP.items():
            if key.lower() in name.lower() or name.lower() in key.lower():
                recommended.append((name, exp["level"], exp["score"], test))
                break
    for disease, level, score, test in sorted(recommended, key=lambda x: -x[2])[:20]:
        lines.append(f"  [{level:>8}] {disease}")
        lines.append(f"             → {test}")
        lines.append("")

    # 5. Hinweise
    lines += [
        "── HINWEISE " + "─" * 60,
        "",
        "  • Score = akkumulierter Expositions-Index (Klimazone × Dauer ×",
        "    Schweregrad × Ausbruchs-Überlapp), kein medizinischer Wahrscheinlichkeitswert.",
        "  • Endemie-Risiken gelten für das Reiseziel, unabhängig von persönlichem",
        "    Verhalten (Mosquito-Schutz, Essen, Tierkontakt).",
        "  • Bereits geimpfte Erreger (FSME, Hep A, Typhus etc.) trotzdem aufführen",
        "    — Impf-Titer-Kontrolle kann sinnvoll sein.",
        "  • Serologie sinnvoll nur bei klinischem Verdacht oder nach",
        "    epidemiologischer Risikoabschätzung durch Infektiologen.",
        "",
    ]
    return "\n".join(lines)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(
        description="Lifetime-Pathogen-Expositionsanalyse aus GPS- und Reisedaten"
    )
    ap.add_argument("--from",       default=_cfg.birthdate or "1900-01-01", dest="dfrom",
                    help="Frühestes Datum (Standard: Geburtsdatum — dies ist eine "
                         "Lebenszeit-Expositionsanalyse; clinical.data_start ist NICHT "
                         "geeignet, da es die Baseline-Periode fuer Wearable-Daten meint)")
    ap.add_argument("--sources",    nargs="+",
                    choices=["travel", "db", "gpx", "google", "apple", "oura", "all"],
                    default=["all"],
                    help="Zu ladende Quellen (Standard: alle)")
    ap.add_argument("--out",        default=None,
                    help="Ausgabe-Datei (Standard: analyses/infectious/)")
    ap.add_argument("--no-geocode", action="store_true",
                    help="Kein Nominatim-API-Aufruf (offline)")
    ap.add_argument("--update",     action="store_true",
                    help="Ergebnis in DB (pathogen_exposure_summary) speichern "
                         "und Ausgabedatei überschreiben")
    ap.add_argument("--plot",       action="store_true",
                    help="(kompatibilitäts-Flag für analyse_all.py, kein Plot-Output)")
    ap.add_argument("--no-llm",     action="store_true")
    ap.add_argument("--person", default=OWN_PERSON_ID,
                    help=t("Person (Standard: selbst)", "Person (default: self)"))
    add_lang_arg(ap)
    args = ap.parse_args()
    apply_lang_from_args(args)

    # Im Batch-Modus (analyse_all.py) immer DB-Update durchführen
    import os as _os
    if _os.environ.get("KYORO_ANALYSES_DIR"):
        args.update = True

    use_all = "all" in (args.sources or [])
    use = lambda s: use_all or s in (args.sources or [])

    conn = open_db()
    geocache = _load_geocache()

    # Heimkoordinaten aus Config (für GPS-Clustering)
    home_lat = getattr(_cfg, "home_lat", None) or _cfg._cfg.get("home_lat")
    home_lon = getattr(_cfg, "home_lon", None) or _cfg._cfg.get("home_lon")

    # Imports-Wurzel (~ /Kyoro-HealthHub/imports)
    _imports = Path(_cfg._cfg.get("paths", {}).get(
        "data_root", str(Path.home() / "Kyoro-HealthHub" / "imports")))

    # GPS-Quellen laden
    stays: list[Stay] = []
    sources_used: list[str] = []

    if use("travel"):
        ts = _load_travel_history(args.dfrom)
        if ts:
            stays.extend(ts)
            sources_used.append(f"travel_history ({len(ts)})")
            print(f"  travel_history.json: {len(ts)} Einträge")

    if use("db"):
        db_s = _load_db_stays(conn, args.dfrom)
        if db_s:
            stays.extend(db_s)
            sources_used.append(f"location_stays_db ({len(db_s)})")
            print(f"  location_stays (DB): {len(db_s)} Einträge")
        db_h = _load_home_stays_db(conn, args.dfrom)
        if db_h:
            stays.extend(db_h)
            sources_used.append(f"home_residence_db ({len(db_h)})")
            print(f"  Wohnsitze (DB): {len(db_h)} Einträge")
        db_t = _load_db_session_tracks(conn, home_lat, home_lon, args.dfrom)
        if db_t:
            stays.extend(db_t)
            sources_used.append(f"session_tracks_db ({len(db_t)})")
            print(f"  session_tracks (DB): {len(db_t)} Einträge")

    if use("google"):
        google_path = None
        # Aus Config laden, falls angegeben
        cfg_path = (_cfg._cfg.get("paths", {}) or {}).get("google_timeline")
        if cfg_path:
            google_path = Path(cfg_path).expanduser()
        else:
            # Automatisch suchen
            for candidate in [
                Path.home() / "Downloads" / "Takeout",
                Path.home() / "Desktop"  / "Takeout",
                _imports / "google_takeout",
            ]:
                if candidate.is_dir():
                    google_path = candidate
                    break
        gs = _load_google_takeout(google_path, args.dfrom)
        if gs:
            stays.extend(gs)
            sources_used.append(f"google_takeout ({len(gs)})")
            print(f"  Google Takeout: {len(gs)} Aufenthalte")
        elif google_path:
            print(f"  Google Takeout: keine Daten in {google_path}")
        else:
            print("  Google Takeout: kein Pfad konfiguriert "
                  "(paths.google_timeline in health_config.json setzen)")

    if use("gpx"):
        gpx_path = None
        cfg_path = (_cfg._cfg.get("paths", {}) or {}).get("gpx_analysis_dir")
        if cfg_path:
            gpx_path = Path(cfg_path).expanduser()
        else:
            for candidate in [
                _imports / "gpx",
                _imports / "polar",
                _imports / "garmin",
            ]:
                if candidate.is_dir():
                    gpx_path = candidate
                    break
        gp = _load_gpx_directory(gpx_path, home_lat, home_lon, args.dfrom)
        if gp:
            stays.extend(gp)
            sources_used.append(f"gpx ({len(gp)})")
            print(f"  GPX-Dateien: {len(gp)} Aktivitäten außerhalb Heimbereich")

    if use("apple"):
        apple_path = None
        cfg_path = _cfg._cfg.get("apple_xml", "")
        if cfg_path:
            apple_path = Path(cfg_path).expanduser().parent
        ah = _load_apple_health_routes(apple_path, home_lat, home_lon, args.dfrom)
        if ah:
            stays.extend(ah)
            sources_used.append(f"apple_health_routes ({len(ah)})")
            print(f"  Apple Health Workout-Routes: {len(ah)} außerhalb Heimbereich")

    if use("oura"):
        oura_path = None
        cfg_path = (_cfg._cfg.get("paths", {}) or {}).get("oura_dir")
        if cfg_path:
            oura_path = Path(cfg_path).expanduser()
        else:
            for candidate in [
                _imports / "oura",
                _imports / "oura" / "data_csv",
                Path.home() / "Downloads" / "oura",
            ]:
                if candidate.is_dir():
                    oura_path = candidate
                    break
        ou_all = _load_oura_location(oura_path, None, None, args.dfrom)
        ou = _load_oura_location(oura_path, home_lat, home_lon, args.dfrom)
        if ou:
            stays.extend(ou)
            sources_used.append(f"oura_gps ({len(ou)})")
            print(f"  Oura GPS: {len(ou)} Aufenthalte außerhalb Heimbereich"
                  f" (von {len(ou_all)} gesamt)")
        elif oura_path and ou_all:
            print(f"  Oura GPS: {len(ou_all)} Aufenthalte geladen, "
                  f"alle im Heimbereich gefiltert — Daten vorhanden aber lokal")
        elif oura_path:
            print(f"  Oura GPS: keine rawlocation.csv in {oura_path}")
        else:
            print("  Oura GPS: kein Verzeichnis gefunden "
                  "(paths.oura_dir in health_config.json oder imports/oura/)")

    if not stays:
        print("\nKeine Aufenthaltsdaten gefunden.")
        print("Tipp: Reisedaten mit 'python3 manage_travel_history.py add' erfassen.")
        conn.close()
        return

    print(f"\n  Gesamt: {len(stays)} Aufenthalte aus {len(sources_used)} Quelle(n)")

    # Geocoding-Anreicherung
    if not args.no_geocode:
        missing_geo = [s for s in stays if not s.country_iso and s.lat]
        if missing_geo:
            print(f"  Geocoding: {len(missing_geo)} Aufenthalte via Nominatim …")
        for stay in stays:
            _enrich_stay(stay, geocache)
        _save_geocache(geocache)
    else:
        for stay in stays:
            if not stay.climate_zone and stay.country_iso:
                stay.climate_zone = _climate_zone(stay.lat, stay.lon,
                                                   stay.country_iso)

    # Heimaufenthalte herausfiltern
    significant = [
        s for s in stays
        if s.duration_d >= 1 or s.source == "travel_history"
    ]

    # Ausbruchs- und Endemie-Daten laden
    outbreaks = _load_outbreak_events(conn, args.dfrom)
    endemic   = _load_endemic_ref(conn)
    print(f"  Ausbruchs-DB: {len(outbreaks)} Events, {len(endemic)} Endemie-Einträge")

    # Analyse
    analysis = analyse_stays(significant, outbreaks, endemic)
    exposure  = _aggregate_exposure(analysis)

    conn.close()

    # Bericht
    report = _render_report(significant, analysis, exposure, sources_used)
    llm_text = "" if args.no_llm else _run_llm(report)
    content = report
    if llm_text:
        content += t("\n\n## Klinische Interpretation\n\n", "\n\n## Clinical Interpretation\n\n") + llm_text + "\n"

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = Path(args.out) if args.out else \
               OUT_DIR / f"pathogen_exposure_{datetime.now().strftime('%Y-%m-%d')}.txt"
    out_path.write_text(content, encoding="utf-8")
    print(f"\nBericht gespeichert: {out_path}")

    if args.update:
        conn2 = open_db()
        save_to_db(conn2, exposure, args.dfrom)
        conn2.close()
        print("  → pathogen_exposure_summary in DB gespeichert.")
        print("  Tipp: Nachträgliche Reiseeinträge hinzufügen und erneut")
        print("        --update ausführen — alle Quellen werden neu gelesen.")

    print(report)


if __name__ == "__main__":
    main()
