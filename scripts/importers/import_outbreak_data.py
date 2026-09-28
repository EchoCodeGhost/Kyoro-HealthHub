#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
import_outbreak_data.py — Ausbruchsdaten-Import: Alle 6 WHO-Regionen und weitere Quellen

@tier        infrastructure
@purpose.de  Importiert Ausbruchsdaten aus mehreren Quellen in die health.db für epidemiologische Analysen
@purpose.en  Imports outbreak data from multiple sources into health.db for epidemiological analysis
@method.de   Aggregiert Daten aus allen 6 WHO-Regionen (EMRO, AFRO, PAHO, SEARO, EURO, WPRO), ECDC, EFSA,
             GDELT, ProMED, RKI SurvStat, RKI GrippeWeb, RKI ARE-Konsultationsinzidenz, LGL Bayern,
             WAHIS/WOAH, WAHIS-Wild, CDC Travel, HealthMap, Eurosurveillance, ReliefWeb, CRM,
             FLI West-Nil-Virus und Aviäre Influenza (Landkreise, einzige
             Playwright-basierte Quellen) und statische Endemie-Referenzdaten.
             Daten werden in Tabellen geschrieben mit Feldern: source, typ, country,
             region, date, cases, deaths, severity, coordinates, notes.
             Unterstuetzt RSS- und API-basierte Quellen. Enthaelt Mapping zu Syndrom-Slugs.
@method.en   Aggregates data from all 6 WHO regions (EMRO, AFRO, PAHO, SEARO, EURO, WPRO), ECDC, EFSA,
             GDELT, ProMED, RKI SurvStat, RKI GrippeWeb, RKI ARE consultation incidence, LGL Bayern,
             WAHIS/WOAH, WAHIS-Wild, CDC Travel, HealthMap, Eurosurveillance, ReliefWeb, CRM,
             FLI West Nile Virus and Avian Influenza (district-level, the only
             Playwright-based sources) and static endemic reference data.
             Data is written to tables with fields: source, typ, country,
             region, date, cases, deaths, severity, coordinates, notes.
             Supports RSS- and API-based sources. Includes mapping to syndrome slugs.
@reads       Verschiedene Online-Quellen (RSS, SOAP API) und eingebettete Endemie-Referenzdaten
@writes      outbreak_reports, outbreak_sources, import_log
@limits.de   Abhaengig von Quellen-Verfuegbarkeit. Keine medizinische Validierung der Ausbruchsdaten.
             Endemie-Referenzdaten sind statisch und muessen manuell aktualisiert werden.
             ALLGEMEINE Daten, keine personenbezogenen: WHO/ECDC/RKI-Meldedaten und die
             statische Endemie-Referenztabelle (Ort/Erreger/Saison) sind unabhaengig von
             der eigenen Reise-/Standort-Historie — geprueft, keine Verbindung zu
             travel_history.json/location_stays im Code. Es wird immer dieselbe globale
             Datenmenge geholt, unabhaengig davon, wo die Person war oder hinwill.
             `person` in den Schreibpfaden ist deshalb kein echtes Dateneigentums-Feld
             wie bei anderen Importern, sondern nur ein pauschaler "fuer wen relevant"-
             Tag auf sonst voellig allgemeinen Daten — deshalb bewusst NICHT Teil des
             --person-Konventions-Fixes in den anderen Importern (s. OpenSpec-Change
             add-importer-person-override-convention, Task 3.3 Punkt 5: Grenzfall,
             niedrige Prioritaet, hier dokumentiert statt gefixt).

@relevance.de  Ermöglicht den Import von Gesundheitsdaten, essentiell für die umfassende Datenanalyse
@relevance.en  Enables import of health data, essential for comprehensive data analysis
@limits.en   Depends on source availability. No medical validation of outbreak data.
             Endemic reference data is static and must be manually updated.
             GENERAL data, not personal: WHO/ECDC/RKI surveillance data and the static
             endemic reference table (location/pathogen/season) are independent of the
             owner's travel/location history — checked, no connection to
             travel_history.json/location_stays anywhere in the code. The same global
             dataset is always fetched, regardless of where the person has been or is
             going. `person` in the write paths is therefore not a real data-ownership
             field the way it is in other importers, just a blanket "relevant for whom"
             tag on otherwise fully general data — deliberately NOT part of the
             --person convention fix applied to the other importers (see OpenSpec change
             add-importer-person-override-convention, task 3.3 item 5: edge case, low
             priority, documented here instead of fixed).
@usage
    python3 import_outbreak_data.py
    python3 import_outbreak_data.py --list-sources
    python3 import_outbreak_data.py --sources who rki cdc_travel crm endemic
    python3 import_outbreak_data.py --sources promedmail --dry-run
    python3 import_outbreak_data.py --full-history  # einmaliger Backfill GrippeWeb + ARE-Konsultationsinzidenz + RKI SurvStat
"""
import argparse
import json
import re
import sqlite3
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from xml.sax.saxutils import escape

sys.path.insert(0, str(Path(__file__).parent.parent))
from health_config import Config as _Cfg, OWN_PERSON_ID as _OWN_PERSON_ID
from modules.db import open_db, DB_ERRORS
from modules.base import ImportResult, log_import
from modules.i18n import t, set_lang, add_lang_arg, apply_lang_from_args

_cfg = _Cfg()

# ── Krankheitsname → syndrome_slug Mapping ──────────────────────────────────

DISEASE_SLUG_MAP: dict[str, str] = {
    # Long COVID / SARS-CoV-2
    "covid-19": "post_covid", "sars-cov-2": "post_covid", "coronavirus": "post_covid",
    # Borreliose
    "lyme": "borreliose", "borreliosis": "borreliose", "lyme disease": "borreliose",
    # Q-Fieber
    "q fever": "q_fieber", "q-fever": "q_fieber", "coxiella": "q_fieber",
    # EBV
    "epstein-barr": "ebv", "ebv": "ebv", "infectious mononucleosis": "ebv",
    "mononucleosis": "ebv", "pfeiffer": "ebv",
    # Bartonellose
    "bartonella": "bartonellose", "bartonellosis": "bartonellose",
    "cat scratch": "bartonellose",
    # FSME
    "tick-borne encephalitis": "fsme", "tbe": "fsme", "fsme": "fsme",
    "frühsommer-meningoenzephalitis": "fsme",
    # Aviäre Influenza (muss VOR der generischen "influenza"-Zeile geprüft
    # werden — "influenza" ist Teilstring von "avian influenza"/"aviäre
    # influenza", _slug_from_disease() gäbe sonst faelschlich "influenza"
    # zurueck. h5n1/h5n2/h7n9 vorher faelschlich auf "influenza" gemappt.)
    "avian influenza": "aviaere_influenza", "aviäre influenza": "aviaere_influenza",
    "h5n1": "aviaere_influenza", "h5n8": "aviaere_influenza",
    "h7n9": "aviaere_influenza", "geflügelpest": "aviaere_influenza",
    "bird flu": "aviaere_influenza",
    # "fowl plague" ist die aeltere Bezeichnung fuer die Gefluegelpest und
    # muss hier stehen, bevor weiter unten "plague" auf die Pest gemappt wird
    "fowl plague": "aviaere_influenza",
    # Influenza (saisonal, human-adaptiert — H1N1/H3N2 sind saisonale
    # Subtypen, nicht die aviären H5/H7-Stämme oben)
    "influenza": "influenza", "flu": "influenza", "grippe": "influenza",
    "h1n1": "influenza", "h3n2": "influenza",
    # LCMV (muss VOR "cmv" geprüft werden — "cmv" ist Teilstring von "lcmv",
    # _slug_from_disease() gibt sonst faelschlich "cmv" zurueck)
    "lcmv": "lcmv", "lymphocytic choriomeningitis": "lcmv",
    "lymphozytäre choriomeningitis": "lcmv",
    # CMV
    "cytomegalovirus": "cmv", "cmv": "cmv",
    # Anaplasmose
    "anaplasmosis": "anaplasmose", "anaplasma": "anaplasmose",
    "human granulocytic": "anaplasmose",
    # Babesiose
    "babesiosis": "babesiose", "babesia": "babesiose",
    # Dengue
    "dengue": "dengue",
    # Parvovirus
    "parvovirus": "parvovirus", "erythema infectiosum": "parvovirus",
    "fifth disease": "parvovirus", "ringelröteln": "parvovirus",
    # Mycoplasma
    "mycoplasma": "mycoplasma", "walking pneumonia": "mycoplasma",
    # HHV-6
    "hhv-6": "hhv6", "human herpesvirus 6": "hhv6", "roseola": "hhv6",
    "exanthema subitum": "hhv6",
    # Enterovirus
    "enterovirus": "enterovirus", "coxsackie": "enterovirus",
    "hand foot mouth": "enterovirus", "hfmd": "enterovirus",
    "echovirus": "enterovirus",
    # Chlamydia pneumoniae
    "chlamydia pneumoniae": "chlamydia_pneumoniae",
    "chlamydophila": "chlamydia_pneumoniae",
    # Pest (Yersinia pestis) — muss VOR "yersinia" geprueft werden, sonst
    # greift die Enteritis-Yersiniose. Bewusst KEIN Schluessel "pest": das
    # waere Teilstring von "geflügelpest"/"schweinepest"/"peste porcine".
    "pestis": "pest", "plague": "pest", "beulenpest": "pest",
    "lungenpest": "pest", "bubonic": "pest", "pneumonic plague": "pest",
    # Yersiniose
    "yersinia": "yersiniose", "yersiniosis": "yersiniose",
    # Toxoplasmose
    "toxoplasma": "toxoplasmose", "toxoplasmosis": "toxoplasmose",
    # Brucellose
    "brucella": "brucellose", "brucellosis": "brucellose",
    # Chikungunya
    "chikungunya": "chikungunya",
    # Zika
    "zika": "zika",
    # Giardiose
    "giardia": "giardiose", "giardiasis": "giardiose", "lamblia": "giardiose",
    # Kryptosporidiose
    "cryptosporidium": "kryptosporidiose", "cryptosporidiosis": "kryptosporidiose",
    "kryptosporidiose": "kryptosporidiose",
    # Rickettsiosen mit eigenem Syndrom — alle drei muessen VOR dem
    # generischen "rickettsia" stehen, sonst verdeckt es sie. Innerhalb des
    # Blocks zuerst das murine Fleckfieber, weil "fleckfieber" Teilstring von
    # "murines fleckfieber" ist. Bewusst KEIN Schluessel "typhus": im
    # Deutschen bezeichnet das den Typhus abdominalis, nicht das Fleckfieber.
    # Die Zeckenbiss-Rickettsiosen tragen im Deutschen ebenfalls "Fleckfieber"
    # im Namen, gehoeren aber zum generischen rickettsia-Syndrom — sie muessen
    # daher vor dem "fleckfieber"-Schluessel weiter unten abgefangen werden
    "mittelmeerfleckfieber": "rickettsia", "zeckenbissfieber": "rickettsia",
    "felsengebirgsfleckfieber": "rickettsia", "conorii": "rickettsia",
    "rickettsialpox": "rickettsia",
    "murine typhus": "fleckfieber_murin", "rickettsia typhi": "fleckfieber_murin",
    "murines fleckfieber": "fleckfieber_murin",
    "endemisches fleckfieber": "fleckfieber_murin",
    "flea-borne typhus": "fleckfieber_murin",
    "epidemic typhus": "fleckfieber_epidemisch",
    "prowazekii": "fleckfieber_epidemisch",
    "brill-zinsser": "fleckfieber_epidemisch",
    "louse-borne typhus": "fleckfieber_epidemisch",
    "fleckfieber": "fleckfieber_epidemisch",
    "scrub typhus": "tsutsugamushi", "tsutsugamushi": "tsutsugamushi",
    "orientia": "tsutsugamushi",
    # Rickettsia
    "rickettsia": "rickettsia", "spotted fever": "rickettsia",
    "rocky mountain": "rickettsia", "mediterranean spotted": "rickettsia",
    # Leishmaniose
    "leishmaniasis": "leishmaniose", "leishmania": "leishmaniose",
    # Malaria
    "malaria": "malaria", "plasmodium": "malaria",
    # West Nil
    "west nile": "west_nile", "wnv": "west_nile",
    # Usutu-Virus
    "usutu": "usutu",
    # Sindbis-Virus
    "sindbis": "sindbis_virus", "ockelbo": "sindbis_virus", "pogosta": "sindbis_virus",
    # Echinokokkose
    "echinococcosis": "echinokokkose", "echinokokkose": "echinokokkose",
    "echinococcus": "echinokokkose",
    # Salmonellose
    "salmonella": "salmonellose", "salmonellosis": "salmonellose",
    # Pseudocowpox/Melkerknoten muss VOR "cowpox" geprüft werden — "cowpox"
    # ist Teilstring von "pseudocowpox", sonst faelschlich "kuhpocken" zurueck
    "pseudocowpox": "parapockenviren", "paravaccinia": "parapockenviren",
    # Kuhpocken
    "cowpox": "kuhpocken", "kuhpocken": "kuhpocken",
    # Igel-Ringworm / Dermatophytose
    "trichophyton erinacei": "igel_dermatophytose",
    # Igelmilben
    "caparinia": "igelmilben",
    # Rattenbissfieber
    "rat-bite fever": "rattenbissfieber", "rattenbissfieber": "rattenbissfieber",
    "streptobacillus moniliformis": "rattenbissfieber", "haverhill fever": "rattenbissfieber",
    # Fuchsräude
    "fuchsräude": "fuchsraeude", "fox mange": "fuchsraeude",
    # Demodikose
    "demodex": "demodikose", "demodikose": "demodikose", "demodicosis": "demodikose",
    # Parapockenviren (Orf/Melkerknoten) — pseudocowpox/paravaccinia bereits
    # weiter oben vor "cowpox" definiert (Verdeckungs-Fix)
    "orf virus": "parapockenviren", "ecthyma contagiosum": "parapockenviren",
    "melkerknoten": "parapockenviren",
    # Newcastle-Krankheit (humane Konjunktivitis)
    "newcastle disease": "newcastle_konjunktivitis",
    "newcastle-krankheit": "newcastle_konjunktivitis",
    # Sandfliegenfieber / Pappataci-Fieber (Toscana-/Sizilianisches/Neapel-Virus)
    "toscana virus": "sandfliegenfieber", "toscana-virus": "sandfliegenfieber",
    "pappataci": "sandfliegenfieber", "sandfly fever": "sandfliegenfieber",
    "sandfliegenfieber": "sandfliegenfieber", "sandmückenfieber": "sandfliegenfieber",
    # Trichinellose
    "trichinellosis": "trichinellose", "trichinellose": "trichinellose",
    "trichinosis": "trichinellose",
    # Läuseübertragenes Rückfallfieber (B. recurrentis) — muss VOR dem
    # generischen "relapsing fever" stehen, das auf das zeckenuebertragene
    # Rueckfallfieber (B. miyamotoi) gemappt ist
    "louse-borne relapsing fever": "rueckfallfieber_laeuse",
    "louse borne relapsing fever": "rueckfallfieber_laeuse",
    "recurrentis": "rueckfallfieber_laeuse",
    "läuserückfallfieber": "rueckfallfieber_laeuse",
    # Borrelia miyamotoi (Zecken-Rückfallfieber)
    "miyamotoi": "borrelia_miyamotoi", "relapsing fever": "borrelia_miyamotoi",
    # Neoehrlichiose
    "neoehrlichia": "neoehrlichiose", "neoehrlichiosis": "neoehrlichiose",
    # Alpha-Gal-Syndrom
    "alpha-gal": "alpha_gal", "alpha gal": "alpha_gal",
    # Zeckenlähmung
    "tick paralysis": "zeckenlaehmung", "zeckenlähmung": "zeckenlaehmung",
    # Mpox/Monkeypox
    "mpox": "mpox", "monkeypox": "mpox",
    # Hepatitis A
    "hepatitis a": "hepatitis_a", "hep a": "hepatitis_a",
    # Ebola / Marburg
    "ebola": "ebola_marburg", "marburg": "ebola_marburg",
    # Gelbfieber
    "yellow fever": "yellow_fever", "gelbfieber": "yellow_fever",
    # Hepatitis E
    "hepatitis e": "hepatitis_e", "hep e": "hepatitis_e",
    # Amöbiasis
    "amoebiasis": "entamoeba", "amebiasis": "entamoeba",
    "amöbiasis": "entamoeba", "entamoeba": "entamoeba",
    # Nicht-Cholera-Vibrionen (Wund-/Sepsisform) — muss VOR "cholera" stehen,
    # weil "non-cholera vibrio" selbst die Zeichenkette "cholera" enthaelt und
    # sonst faelschlich auf den Cholera-Slug traefe
    "vibrio vulnificus": "vibrio_non_cholerae", "vibrio parahaemolyticus": "vibrio_non_cholerae",
    "vibrio alginolyticus": "vibrio_non_cholerae", "vibrio spp": "vibrio_non_cholerae",
    "vibrionen": "vibrio_non_cholerae", "non-cholera vibrio": "vibrio_non_cholerae",
    # Cholera
    "cholera": "cholera",
    # Meningokokken (bewusst spezifisch, nicht "meningitis" — zu unspezifisch,
    # würde auch virale/andere bakterielle Meningitiden fälschlich zuordnen)
    "meningococc": "meningokokken", "meningokokk": "meningokokken",
    # Polio
    "poliomyelitis": "polio", "polio": "polio",
    # Coccidioidomykose
    "coccidioidomycosis": "coccidioidomykose", "coccidioides": "coccidioidomykose",
    "valley fever": "coccidioidomykose",
    # Histoplasmose
    "histoplasmosis": "histoplasmose", "histoplasma": "histoplasmose",
    # Strongyloidiasis
    "strongyloidiasis": "strongyloidiasis", "strongyloides": "strongyloidiasis",
    # Japanische Enzephalitis
    "japanese encephalitis": "japanische_enzephalitis",
    "japanische enzephalitis": "japanische_enzephalitis",
    # Rabies/Tollwut
    "rabies": "rabies", "tollwut": "rabies",
    "lyssavirus": "rabies", "eblv": "rabies", "fledermaus-lyssavirus": "rabies",
    "bblv": "rabies", "bokeloh": "rabies",
    # Tuberkulose
    "tuberculosis": "tuberkulose", "tuberkulose": "tuberkulose", "tbc": "tuberkulose",
    # Hepatitis B
    "hepatitis b": "hepatitis_b", "hep b": "hepatitis_b",
    # Toxocariose (Hunde-/Katzenspulwurm)
    "toxocar": "toxocariose", "larva migrans": "toxocariose",
    "spulwurm": "toxocariose",
    # Capnocytophaga (Hunde-/Katzenbiss-Sepsis)
    "capnocytophaga": "capnocytophaga", "canimorsus": "capnocytophaga",
    # Milzbrand / Anthrax
    "anthrax": "milzbrand", "milzbrand": "milzbrand", "anthracis": "milzbrand",
    # Angiostrongyliasis (Rattenlungenwurm)
    "angiostrongyl": "angiostrongyliasis", "rat lungworm": "angiostrongyliasis",
    "rattenlungenwurm": "angiostrongyliasis",
    "eosinophilic meningitis": "angiostrongyliasis",
    # Powassan (nordamerikanische Zecken-Enzephalitis)
    "powassan": "powassan", "powv": "powassan", "deer tick virus": "powassan",
    # Naegleria fowleri (primaere amoebische Meningoenzephalitis)
    "naegleria": "naegleriasis", "primary amebic meningoencephalitis": "naegleriasis",
    "primäre amöbische meningoenzephalitis": "naegleriasis", "brain-eating amoeba": "naegleriasis",
    # Candida auris
    "candida auris": "candida_auris", "candidozyma auris": "candida_auris",
}


def _slug_from_disease(disease: str) -> str | None:
    d = disease.lower()
    for key, slug in DISEASE_SLUG_MAP.items():
        if key in d:
            return slug
    return None


# ── Länder → ISO ──────────────────────────────────────────────────────────────

COUNTRY_ISO: dict[str, str] = {
    "germany": "DE", "deutschland": "DE", "france": "FR", "frankreich": "FR",
    "spain": "ES", "spanien": "ES", "italy": "IT", "italien": "IT",
    "greece": "GR", "griechenland": "GR", "turkey": "TR", "türkei": "TR",
    "portugal": "PT", "croatia": "HR", "kroatien": "HR",
    "austria": "AT", "österreich": "AT", "switzerland": "CH",
    "netherlands": "NL", "niederlande": "NL", "belgium": "BE",
    "poland": "PL", "czech republic": "CZ", "hungary": "HU",
    "romania": "RO", "bulgaria": "BG", "sweden": "SE", "norway": "NO",
    "denmark": "DK", "finland": "FI", "united kingdom": "GB", "uk": "GB",
    "egypt": "EG", "ägypten": "EG", "morocco": "MA", "marokko": "MA",
    "tunisia": "TN", "tunesien": "TN", "israel": "IL",
    "thailand": "TH", "vietnam": "VN", "indonesia": "ID", "bali": "ID",
    "malaysia": "MY", "philippines": "PH", "japan": "JP",
    "india": "IN", "indien": "IN", "sri lanka": "LK",
    "mexico": "MX", "mexiko": "MX", "brazil": "BR", "brasilien": "BR",
    "colombia": "CO", "peru": "PE", "cuba": "CU", "argentina": "AR",
    "united states": "US", "usa": "US", "canada": "CA",
    "australia": "AU", "new zealand": "NZ",
    "kenya": "KE", "kenia": "KE", "tanzania": "TZ", "south africa": "ZA",
    "china": "CN", "south korea": "KR", "taiwan": "TW",
    "cambodia": "KH", "laos": "LA", "myanmar": "MM",
    "nigeria": "NG", "congo": "CD", "ethiopia": "ET", "ghana": "GH",
}


def _iso_from_country(country: str) -> str | None:
    return COUNTRY_ISO.get(country.lower().strip())


# ── Statische Endemie-Referenzdaten ──────────────────────────────────────────
# Quellen: ECDC/ECPHO-Risikoprofile, CDC Travelers' Health, RKI-Ratgeber,
#          WHO Global Health Observatory (Stand 2026)

ENDEMIC_REFERENCE: list[dict] = [
    # ── Deutschland / DACH ────────────────────────────────────────────────────
    # Die frueheren groben Deutschland-Eintraege hier (Bayern/Baden-Württemberg,
    # je ein Punkt ohne radius_km) sind entfernt -- fetch_lgl_fsme() deckt
    # Deutschland jetzt mit 185 landkreisgenauen Eintraegen (source='lgl_fsme')
    # ab. Die beiden groben Punkte blockierten in _structural_exposure_hits()
    # die praeziseren lgl_fsme-Treffer ("erster Treffer pro Slug gewinnt" und
    # die alten Eintraege kamen in der DB zuerst). Die Nachbarlaender unten
    # (Oesterreich, Schweiz, Tschechien etc.) bleiben unberuehrt -- dafuer gibt
    # es (noch) keine landkreisgenaue Alternative.
    {"disease": "FSME", "slug": "fsme", "country": "Österreich", "iso": "AT",
     "region": "Gesamtösterreich", "lat": 47.8, "lon": 13.0,
     "season": "04-10", "severity": "medium"},
    {"disease": "Lyme-Borreliose", "slug": "borreliose",
     "country": "Deutschland", "iso": "DE", "region": "Gesamtdeutschland",
     "lat": 51.0, "lon": 10.0, "season": "04-10", "severity": "low"},
    {"disease": "Lyme-Borreliose", "slug": "borreliose",
     "country": "Österreich", "iso": "AT", "region": "Gesamtösterreich",
     "lat": 47.8, "lon": 13.0, "season": "04-10", "severity": "low"},
    {"disease": "Toxocariose (Hunde-/Katzenspulwurm)", "slug": "toxocariose",
     "country": "Deutschland", "iso": "DE", "region": "Gesamtdeutschland",
     "lat": 51.0, "lon": 10.0, "season": "01-12", "severity": "low",
     "note": "Bodengebundene Zoonose (Sandkaesten, Gaerten, Parks) statt "
             "direkter Tierkontakt — ubiquitaer in Mitteleuropa, keine "
             "regionale Differenzierung sinnvoll, daher bewusst als "
             "Flaechen-Eintrag ohne Landkreis-Aufloesung"},
    # ── Nord-/Ostsee (klimawandelbedingte Vibrionen-Ausbreitung) ────────────────
    {"disease": "Nicht-Cholera-Vibrionen (Wund-/Sepsisform)", "slug": "vibrio_non_cholerae",
     "country": "Deutschland", "iso": "DE", "region": "Ostseeküste (MV/SH)",
     "lat": 54.2, "lon": 12.1, "season": "06-09", "severity": "medium",
     "note": "Seit 2020 eigenstaendig meldepflichtig (§7 IfSG); RKI zaehlte 2024 "
             "95 Faelle bundesweit (42 in Deutschland erworben), mehrere "
             "Todesfaelle mit Ostsee-Bezug in Mecklenburg-Vorpommern. Risiko "
             "steigt mit Wassertemperatur (>20°C) — klassischer "
             "Klimawandel-Gewinner unter den Erregern"},
    {"disease": "Nicht-Cholera-Vibrionen (Wund-/Sepsisform)", "slug": "vibrio_non_cholerae",
     "country": "USA", "iso": "US", "region": "Golfküste (Florida/Texas/Louisiana)",
     "lat": 29.5, "lon": -89.0, "season": "05-10", "severity": "high",
     "note": "Globaler Hotspot fuer V. vulnificus; 8-facher Fallzahlanstieg an "
             "der US-Ostkueste 1988-2018 mit dokumentierter geografischer "
             "Ausbreitung (Baker-Austin 2018, Scientific Reports 2023)"},
    # ── Schweiz ───────────────────────────────────────────────────────────────
    {"disease": "FSME", "slug": "fsme", "country": "Schweiz", "iso": "CH",
     "region": "Gesamtschweiz (Mittelland + Nordalpen)", "lat": 47.0, "lon": 8.2,
     "season": "04-10", "severity": "medium",
     "note": "CH hat eine der höchsten FSME-Inzidenzen Europas; BAG-Risikogebiete v.a. Mittelland"},
    {"disease": "Lyme-Borreliose", "slug": "borreliose",
     "country": "Schweiz", "iso": "CH", "region": "Gesamtschweiz",
     "lat": 47.0, "lon": 8.2, "season": "04-10", "severity": "low"},
    # ── Mittelmeer ────────────────────────────────────────────────────────────
    {"disease": "Rickettsia conorii (Mittelmeerfleckfieber)", "slug": "rickettsia",
     "country": "Spanien", "iso": "ES", "region": "Balearen",
     "lat": 39.6, "lon": 2.9, "season": "04-10", "severity": "medium",
     "note": "Rhipicephalus sanguineus Zecke, Hunde als Reservoir"},
    {"disease": "Rickettsia conorii", "slug": "rickettsia",
     "country": "Spanien", "iso": "ES", "region": "Kanarische Inseln",
     "lat": 28.1, "lon": -15.4, "season": "01-12", "severity": "low"},
    {"disease": "Rickettsia conorii", "slug": "rickettsia",
     "country": "Frankreich", "iso": "FR", "region": "Südfrankreich",
     "lat": 43.5, "lon": 5.0, "season": "04-10", "severity": "medium"},
    # Tigermücke (Aedes albopictus) in Frankreich seit ca. 2021 etabliert
    # (s. dengue.json/chikungunya.json/zika.json system_prompt) -- since_date
    # verhindert rueckwirkende Anwendung auf aeltere Frankreich-Reisen, analog
    # zu den deutschen Tigermuecken-Landkreisen. Bergerac (Dordogne) zusaetzlich
    # als eigener Punkt: dokumentierter autochthoner Ausbruch 2025 mit >700
    # Faellen (Frank/Jung-Sendzik, RKI Epid Bull 2025;29:24-27).
    {"disease": "Dengue-Fieber", "slug": "dengue",
     "country": "Frankreich", "iso": "FR", "region": "Südfrankreich",
     "lat": 43.5, "lon": 5.0, "radius_km": 150.0, "since": "2021-01-01",
     "season": "05-10", "severity": "low"},
    {"disease": "Chikungunya-Fieber", "slug": "chikungunya",
     "country": "Frankreich", "iso": "FR", "region": "Südfrankreich",
     "lat": 43.5, "lon": 5.0, "radius_km": 150.0, "since": "2021-01-01",
     "season": "05-10", "severity": "low"},
    {"disease": "Dengue-Fieber", "slug": "dengue",
     "country": "Frankreich", "iso": "FR", "region": "Bergerac (Dordogne)",
     "lat": 44.85, "lon": 0.48, "radius_km": 40.0, "since": "2025-01-01",
     "season": "05-10", "severity": "medium",
     "note": "Autochthoner Ausbruch 2025, >700 Fälle, teils grenznah zu Deutschland"},
    {"disease": "Chikungunya-Fieber", "slug": "chikungunya",
     "country": "Frankreich", "iso": "FR", "region": "Bergerac (Dordogne)",
     "lat": 44.85, "lon": 0.48, "radius_km": 40.0, "since": "2025-01-01",
     "season": "05-10", "severity": "medium",
     "note": "Autochthoner Ausbruch 2025, >700 Fälle, teils grenznah zu Deutschland"},
    # Niederlande: FSME erstmals 2016 autochthon nachgewiesen (Utrechtse
    # Heuvelrug UND Sallandse Heuvelrug Nationalparks) -- since_date, da erst
    # seit 2016 dokumentiert, nicht seit jeher endemisch wie DACH.
    {"disease": "FSME", "slug": "fsme",
     "country": "Niederlande", "iso": "NL", "region": "Utrechtse Heuvelrug",
     "lat": 52.03, "lon": 5.40, "radius_km": 25.0, "since": "2016-01-01",
     "season": "04-10", "severity": "low"},
    {"disease": "FSME", "slug": "fsme",
     "country": "Niederlande", "iso": "NL", "region": "Sallandse Heuvelrug",
     "lat": 52.38, "lon": 6.35, "radius_km": 25.0, "since": "2016-01-01",
     "season": "04-10", "severity": "low"},
    # Belgien: erste bestaetigte autochthone FSME-Faelle 2020 (Region nicht
    # naeher spezifiziert), Haushalts-Cluster 2025 in Limburg (Genk) --
    # since_date=2020, da erst juengst dokumentiert. Luxemburg bewusst NICHT
    # aufgenommen: trotz Untersuchung von ~4500 Zecken kein FSME-Virus
    # nachgewiesen, kein bestaetigter autochthoner Fall (Stand 2026).
    {"disease": "FSME", "slug": "fsme",
     "country": "Belgien", "iso": "BE", "region": "Limburg",
     "lat": 50.97, "lon": 5.50, "radius_km": 40.0, "since": "2020-01-01",
     "season": "04-10", "severity": "low",
     "note": "Erste autochthone Faelle 2020; Haushalts-Cluster 2025 (Limburg/Genk)"},
    {"disease": "Rickettsia conorii", "slug": "rickettsia",
     "country": "Italien", "iso": "IT", "region": "Sizilien/Sardinien",
     "lat": 37.5, "lon": 14.0, "season": "04-10", "severity": "medium"},
    {"disease": "Rickettsia conorii", "slug": "rickettsia",
     "country": "Griechenland", "iso": "GR", "region": "Gesamtgriechenland",
     "lat": 39.0, "lon": 22.0, "season": "04-10", "severity": "medium"},
    {"disease": "Leishmaniose (kutan/viszeral)", "slug": "leishmaniose",
     "country": "Spanien", "iso": "ES", "region": "Balearen/Valencia/Andalusien",
     "lat": 39.6, "lon": 2.9, "season": "06-10", "severity": "low",
     "note": "Phlebotomus-Sandmücken, Hunde als Reservoir"},
    {"disease": "Leishmaniose", "slug": "leishmaniose",
     "country": "Griechenland", "iso": "GR", "region": "Festland + Inseln",
     "lat": 38.0, "lon": 23.0, "season": "05-10", "severity": "low"},
    {"disease": "West-Nil-Virus", "slug": "west_nile",
     "country": "Griechenland", "iso": "GR", "region": "Nordgriechenland",
     "lat": 41.0, "lon": 23.0, "season": "07-10", "severity": "medium"},
    {"disease": "West-Nil-Virus", "slug": "west_nile",
     "country": "Italien", "iso": "IT", "region": "Po-Ebene/Norditalien",
     "lat": 45.0, "lon": 11.0, "season": "07-10", "severity": "medium"},
    {"disease": "Q-Fieber", "slug": "q_fieber",
     "country": "Spanien", "iso": "ES", "region": "Spanien (Nutztiere)",
     "lat": 40.0, "lon": -3.7, "season": "01-12", "severity": "low",
     "note": "Coxiella burnetii über Nutztiere/Staub"},
    {"disease": "Borreliose", "slug": "borreliose",
     "country": "Frankreich", "iso": "FR", "region": "Elsass/Lothringen/Alpen",
     "lat": 48.3, "lon": 7.4, "season": "04-10", "severity": "medium"},
    # ── Kanarische Inseln ─────────────────────────────────────────────────────
    {"disease": "Dengue", "slug": "dengue",
     "country": "Spanien", "iso": "ES", "region": "Kanarische Inseln",
     "lat": 28.1, "lon": -15.4, "season": "07-11", "severity": "medium",
     "note": "Aedes aegypti auf Kanaren seit 2017; lokale Übertragung dokumentiert"},
    {"disease": "Chikungunya", "slug": "chikungunya",
     "country": "Spanien", "iso": "ES", "region": "Kanarische Inseln",
     "lat": 28.1, "lon": -15.4, "season": "06-11", "severity": "low"},
    {"disease": "Murines Fleckfieber (Rickettsia typhi)", "slug": "fleckfieber_murin",
     "country": "Spanien", "iso": "ES", "region": "Kanarische Inseln",
     "lat": 28.1, "lon": -15.4, "season": "01-12", "severity": "medium",
     "note": "Hochinzidenzgebiet — mehr gemeldete Faelle als im uebrigen Spanien, "
             "Israel oder den USA; Seropraevalenz ~3,9% (IgG) in der Bevoelkerung, "
             "erhoeht in laendlichen Gebieten. Gilt dort als haeufige Ursache von "
             "'Fieber mittlerer Dauer' (7-28 Tage) ohne lokalisierenden Befund. "
             "Uebertraeger Ratten-/Katzenfloh (Bolanos-Rivero 2011, Ramos 2021)"},
    {"disease": "Angiostrongyliasis (Rattenlungenwurm)", "slug": "angiostrongyliasis",
     "country": "Spanien", "iso": "ES", "region": "Teneriffa",
     "lat": 28.29, "lon": -16.63, "season": "01-12", "severity": "low",
     "note": "Angiostrongylus cantonensis in Ratten und Schnecken auf Teneriffa "
             "nachgewiesen (Martin-Alonso 2015) — Reservoir/Zwischenwirt belegt, "
             "autochthone Humanfaelle dort bislang NICHT bestaetigt (gleiche "
             "Unterscheidung wie bei den Tigermuecken-Eintraegen: Vektor/Reservoir "
             "vorhanden heisst nicht dokumentierte Uebertragung)"},
    # ── Nordafrika / Ägypten ──────────────────────────────────────────────────
    {"disease": "Hepatitis A", "slug": "hepatitis_a",
     "country": "Ägypten", "iso": "EG", "region": "Gesamtägypten",
     "lat": 26.0, "lon": 30.0, "season": "01-12", "severity": "medium"},
    {"disease": "Brucellose", "slug": "brucellose",
     "country": "Ägypten", "iso": "EG", "region": "Ländliche Gebiete",
     "lat": 26.0, "lon": 30.0, "season": "01-12", "severity": "low"},
    {"disease": "Rickettsia", "slug": "rickettsia",
     "country": "Marokko", "iso": "MA", "region": "Mittelmeerküste",
     "lat": 34.0, "lon": -6.0, "season": "04-10", "severity": "low"},
    # ── Türkei ────────────────────────────────────────────────────────────────
    {"disease": "Krim-Kongo-Hämorrhagisches Fieber", "slug": "cchf",
     "country": "Türkei", "iso": "TR", "region": "Zentralanatolien",
     "lat": 39.0, "lon": 35.0, "season": "04-10", "severity": "high",
     "note": "Ixodes/Hyalomma-Zecken; Türkei weltweit höchste CCHF-Rate"},
    {"disease": "Brucellose", "slug": "brucellose",
     "country": "Türkei", "iso": "TR", "region": "Ländliche Gebiete",
     "lat": 39.0, "lon": 35.0, "season": "01-12", "severity": "medium"},
    {"disease": "Leishmaniose", "slug": "leishmaniose",
     "country": "Türkei", "iso": "TR", "region": "Südtürkei",
     "lat": 37.0, "lon": 36.0, "season": "05-10", "severity": "low"},
    # ── Südostasien ───────────────────────────────────────────────────────────
    {"disease": "Dengue", "slug": "dengue",
     "country": "Thailand", "iso": "TH", "region": "Gesamtthailand",
     "lat": 15.0, "lon": 101.0, "season": "06-10", "severity": "high"},
    {"disease": "Dengue", "slug": "dengue",
     "country": "Indonesien", "iso": "ID", "region": "Bali/Java/Sumatra",
     "lat": -8.4, "lon": 115.2, "season": "11-05", "severity": "high"},
    {"disease": "Dengue", "slug": "dengue",
     "country": "Vietnam", "iso": "VN", "region": "Gesamtvietnam",
     "lat": 16.0, "lon": 108.0, "season": "05-11", "severity": "high"},
    {"disease": "Chikungunya", "slug": "chikungunya",
     "country": "Indonesien", "iso": "ID", "region": "Gesamtindonesien",
     "lat": -8.4, "lon": 115.2, "season": "01-12", "severity": "medium"},
    {"disease": "Malaria", "slug": "malaria",
     "country": "Indonesien", "iso": "ID", "region": "Außer Bali/Java",
     "lat": -3.0, "lon": 120.0, "season": "01-12", "severity": "high"},
    {"disease": "Giardiasis", "slug": "giardiose",
     "country": "Thailand", "iso": "TH", "region": "Gesamtthailand",
     "lat": 15.0, "lon": 101.0, "season": "01-12", "severity": "medium"},
    # ── Lateinamerika ─────────────────────────────────────────────────────────
    {"disease": "Dengue", "slug": "dengue",
     "country": "Brasilien", "iso": "BR", "region": "Gesamtbrasilien",
     "lat": -15.0, "lon": -47.0, "season": "11-05", "severity": "high"},
    {"disease": "Chikungunya", "slug": "chikungunya",
     "country": "Brasilien", "iso": "BR", "region": "Küstenregionen",
     "lat": -15.0, "lon": -47.0, "season": "11-05", "severity": "high"},
    {"disease": "Giardiasis", "slug": "giardiose",
     "country": "Mexiko", "iso": "MX", "region": "Ländliche Gebiete",
     "lat": 23.0, "lon": -102.0, "season": "01-12", "severity": "medium"},
    # ── Feuchtgebiete / Vogelschutzgebiete Spanien ───────────────────────────
    {"disease": "West-Nil-Virus (WNV)", "slug": "west_nile",
     "country": "Spanien", "iso": "ES", "region": "S'Albufera Mallorca",
     "lat": 39.78, "lon": 3.1, "season": "07-10", "severity": "medium",
     "note": "Baleares WNV-Sentinel-Standort; Zugvögel + Culex pipiens in Schilfflächen"},
    {"disease": "Ornithose (Chlamydia psittaci)", "slug": "ornithose",
     "country": "Spanien", "iso": "ES", "region": "S'Albufera Mallorca",
     "lat": 39.78, "lon": 3.1, "season": "01-12", "severity": "medium",
     "note": "Großes Feuchtgebiet nördl. Can Picafort; Zugvögel als Reservoir; Aerosol-Exposition"},
    {"disease": "West-Nil-Virus (WNV)", "slug": "west_nile",
     "country": "Spanien", "iso": "ES", "region": "Delta de l'Ebre",
     "lat": 40.73, "lon": 0.82, "season": "06-10", "severity": "medium",
     "note": "Spanisches WNV-Hauptsurveillance-Gebiet (Tarragona/Katalonien); Flamingo-Kolonien"},
    {"disease": "Ornithose (Chlamydia psittaci)", "slug": "ornithose",
     "country": "Spanien", "iso": "ES", "region": "Delta de l'Ebre",
     "lat": 40.73, "lon": 0.82, "season": "01-12", "severity": "medium",
     "note": "Flamingo-Kolonien als C.-psittaci-Reservoir; Aerosol bei Wanderungen"},
    {"disease": "Leptospirose", "slug": "leptospirose",
     "country": "Spanien", "iso": "ES", "region": "Delta de l'Ebre",
     "lat": 40.73, "lon": 0.82, "season": "05-10", "severity": "medium",
     "note": "Feuchtgebiet-Exposition; Reisfelder + Flussarme + Rattenurin"},
    {"disease": "Tularämie (Francisella tularensis)", "slug": "tularaemie",
     "country": "Spanien", "iso": "ES", "region": "Delta de l'Ebre / Ebro-Tal",
     "lat": 40.73, "lon": 0.82, "season": "04-10", "severity": "medium",
     "note": "Spanien hat die höchste Tularämie-Inzidenz Westeuropas; Hasen, Nagetiere, Zecken, Aerosol"},
    # ── Osteuropa / Skandinavien ──────────────────────────────────────────────
    {"disease": "FSME", "slug": "fsme",
     "country": "Schweden", "iso": "SE", "region": "Küstengebiete",
     "lat": 59.0, "lon": 18.0, "season": "04-10", "severity": "medium"},
    {"disease": "FSME", "slug": "fsme",
     "country": "Tschechien", "iso": "CZ", "region": "Gesamttschechien",
     "lat": 50.0, "lon": 15.5, "season": "04-10", "severity": "medium"},
    # Polen: mehrfach unabhaengig als FSME-Risikogebiet genannt, mit
    # Schwerpunkt Nordostpolen/Woiwodschaft Podlachien (Podlaskie) --
    # bewusst NUR dieser eine, konsistent bestaetigte Punkt statt einer
    # unbestaetigten "5 Woiwodschaften"-Liste (Quelle dazu war beim
    # Nachpruefen nicht mehr erreichbar/nicht zuverlaessig reproduzierbar).
    {"disease": "FSME", "slug": "fsme",
     "country": "Polen", "iso": "PL", "region": "Podlachien (Podlaskie)",
     "lat": 53.13, "lon": 23.16, "radius_km": 100.0,
     "season": "04-10", "severity": "medium",
     "note": "Schwerpunkt Nordostpolen; landesweite Feinverteilung nicht verifiziert"},
    {"disease": "FSME", "slug": "fsme",
     "country": "Slowenien", "iso": "SI", "region": "Gesamtslowenien",
     "lat": 46.1, "lon": 14.8, "season": "04-10", "severity": "high",
     "note": "Höchste FSME-Inzidenz in Europa"},
    {"disease": "Lyme-Borreliose", "slug": "borreliose",
     "country": "Schweden", "iso": "SE", "region": "Gesamtschweden",
     "lat": 63.0, "lon": 16.0, "season": "04-10", "severity": "medium"},
    # ── Bulgarien / Schwarzmeerküste ──────────────────────────────────────────
    {"disease": "FSME", "slug": "fsme",
     "country": "Bulgarien", "iso": "BG", "region": "Gesamtbulgarien",
     "lat": 42.7, "lon": 25.5, "season": "04-10", "severity": "medium",
     "note": "Ixodes ricinus weit verbreitet; Risikogebiete v.a. Wälder/Hügel"},
    {"disease": "Lyme-Borreliose", "slug": "borreliose",
     "country": "Bulgarien", "iso": "BG", "region": "Gesamtbulgarien",
     "lat": 42.7, "lon": 25.5, "season": "04-10", "severity": "medium"},
    {"disease": "West-Nil-Virus", "slug": "west_nile",
     "country": "Bulgarien", "iso": "BG", "region": "Schwarzmeerküste / Donauebene",
     "lat": 43.2, "lon": 27.9, "season": "07-10", "severity": "medium",
     "note": "Bulgarien zählt zu den WNV-Endemiegebieten Osteuropas; Culex-Mücken"},
    {"disease": "Krim-Kongo-Hämorrhagisches Fieber (CCHF)", "slug": "cchf",
     "country": "Bulgarien", "iso": "BG", "region": "Südbulgarien/Thrakien",
     "lat": 42.0, "lon": 25.5, "season": "04-09", "severity": "high",
     "note": "Bulgarien hat eine der höchsten CCHF-Inzidenzen Europas; Hyalomma-Zecken"},
    {"disease": "Rickettsia conorii", "slug": "rickettsia",
     "country": "Bulgarien", "iso": "BG", "region": "Schwarzmeerküste / Südbulgarien",
     "lat": 42.5, "lon": 27.5, "season": "05-10", "severity": "medium"},
    {"disease": "Leishmaniose (kutan)", "slug": "leishmaniose",
     "country": "Bulgarien", "iso": "BG", "region": "Südbulgarien",
     "lat": 41.8, "lon": 25.0, "season": "06-10", "severity": "low",
     "note": "Phlebotomus-Sandmücken in südlichen Regionen"},
    # ── Norditalien (ergänzend zu Sizilien/Sardinien) ────────────────────────
    {"disease": "Lyme-Borreliose", "slug": "borreliose",
     "country": "Italien", "iso": "IT",
     "region": "Norditalien / Piemont / Lombardei / Alpenvorland",
     "lat": 45.5, "lon": 10.5, "season": "04-10", "severity": "medium",
     "note": "Lago Maggiore, Gardasee, Friaul — Ixodes ricinus Habitat"},
    {"disease": "FSME", "slug": "fsme",
     "country": "Italien", "iso": "IT",
     "region": "Norditalien / Piemont / Lombardei / Friaul",
     "lat": 46.0, "lon": 12.5, "season": "04-10", "severity": "medium",
     "note": "FSME-Foci v.a. Friaul-Julisch Venetien, Nordostalpen"},
    {"disease": "Rickettsia conorii", "slug": "rickettsia",
     "country": "Italien", "iso": "IT",
     "region": "Norditalien / Piemont / Lombardei",
     "lat": 45.5, "lon": 8.0, "season": "04-10", "severity": "medium"},
    # ── Bosnien-Herzegowina / Serbien ─────────────────────────────────────────
    {"disease": "FSME", "slug": "fsme",
     "country": "Bosnien-Herzegowina", "iso": "BA", "region": "Gesamtbosnien",
     "lat": 44.2, "lon": 17.9, "season": "04-10", "severity": "medium",
     "note": "Republika Srpska + Föd. BiH; Risikogebiete Hügelland/Wälder"},
    {"disease": "Lyme-Borreliose", "slug": "borreliose",
     "country": "Bosnien-Herzegowina", "iso": "BA", "region": "Gesamtbosnien",
     "lat": 44.2, "lon": 17.9, "season": "04-10", "severity": "medium"},
    {"disease": "Hantavirus (Puumala/Dobrava)", "slug": "hantavirus",
     "country": "Bosnien-Herzegowina", "iso": "BA", "region": "Gesamtbosnien",
     "lat": 44.2, "lon": 17.9, "season": "10-04", "severity": "medium",
     "note": "Apodemus-Mäuse als Reservoir; Herbst-/Winterpeak; v.a. Ländliche Gebiete"},
    {"disease": "FSME", "slug": "fsme",
     "country": "Serbien", "iso": "RS", "region": "Gesamtserbien",
     "lat": 44.0, "lon": 21.0, "season": "04-10", "severity": "medium"},
    {"disease": "Lyme-Borreliose", "slug": "borreliose",
     "country": "Serbien", "iso": "RS", "region": "Gesamtserbien",
     "lat": 44.0, "lon": 21.0, "season": "04-10", "severity": "medium"},
    {"disease": "West-Nil-Virus", "slug": "west_nile",
     "country": "Serbien", "iso": "RS", "region": "Vojvodina / Donauebene",
     "lat": 45.2, "lon": 19.8, "season": "07-10", "severity": "high",
     "note": "Serbien hat eine der höchsten WNV-Inzidenzen Europas (v.a. Vojvodina)"},
    {"disease": "Hantavirus (Puumala/Dobrava)", "slug": "hantavirus",
     "country": "Serbien", "iso": "RS", "region": "Gesamtserbien",
     "lat": 44.0, "lon": 21.0, "season": "10-04", "severity": "medium",
     "note": "Dobrava-HFRS (hämorrhagisches Fieber) — höheres Risiko als Puumala"},
    # ── Kroatien ──────────────────────────────────────────────────────────────
    {"disease": "FSME", "slug": "fsme",
     "country": "Kroatien", "iso": "HR", "region": "Gorski Kotar / Lika / Slawonien",
     "lat": 45.4, "lon": 15.5, "season": "04-10", "severity": "medium",
     "note": "Risikogebiete Kontinentalkroatien; Küste/Inseln geringes Risiko"},
    {"disease": "Lyme-Borreliose", "slug": "borreliose",
     "country": "Kroatien", "iso": "HR", "region": "Gesamtkroatien",
     "lat": 45.1, "lon": 15.2, "season": "04-10", "severity": "medium"},
    {"disease": "West-Nil-Virus", "slug": "west_nile",
     "country": "Kroatien", "iso": "HR", "region": "Slawonien / Donauebene",
     "lat": 45.5, "lon": 18.0, "season": "07-10", "severity": "medium"},
]

# ── Tigermücken-Landkreise Deutschland (Aedes albopictus) ────────────────────
# Quelle: Nat. Expertenkommission "Stechmücken als Überträger von
# Krankheitserregern" (FLI), Karte "Vorkommen der Asiatischen Tigermücke in
# Deutschland", Stand 31.12.2025.
# https://www.fli.de/de/kommissionen/nationale-expertenkommission-stechmuecken-als-uebertraeger-von-krankheitserregern/
# Für Bayern gilt vorrangig die feingranularere LGL-Bayern-Kartierung
# (BayMüMo 2024-2026, https://www.lgl.bayern.de/.../stechmuecken_monitoring_index.htm)
# statt der FLI-Karte — deshalb hier nur die außerbayerischen Landkreise der
# FLI-Karte sowie der eine bayerische Einzelpunkt (München), der auf beiden
# Karten übereinstimmend als vorhanden markiert ist.
# Aedes albopictus ist laut Nat. Expertenkommission Stechmücken/FLI (2022)
# effiziente Überträgerin von mindestens 20 Arboviren, darunter Dengue-,
# Zika- und Chikungunya-Virus — pro Landkreis daher je ein Eintrag für alle
# drei Krankheiten. Muss jährlich aktualisiert werden, sobald eine neue
# Kartenversion erscheint (Koordinaten sind Landkreis-Zentroide, keine
# Einzeladressen — für den 100-200km-Radius-Abgleich in
# analyse_outbreak_exposure.py/analyse_pathogen_exposure.py ausreichend
# präzise). "Eliminierte Population" (Stand 31.12.2025: Wiesbaden/Mainz)
# bewusst NICHT aufgenommen — dort ist die Mücke laut Karte nicht mehr
# vorhanden.
_TIGERMUECKE_ARBOVIREN = [("Dengue-Fieber", "dengue"), ("Chikungunya-Fieber", "chikungunya"), ("Zika-Virus", "zika")]

_TIGERMUECKE_LANDKREISE_ETABLIERT = [
    ("Rhein-Erft-Kreis", 50.90, 6.75), ("Köln", 50.94, 6.96), ("Bonn", 50.74, 7.10),
    ("Rheingau-Taunus-Kreis", 50.13, 8.00), ("Main-Taunus-Kreis", 50.13, 8.45),
    ("Hochtaunuskreis", 50.28, 8.50), ("Frankfurt am Main", 50.11, 8.68),
    ("Wetteraukreis", 50.35, 8.90), ("Main-Kinzig-Kreis", 50.15, 9.15),
    ("Groß-Gerau", 49.92, 8.48), ("Darmstadt", 49.87, 8.65), ("Bergstraße", 49.65, 8.63),
    ("Heidelberg", 49.40, 8.67), ("Rhein-Neckar-Kreis", 49.35, 8.70),
    ("Ludwigshafen", 49.47, 8.43), ("Mannheim", 49.49, 8.47), ("Rhein-Pfalz-Kreis", 49.35, 8.28),
    ("Speyer", 49.32, 8.43), ("Germersheim", 49.22, 8.37), ("Karlsruhe", 49.01, 8.40),
    ("Rastatt", 48.86, 8.20), ("Ortenaukreis", 48.47, 7.94), ("Emmendingen", 48.12, 7.85),
    ("Freiburg im Breisgau", 48.00, 7.84), ("Breisgau-Hochschwarzwald", 47.85, 7.90),
    ("Lörrach", 47.61, 7.66), ("Konstanz", 47.66, 9.18), ("Bodenseekreis", 47.75, 9.40),
    ("Stuttgart", 48.78, 9.18), ("Esslingen", 48.74, 9.31), ("Göppingen", 48.70, 9.65),
    ("Ludwigsburg", 48.90, 9.19), ("Rems-Murr-Kreis", 48.83, 9.42), ("Heilbronn", 49.14, 9.21),
    ("Saarbrücken", 49.24, 7.00), ("Berlin", 52.52, 13.41), ("Dresden", 51.05, 13.74),
    ("Jena", 50.93, 11.59),
    # München bewusst NICHT hier (FLI-Karte, national) — für Bayern gilt die
    # LGL-Karte vorrangig, München steht daher unten im Bayern-Block (LGL-Quelle)
]

_TIGERMUECKE_LANDKREISE_NEU: list[tuple[str, float, float]] = [
    # Alle bayerischen Punkte der FLI-Karte (Wunsiedel, Forchheim, Fürth,
    # Nürnberg, Würzburg) bewusst ENTFERNT und in den Bayern-Block unten
    # verschoben — für Bayern gilt die LGL-Karte vorrangig, zwei parallele
    # Quellen für dieselben Landkreise führten zu Duplikaten/Widersprüchen
    # (s. Würzburg-Korrektur).
]

# Radius-Override fuer landkreisgenaue Referenzpunkte: die Standard-Radien der
# Analyseskripte (GEO_RADIUS_KM_ENDEMIC=200 km bzw. degree-basierter Fallback in
# analyse_pathogen_exposure.py) sind fuer Laender-Zentroide gedacht (ein Punkt
# vertritt ein ganzes Land) und wuerden bei landkreisgenauen Punkten dazu
# fuehren, dass z.B. ein Aufenthalt in Berlin faelschlich gegen bayerische
# Landkreise matcht, oder Nachbar-Landkreise sich gegenseitig ueberdecken.
# ~20 km deckt die typische Ausdehnung eines Landkreises plus Sicherheitsspanne
# ab (vgl. aehnliches Prinzip bei modules/airport_proximity.py).
_TIGERMUECKE_LANDKREIS_RADIUS_KM = 20.0

# Konservative Floor-Datierung: der aktuelle Verbreitungsstand (FLI Stand
# 31.12.2025 / LGL Stand 18.12.2025) darf NICHT rueckwirkend auf beliebig
# alte Reisen/Wohnsitze angewandt werden — anders als z.B. FSME oder
# Malariazonen ist die Tigermuecke in Deutschland eine erst juengst (und
# weiter aktiv) expandierende Art. Fruehester belegter Einzelnachweis einer
# etablierten deutschen Population: Fuerth, Erstfund 2019 (LGL-Jahresbericht
# 2024). Fuer alle Landkreise pauschal auf 2019-01-01 gesetzt statt einer
# unbelegten Pro-Landkreis-Praezision (die meisten anderen Landkreise sind
# nachweislich erst 2023-2025 hinzugekommen — 2019 ist also die konservative,
# nie zu fruehe Untergrenze).
_TIGERMUECKE_LANDKREIS_SINCE = "2019-01-01"

for _name, _lat, _lon in _TIGERMUECKE_LANDKREISE_ETABLIERT:
    for _disease, _slug in _TIGERMUECKE_ARBOVIREN:
        ENDEMIC_REFERENCE.append({
            "disease": _disease, "slug": _slug, "country": "Deutschland", "iso": "DE",
            "region": _name, "lat": _lat, "lon": _lon, "season": "05-10", "severity": "low",
            "radius_km": _TIGERMUECKE_LANDKREIS_RADIUS_KM,
            "since": _TIGERMUECKE_LANDKREIS_SINCE,
            "note": "Tigermücke (Aedes albopictus), etablierte Population — "
                    "Vektor vorhanden, in Deutschland selbst bisher keine autochthone "
                    "Übertragung nachgewiesen (Nat. Expertenkommission Stechmücken/FLI, Stand 31.12.2025)",
        })
for _name, _lat, _lon in _TIGERMUECKE_LANDKREISE_NEU:
    for _disease, _slug in _TIGERMUECKE_ARBOVIREN:
        ENDEMIC_REFERENCE.append({
            "disease": _disease, "slug": _slug, "country": "Deutschland", "iso": "DE",
            "region": _name, "lat": _lat, "lon": _lon, "season": "05-10", "severity": "low",
            "radius_km": _TIGERMUECKE_LANDKREIS_RADIUS_KM,
            "since": _TIGERMUECKE_LANDKREIS_SINCE,
            "note": "Tigermücke (Aedes albopictus), neue/kleinere Population — "
                    "Vektor vorhanden, in Deutschland selbst bisher keine autochthone "
                    "Übertragung nachgewiesen (Nat. Expertenkommission Stechmücken/FLI, Stand 31.12.2025)",
        })

# Bayern: LGL-Bayern-Kartierung (BayMüMo 2024-2026) gilt vorrangig statt der
# FLI-Karte oben, da feingranularer. Quelle hat KEINE Landkreis-Beschriftung
# (nur eingefärbte Flächen ohne Text, per Alt-Text bestätigt) — Zuordnung per
# Lagevergleich mit der amtlichen Verwaltungskarte Bayern (Bayer. Landesamt
# für Statistik, "Kreisfreie Städte, Landkreise und Regierungsbezirke") und
# dem bekannten Aschaffenburg-WNV-Fund (2025). Für die südlichen/
# südöstlichen "Einzelfunde"-Flächen um München sind anhand von Lage/Form
# mehrere Landkreise als plausibel identifiziert (Miesbach, Rosenheim,
# Bad Tölz-Wolfratshausen) — welcher Landkreis exakt zu welcher Farbabstufung
# gehört, ist aus der unbeschrifteten Quelle nicht zweifelsfrei bestimmbar,
# aber alle drei liegen korrekt in der betroffenen Region (für den
# 100-200km-Radius-Abgleich ausreichend, auch ohne exakte Shape-Zuordnung).
# https://www.lgl.bayern.de/gesundheit/umweltbezogener_gesundheitsschutz/klimawandel_gesundheit/infektionskrankheiten/stechmuecken_monitoring_index.htm
_TIGERMUECKE_BAYERN_LGL_NOTE = (
    "Tigermücke (Aedes albopictus), Bayern — Vektor vorhanden, in Deutschland "
    "selbst bisher keine autochthone Übertragung nachgewiesen (LGL Bayern, "
    "BayMüMo, Stand 18.12.2025)"
)
_TIGERMUECKE_BAYERN_ETABLIERT = [
    ("Aschaffenburg", 49.98, 9.15),   # kreisfreie Stadt, dunkelblau, deckt sich mit WNV-Erstfall 2025
    ("Würzburg", 49.79, 9.93),        # kreisfreie Stadt, dunkelblau
    ("München", 48.14, 11.58),        # kreisfreie Stadt, dunkelblau
    # Fürth: per unbeschrifteter LGL-Karte nicht von benachbartem Einzelfund-
    # Gebiet zu unterscheiden, aber im LGL-Jahresbericht 2024 (jb24, Abb. 1,
    # Stand 25.02.2025, explizit beschriftet "SK Fürth") als "Population"
    # (= etabliert) bestätigt — überschreibt die visuelle Einordnung.
    ("Fürth", 49.48, 10.99),
]
_TIGERMUECKE_BAYERN_EINZELFUNDE = [
    ("Landkreis Aschaffenburg", 49.90, 9.30),
    ("Kitzingen", 49.74, 10.16),  # hellblau/Einzelfunde, nicht Landkreis Würzburg
    ("Forchheim/Nürnberg-Gebiet", 49.55, 11.05),  # Fürth s.o. nach Etabliert verschoben
    ("Wunsiedel i.Fichtelgebirge", 50.03, 12.00),  # aus FLI-Karte übernommen, in Bayern-Block
                                                    # konsolidiert; offizieller Name (RKI-Stil,
                                                    # s. FSME_RISIKOKREISE_BAYERN oben)
    ("Landkreis München", 48.05, 11.70),
    ("Rosenheim", 47.86, 12.13),  # Korrektur: Einzelfunde, nicht etabliert
    ("Landkreis Rosenheim", 47.90, 12.05),
    ("Miesbach", 47.79, 11.83),
    ("Bad Tölz-Wolfratshausen", 47.76, 11.56),
    ("Regensburg", 49.02, 12.10),
    ("Landkreis Regensburg", 49.05, 12.05),
    ("Memmingen", 47.99, 10.18),  # kreisfreie Stadt, Schwaben, hellblau/Einzelfunde
]
for _name, _lat, _lon in _TIGERMUECKE_BAYERN_ETABLIERT:
    for _disease, _slug in _TIGERMUECKE_ARBOVIREN:
        ENDEMIC_REFERENCE.append({
            "disease": _disease, "slug": _slug, "country": "Deutschland", "iso": "DE",
            "region": _name, "lat": _lat, "lon": _lon, "season": "05-10", "severity": "low",
            "radius_km": _TIGERMUECKE_LANDKREIS_RADIUS_KM,
            "since": _TIGERMUECKE_LANDKREIS_SINCE,
            "note": _TIGERMUECKE_BAYERN_LGL_NOTE + " — etablierte Population",
        })
for _name, _lat, _lon in _TIGERMUECKE_BAYERN_EINZELFUNDE:
    for _disease, _slug in _TIGERMUECKE_ARBOVIREN:
        ENDEMIC_REFERENCE.append({
            "disease": _disease, "slug": _slug, "country": "Deutschland", "iso": "DE",
            "region": _name, "lat": _lat, "lon": _lon, "season": "05-10", "severity": "low",
            "radius_km": _TIGERMUECKE_LANDKREIS_RADIUS_KM,
            "since": _TIGERMUECKE_LANDKREIS_SINCE,
            "note": _TIGERMUECKE_BAYERN_LGL_NOTE + " — Einzelfunde",
        })


# ── HTTP-Hilfsfunktion ─────────────────────────────────────────────────────────

def _fetch_url(url: str, timeout: int = 15) -> str | None:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Kyoro-HealthHub/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(t(f"  Fetch-Fehler {url}: {e}", f"  Fetch error {url}: {e}"))
        return None


def _parse_rss_date(s: str) -> str:
    """Parst RFC 2822 oder ISO-Datumsstring → YYYY-MM-DD."""
    try:
        return parsedate_to_datetime(s).strftime("%Y-%m-%d")
    except Exception:
        pass
    # Versuche ISO
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(s[:19], fmt[:len(s[:19])]).strftime("%Y-%m-%d")
        except Exception:
            pass
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


# ── Quellen-Fetcher ───────────────────────────────────────────────────────────

def fetch_who_don(conn: sqlite3.Connection) -> int:
    """WHO Disease Outbreak News → outbreak_events via JSON REST API.

    Die WHO hat nach dem Website-Redesign 2023 keine öffentlichen RSS-Feeds mehr
    für DON bereitgestellt. Stattdessen wird die offizielle JSON REST API genutzt.
    Doku: https://www.who.int/api/news/diseaseoutbreaknews/sfhelp
    """
    api_url = (
        "https://www.who.int/api/news/diseaseoutbreaknews"
        "?$top=50&$orderby=PublicationDate+desc"
    )
    text = _fetch_url(api_url)
    if not text:
        print(t("  WHO DON: JSON-API nicht erreichbar",
                "  WHO DON: JSON API not reachable"))
        return 0

    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        print(t(f"  WHO DON: JSON-Fehler — {e}", f"  WHO DON: JSON error — {e}"))
        return 0

    # OData-Format {"value": [...]} oder direkte Liste
    items = data if isinstance(data, list) else data.get("value", [])
    if not items:
        print(t("  WHO DON: API liefert keine Einträge",
                "  WHO DON: API returned no items"))
        return 0

    now = datetime.now(timezone.utc).isoformat()
    inserted = 0

    for item in items:
        title = (item.get("Title") or item.get("OverrideTitle") or "").strip()
        if not title:
            continue

        pub_raw = (item.get("PublicationDate") or
                   item.get("PublicationDateAndTime") or "")
        date_reported = pub_raw[:10] if pub_raw else \
                        datetime.now(timezone.utc).strftime("%Y-%m-%d")

        url_name = item.get("UrlName", "")
        url = (f"https://www.who.int/emergencies/disease-outbreak-news/item/{url_name}"
               if url_name else "https://www.who.int/emergencies/disease-outbreak-news")

        parts = re.split(r"\s[–—-]\s", title, maxsplit=1)
        disease = parts[0].strip() if parts else title
        country = parts[1].strip() if len(parts) > 1 else ""
        if "multiple" in country.lower() or "several" in country.lower():
            country = ""

        iso  = _iso_from_country(country) if country else None
        slug = _slug_from_disease(disease)

        try:
            conn.execute("""
                INSERT OR IGNORE INTO outbreak_events
                (source, disease, syndrome_slug, country, country_iso,
                 date_reported, severity, url, title, fetched_at, person)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """, ("who_don", disease, slug, country or None, iso,
                  date_reported, "medium", url, title, now, _OWN_PERSON_ID))
            if conn.execute("SELECT changes()").fetchone()[0]:
                inserted += 1
        except DB_ERRORS as e:
            print(t(f"  DB-Fehler: {e}", f"  DB error: {e}"))

    conn.commit()
    return inserted


def fetch_ecdc(conn: sqlite3.Connection) -> int:
    """ECDC Epidemiologische Updates + Risk Assessments → outbreak_events.

    ECDC nutzt Drupal-Taxonomy-Feeds (Stand 2026, von ecdc.europa.eu/en/rss-feeds).
    Mehrere thematische Feeds werden zusammengeführt.
    """
    # Priorisiert nach Ausbruchsrelevanz: Updates > Risk > CDTR > News
    candidates = [
        "https://www.ecdc.europa.eu/en/taxonomy/term/1310/feed",  # Epidemiological updates
        "https://www.ecdc.europa.eu/en/taxonomy/term/1295/feed",  # Risk assessments
        "https://www.ecdc.europa.eu/en/taxonomy/term/1505/feed",  # Communicable disease threats
        "https://www.ecdc.europa.eu/en/taxonomy/term/1307/feed",  # News/press releases
    ]
    xml = None
    url = ""
    for u in candidates:
        xml = _fetch_url(u)
        if xml and "<item>" in xml:
            url = u
            break
    if not xml:
        print(t("  ECDC: kein RSS-Feed erreichbar",
                "  ECDC: no RSS feed reachable"))
        return 0
    print(f"  ECDC: {url}")

    try:
        root = ET.fromstring(xml)
    except ET.ParseError as e:
        print(t(f"  XML-Fehler: {e}", f"  XML error: {e}"))
        return 0

    now = datetime.now(timezone.utc).isoformat()
    inserted = 0
    threat_keywords = {
        "threat", "outbreak", "alert", "warning", "risk", "surveillance",
        "ausbruch", "bedrohung", "warnung",
    }

    for item in root.iter("item"):
        title    = (item.findtext("title") or "").strip()
        link     = (item.findtext("link") or "").strip()
        pub_date = (item.findtext("pubDate") or "").strip()

        # Nur Gesundheitsbedrohungen/Ausbrüche
        title_lower = title.lower()
        if not any(k in title_lower for k in threat_keywords):
            continue

        date_reported = _parse_rss_date(pub_date) if pub_date else \
                        datetime.now(timezone.utc).strftime("%Y-%m-%d")

        # Disease aus Titel extrahieren
        disease = title
        slug    = _slug_from_disease(title)

        try:
            conn.execute("""
                INSERT OR IGNORE INTO outbreak_events
                (source, disease, syndrome_slug, date_reported, severity, url, title, fetched_at,
                 person)
                VALUES (?,?,?,?,?,?,?,?,?)
            """, ("ecdc", disease, slug, date_reported, "medium", link, title, now,
                  _OWN_PERSON_ID))
            if conn.execute("SELECT changes()").fetchone()[0]:
                inserted += 1
        except DB_ERRORS as e:
            print(t(f"  DB-Fehler: {e}", f"  DB error: {e}"))

    conn.commit()
    return inserted


def fetch_efsa(conn: sqlite3.Connection) -> int:
    """EFSA (Europäische Behörde für Lebensmittelsicherheit) Updates → outbreak_events.

    EFSA veröffentlicht regelmäßig Berichte zu Zoonosen und lebensmittelbedingten
    Ausbrüchen (u.a. Vogelgrippe-Lageberichte) — thematisch komplementär zu
    WAHIS (Tierseuchen), aber tatsächlich per RSS erreichbar, anders als das
    Cloudflare-geschützte WAHIS. Live per curl verifiziert (30 aktuelle
    Eintraege, u.a. tagesaktueller Vogelgrippe-Lagebericht).
    """
    url = "https://www.efsa.europa.eu/en/all/rss"
    xml = _fetch_url(url)
    if not xml or "<item>" not in xml:
        print(t("  EFSA: kein RSS-Feed erreichbar", "  EFSA: no RSS feed reachable"))
        return 0

    try:
        root = ET.fromstring(xml)
    except ET.ParseError as e:
        print(t(f"  XML-Fehler: {e}", f"  XML error: {e}"))
        return 0

    now = datetime.now(timezone.utc).isoformat()
    inserted = 0
    threat_keywords = {
        "outbreak", "avian influenza", "zoono", "disease", "virus", "risk",
        "surveillance", "alert", "ausbruch", "vogelgrippe", "seuche",
    }

    for item in root.iter("item"):
        title    = (item.findtext("title") or "").strip()
        link     = (item.findtext("link") or "").strip()
        pub_date = (item.findtext("pubDate") or "").strip()

        title_lower = title.lower()
        if not any(k in title_lower for k in threat_keywords):
            continue

        date_reported = _parse_rss_date(pub_date) if pub_date else \
                        datetime.now(timezone.utc).strftime("%Y-%m-%d")
        disease = title
        slug    = _slug_from_disease(title)

        try:
            conn.execute("""
                INSERT OR IGNORE INTO outbreak_events
                (source, disease, syndrome_slug, date_reported, severity, url, title, fetched_at,
                 person)
                VALUES (?,?,?,?,?,?,?,?,?)
            """, ("efsa", disease, slug, date_reported, "medium", link, title, now,
                  _OWN_PERSON_ID))
            if conn.execute("SELECT changes()").fetchone()[0]:
                inserted += 1
        except DB_ERRORS as e:
            print(t(f"  DB-Fehler: {e}", f"  DB error: {e}"))

    conn.commit()
    return inserted


def fetch_gdelt(conn: sqlite3.Connection) -> int:
    """GDELT DOC 2.0 API (globale Nachrichten-Ereignisdatenbank) → outbreak_events.

    Ersatz fuer das per Cloudflare/403 blockierte HealthMap: GDELT ist eine
    offene, kostenlose, oeffentlich dokumentierte API (api.gdeltproject.org),
    kein Auth-Token noetig. Live per curl verifiziert -- allerdings mit
    strengem Rate-Limit (429 "Please limit requests to one every 5 seconds"
    wurde in Tests auch nach 20s Pause noch ausgeloest, das tatsaechliche
    Fenster ist also grosszuegiger als dokumentiert). Deshalb bewusst nur EIN
    Versuch pro Lauf, kein Retry-Loop -- ein 429 gilt als "diesmal nicht",
    nicht als Fehler, und wird beim naechsten taeglichen Lauf automatisch neu
    versucht.
    """
    query = '("disease outbreak" OR "tick-borne encephalitis" OR chikungunya OR dengue)'
    url = (
        "https://api.gdeltproject.org/api/v2/doc/doc"
        f"?query={urllib.parse.quote(query)}"
        "&mode=artlist&maxrecords=20&format=json&timespan=2d&sourcelang=english"
    )
    raw = _fetch_url(url, timeout=20)
    if not raw:
        print(t("  GDELT: nicht erreichbar", "  GDELT: not reachable"))
        return 0
    if raw.lstrip().startswith("Please limit requests") or not raw.lstrip().startswith("{"):
        print(t(f"  GDELT: uebersprungen ({raw[:80]!r})",
                f"  GDELT: skipped ({raw[:80]!r})"))
        return 0

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        print(t(f"  GDELT: JSON-Fehler: {e}", f"  GDELT: JSON error: {e}"))
        return 0

    now = datetime.now(timezone.utc).isoformat()
    inserted = 0
    for art in data.get("articles", []):
        title = (art.get("title") or "").strip()
        link  = (art.get("url") or "").strip()
        if not title or not link:
            continue
        seen = art.get("seendate", "")  # Format: YYYYMMDDTHHMMSSZ
        try:
            date_reported = datetime.strptime(seen[:8], "%Y%m%d").strftime("%Y-%m-%d")
        except ValueError:
            date_reported = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        slug = _slug_from_disease(title)

        try:
            conn.execute("""
                INSERT OR IGNORE INTO outbreak_events
                (source, disease, syndrome_slug, date_reported, severity, url, title, fetched_at,
                 person)
                VALUES (?,?,?,?,?,?,?,?,?)
            """, ("gdelt", title, slug, date_reported, "low", link, title, now,
                  _OWN_PERSON_ID))
            if conn.execute("SELECT changes()").fetchone()[0]:
                inserted += 1
        except DB_ERRORS as e:
            print(t(f"  DB-Fehler: {e}", f"  DB error: {e}"))

    conn.commit()
    return inserted


def fetch_promedmail(conn: sqlite3.Connection) -> int:
    """ProMED RSS-Feed → outbreak_events.

    ANDERS als die anderen in dieser Datei reparierten Quellen: dies ist KEIN
    technisches Problem (verschobene URL, veralteter Endpunkt), sondern eine
    ABSICHTLICHE Entscheidung des Betreibers (ISID) -- am 14.07.2023 wurden
    RSS-/Twitter-Feeds bewusst abgeschaltet und ein Login-Abo-Modell
    eingefuehrt, ausdruecklich um Scraping zu verhindern (Quelle: mehrere
    unabhaengige Presseberichte, s. STAT News/Lancet Microbe Berichterstattung
    August 2023). Deshalb bewusst NICHT per Netzwerk-Traffic-Mitschnitt nach
    einem oeffentlichen Ersatz-Endpunkt gesucht, wie bei CRM/HealthMap/WAHIS:
    ein absichtliches Zugriffshindernis ist etwas anderes als eine kaputte
    URL, und sollte respektiert statt umgangen werden.
    """
    candidates = [
        "https://promedmail.org/feed/",
        "https://promedmail.org/promed-post/?feed=rss2",
        "https://www.promedmail.org/feed/",
    ]
    xml = None
    url = ""
    for u in candidates:
        xml = _fetch_url(u)
        if xml and "<item>" in xml:
            url = u
            break
    if not xml:
        print(t("  ProMED: kein RSS erreichbar", "  ProMED: no RSS reachable"))
        return 0
    print(f"  ProMED: {url}")
    xml = _fetch_url(url)
    if not xml:
        return 0

    try:
        root = ET.fromstring(xml)
    except ET.ParseError as e:
        print(t(f"  XML-Fehler: {e}", f"  XML error: {e}"))
        return 0

    now = datetime.now(timezone.utc).isoformat()
    inserted = 0

    for item in root.iter("item"):
        title    = (item.findtext("title") or "").strip()
        link     = (item.findtext("link") or "").strip()
        pub_date = (item.findtext("pubDate") or "").strip()

        date_reported = _parse_rss_date(pub_date) if pub_date else \
                        datetime.now(timezone.utc).strftime("%Y-%m-%d")

        # ProMED-Format: "PRO/AH/EDR> Disease - Country: ..."
        clean_title = re.sub(r"^PRO/[A-Z/]+>\s*", "", title)
        parts = re.split(r"\s*-\s*", clean_title, maxsplit=2)
        disease = parts[0].strip() if parts else clean_title
        country = parts[1].strip() if len(parts) > 1 else ""
        if "multiple" in country.lower():
            country = ""

        iso  = _iso_from_country(country) if country else None
        slug = _slug_from_disease(disease)

        try:
            conn.execute("""
                INSERT OR IGNORE INTO outbreak_events
                (source, disease, syndrome_slug, country, country_iso,
                 date_reported, severity, url, title, fetched_at, person)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """, ("promedmail", disease, slug, country or None, iso,
                  date_reported, "low", link, clean_title, now, _OWN_PERSON_ID))
            if conn.execute("SELECT changes()").fetchone()[0]:
                inserted += 1
        except DB_ERRORS as e:
            print(t(f"  DB-Fehler: {e}", f"  DB error: {e}"))

    conn.commit()
    return inserted


def import_endemic_reference(conn: sqlite3.Connection) -> int:
    """Statische Endemie-Referenzdaten einmalig importieren."""
    now = datetime.now(timezone.utc).isoformat()
    inserted = 0

    for ref in ENDEMIC_REFERENCE:
        # Saisonale Zeiträume als date_start/date_end (aktuelles Jahr)
        year = datetime.now().year
        season = ref.get("season", "01-12").split("-")
        date_start = f"{year}-{season[0]}-01" if len(season) == 2 else f"{year}-01-01"
        date_end   = None  # endemisch = kein Ende

        title = f"{ref['disease']} (endemisch) — {ref.get('region', ref['country'])}"

        try:
            conn.execute("""
                INSERT OR IGNORE INTO outbreak_events
                (source, disease, syndrome_slug, country, country_iso,
                 region, lat, lon, date_reported, date_start, date_end,
                 severity, title, fetched_at, person, radius_km, note, since_date)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, ("endemic_ref", ref["disease"], ref.get("slug"),
                  ref["country"], ref["iso"],
                  ref.get("region"), ref.get("lat"), ref.get("lon"),
                  date_start, date_start, date_end,
                  ref.get("severity", "low"), title, now, _OWN_PERSON_ID,
                  ref.get("radius_km"), ref.get("note"), ref.get("since")))
            if conn.execute("SELECT changes()").fetchone()[0]:
                inserted += 1
        except DB_ERRORS as e:
            print(t(f"  DB-Fehler: {e}", f"  DB error: {e}"))

    conn.commit()
    return inserted


# ── RKI SurvStat ──────────────────────────────────────────────────────────────
# Meldepflichtige Erkrankungen Deutschland/Bundesland via OLAP/MDX-SOAP-API
# Doku: https://tools.rki.de/SurvStat/SurvStatWebService.svc?wsdl
#
# RKI hat die alte SurvStat-Schnittstelle (SOAP 1.1, Operation GetResultRowData,
# Namespace tempuri.org) komplett durch ein OLAP/MDX-Modell ersetzt — die alte
# Operation existiert serverseitig nicht mehr. Verifiziert durch
# Auswertung des live WSDL + der importierten XSDs (xsd0: Operationshüllen,
# xsd2: Mdx-Contracttypen). Wichtigste Unterschiede zum alten (nie
# funktionierenden) Code:
#  - SOAP 1.2 (nicht 1.1) UND ein WS-Addressing-Header (wsa:Action) sind
#    zwingend erforderlich — ohne Header schlägt jede Anfrage mit einem
#    "ActionMismatch"-Fault fehl, ein falscher Action-Namespace (z.B. das alte
#    tempuri.org) ebenso.
#  - Reale Action-Basis ist http://tools.rki.de/SurvStat/SurvStatWebService/*,
#    nicht http://tempuri.org/*.
#  - Statt einer Einzelwert-Abfrage (GetResultRowData) liefert die neue API
#    Kreuztabellen: GetOlapData(RowHierarchy, ColumnHierarchy, HierarchyFilters,
#    Measures) — hier Meldewoche × Meldejahr, gefiltert auf eine Krankheit und
#    optional ein Bundesland. Ein einzelner Aufruf liefert dabei gleich die
#    GESAMTE in SurvStat verfügbare Historie (für Borreliose z.B. 2001–heute),
#    keine Jahresschleife nötig.
#  - Hierarchie-/Mitglieds-IDs (z.B. welcher String für "Borreliose" oder
#    "Bayern" steht) sind keine freien Klartexte, sondern über
#    GetAllHierarchyMembers abgefragte, stabile MDX-Member-IDs.

RKI_DISEASES = {
    # Anzeigename (wird in Titel/DB-Feld "disease" geschrieben) →
    # (Caption in SurvStat-Hierarchie "Krankheit / Erreger", syndrome_slug).
    # Caption-Strings live gegen GetAllHierarchyMembers verifiziert —
    # weichen an einigen Stellen von der Alltagsbezeichnung ab (z.B.
    # "Denguefieber" statt "Dengue-Fieber", "Ornithose" statt "Psittakose").
    "FSME (Frühsommer-Meningoenzephalitis)": ("FSME (Frühsommer-Meningoenzephalitis)", "fsme"),
    "Q-Fieber":                              ("Q-Fieber", "q_fieber"),
    "Ornithose (Psittakose)":                ("Ornithose", "ornithose"),
    "Yersiniose":                            ("Yersiniose", "yersiniose"),
    "Dengue-Fieber":                         ("Denguefieber", "dengue"),
    "Chikungunya-Fieber":                    ("Chikungunya-Fieber", "chikungunya"),
    "West-Nil-Virus-Erkrankung":             ("West-Nil-Virus", "west_nile"),
    "Tularämie":                             ("Tularämie", "tularaemie"),
    "Brucellose":                            ("Brucellose", "brucellose"),
    "Leptospirose":                          ("Leptospirose", "leptospirose"),
    "Borreliose":                            ("Borreliose", "borreliose"),
    "Influenza (saisonal)":                  ("Influenza, saisonal", "influenza"),
    # Humane granulozytäre Anaplasmose (HGA) und Rickettsiose sind in dieser
    # Cube-Version keine eigene Meldekategorie (nicht bundesweit meldepflichtig
    # nach IfSG) — kein SurvStat-Signal verfügbar, daher hier absichtlich nicht
    # gelistet statt eine Erkrankung stillschweigend auf 0 Fälle zu setzen.
}

# ASCII-Schreibweise wie in geo_bundesland.py / den anderen RKI-GitHub-Quellen
# (ARE-Konsultationsinzidenz) — SurvStat selbst verwendet Umlaute in seinen
# Klartext-Captions, aber die stabilen Member-IDs referenzieren nur den
# 2-stelligen FedStateKey71-Code, sodass die Umlaut-Schreibweise dafür gar
# nicht gebraucht wird. Codes live gegen GetAllHierarchyMembers
# verifiziert.
RKI_BUNDESLAENDER = {
    "Schleswig-Holstein":      "01",
    "Hamburg":                 "02",
    "Niedersachsen":           "03",
    "Bremen":                  "04",
    "Nordrhein-Westfalen":     "05",
    "Hessen":                  "06",
    "Rheinland-Pfalz":         "07",
    "Baden-Wuerttemberg":      "08",
    "Bayern":                  "09",
    "Saarland":                "10",
    "Berlin":                  "11",
    "Brandenburg":             "12",
    "Mecklenburg-Vorpommern":  "13",
    "Sachsen":                 "14",
    "Sachsen-Anhalt":          "15",
    "Thueringen":              "16",
}

_RKI_SOAP_ENDPOINT = "https://tools.rki.de/SurvStat/SurvStatWebService.svc"
_RKI_ELEMENT_NS = "http://tools.rki.de/SurvStat/"
_RKI_ACTION_BASE = "http://tools.rki.de/SurvStat/SurvStatWebService"
_RKI_MDX_NS = "http://schemas.datacontract.org/2004/07/Rki.SurvStat.WebService.Contracts.Mdx"

_RKI_DIM_KRANKHEIT = "[PathogenOut].[KategorieNz]"
_RKI_HIER_KRANKHEIT = "[PathogenOut].[KategorieNz].[Krankheit DE]"
_RKI_DIM_BUNDESLAND = "[DeutschlandNodes].[Kreise71Web]"
_RKI_HIER_BUNDESLAND = "[DeutschlandNodes].[Kreise71Web].[FedStateKey71]"
_RKI_HIER_WEEK = "[ReportingDate].[Week].[Week]"
_RKI_HIER_WEEKYEAR = "[ReportingDate].[WeekYear].[WeekYear]"


def _rki_soap_call(operation: str, request_body: str, timeout: int = 30) -> ET.Element | None:
    """SOAP-1.2-Anfrage mit WS-Addressing-Header an SurvStat senden.

    Liefert das <s:Body>-Element der Antwort, oder None bei Netzwerkfehler
    bzw. SOAP-Fault (wird geloggt).
    """
    action = f"{_RKI_ACTION_BASE}/{operation}"
    envelope = (
        '<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope" '
        'xmlns:a="http://www.w3.org/2005/08/addressing">'
        '<s:Header>'
        f'<a:Action s:mustUnderstand="1">{action}</a:Action>'
        f'<a:To s:mustUnderstand="1">{_RKI_SOAP_ENDPOINT}</a:To>'
        '</s:Header>'
        f'<s:Body><{operation} xmlns="{_RKI_ELEMENT_NS}">{request_body}</{operation}></s:Body>'
        '</s:Envelope>'
    )
    try:
        req = urllib.request.Request(
            _RKI_SOAP_ENDPOINT,
            data=envelope.encode("utf-8"),
            headers={
                "Content-Type": f'application/soap+xml; charset=utf-8; action="{action}"',
                "User-Agent": "Kyoro-HealthHub/1.0",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as r:
            xml_text = r.read().decode("utf-8", errors="replace")
        root = ET.fromstring(xml_text)
        body = root.find("{http://www.w3.org/2003/05/soap-envelope}Body")
        fault = body.find("{http://www.w3.org/2003/05/soap-envelope}Fault") if body is not None else None
        if fault is not None:
            reason = fault.findtext(
                ".//{http://www.w3.org/2003/05/soap-envelope}Text", default="?")
            print(t(f"    RKI SurvStat SOAP-Fault ({operation}): {reason}",
                    f"    RKI SurvStat SOAP fault ({operation}): {reason}"))
            return None
        return body
    except Exception as e:
        print(t(f"    RKI SurvStat Fehler ({operation}): {e}",
                f"    RKI SurvStat error ({operation}): {e}"))
        return None


def _rki_filter_entry(dimension_id: str, hierarchy_id: str, member_id: str) -> str:
    return (
        '<q1:KeyValueOfFilterCollectionKeyFilterMemberCollectionb2rWaiIW>'
        f'<q1:Key><q1:DimensionId>{escape(dimension_id)}</q1:DimensionId>'
        f'<q1:HierarchyId>{escape(hierarchy_id)}</q1:HierarchyId></q1:Key>'
        f'<q1:Value><q1:string>{escape(member_id)}</q1:string></q1:Value>'
        '</q1:KeyValueOfFilterCollectionKeyFilterMemberCollectionb2rWaiIW>'
    )


def _rki_olap_data_request(disease_caption: str, bundesland_code: str | None) -> str:
    """<request>-Body für GetOlapData: eine Krankheit, optional ein Bundesland,
    Kreuztabelle Meldewoche × Meldejahr, Maß = Fallzahl."""
    filters = _rki_filter_entry(
        _RKI_DIM_KRANKHEIT, _RKI_HIER_KRANKHEIT,
        f"{_RKI_HIER_KRANKHEIT}.&[{disease_caption}]")
    if bundesland_code:
        filters += _rki_filter_entry(
            _RKI_DIM_BUNDESLAND, _RKI_HIER_BUNDESLAND,
            f"{_RKI_HIER_BUNDESLAND}.&[{bundesland_code}]")
    return (
        f'<request xmlns:q1="{_RKI_MDX_NS}" xmlns:i="http://www.w3.org/2001/XMLSchema-instance">'
        f'<q1:ColumnHierarchy>{_RKI_HIER_WEEKYEAR}</q1:ColumnHierarchy>'
        '<q1:Cube>SurvStat</q1:Cube>'
        '<q1:DataStatus i:nil="true"/>'
        f'<q1:HierarchyFilters>{filters}</q1:HierarchyFilters>'
        '<q1:IncludeNullColumns>false</q1:IncludeNullColumns>'
        '<q1:IncludeNullRows>false</q1:IncludeNullRows>'
        '<q1:IncludeTotalColumn>false</q1:IncludeTotalColumn>'
        '<q1:IncludeTotalRow>false</q1:IncludeTotalRow>'
        '<q1:Language>German</q1:Language>'
        '<q1:Measures>Count</q1:Measures>'
        f'<q1:RowHierarchy>{_RKI_HIER_WEEK}</q1:RowHierarchy>'
        '</request>'
    )


def _rki_parse_olap_grid(body: ET.Element) -> dict[tuple[int, int], int]:
    """GetOlapDataResponse → {(Meldejahr, Meldewoche): Fallzahl} für Zellen > 0."""
    ns = {"b": _RKI_MDX_NS}
    result = body.find(f".//{{{_RKI_ELEMENT_NS}}}GetOlapDataResult")
    if result is None:
        return {}
    years: list[int | None] = []
    for col in result.findall(".//b:QueryResultColumn", ns):
        cap = col.findtext("b:Caption", default="", namespaces=ns)
        years.append(int(cap) if cap.isdigit() else None)
    grid: dict[tuple[int, int], int] = {}
    for row in result.findall(".//b:QueryResultRow", ns):
        week_cap = row.findtext("b:Caption", default="", namespaces=ns)
        if not week_cap.isdigit():
            continue
        week = int(week_cap)
        values = row.find("b:Values", ns)
        if values is None:
            continue
        for year, val in zip(years, values.findall("b:string", ns)):
            if year is None or val.text is None or not val.text.strip().lstrip("-").isdigit():
                continue
            count = int(val.text)
            if count > 0:
                grid[(year, week)] = count
    return grid


def fetch_rki_survstat(conn: sqlite3.Connection,
                       bundeslaender: list[str] | None = None,
                       weeks_back: int = 52) -> int:
    """RKI SurvStat (OLAP/MDX-API) → outbreak_events: wöchentliche Fallzahlen
    meldepflichtiger Erkrankungen, bundesweit + alle 16 Bundesländer.

    bundeslaender=None: alle 16 Bundesländer werden abgefragt (kein
    hartkodiertes Bundesland). Nicht jede Krankheit ist in jedem Bundesland
    meldepflichtig — Borreliose z.B. nur über einzelne Landesmeldeverordnungen
    statt bundesweit nach IfSG, mit sehr unterschiedlichem Start (Brandenburg/
    Sachsen-Anhalt seit 2001, Bayern erst seit 2016, Baden-Württemberg/Hessen/
    NRW u.a. gar nicht) — verifiziert gegen die Live-API. Für nicht
    meldepflichtige Kombinationen liefert GetOlapData einfach keine Spalten,
    das wird hier nicht gesondert behandelt und ergibt schlicht 0 Einträge für
    diese Kombination, statt sie stillschweigend auf 0 Fälle zu setzen.

    Pro Krankheit+Region liefert die API die GESAMTE verfügbare Historie in
    einem Aufruf; standardmäßig wird das Ergebnis lokal auf die letzten
    `weeks_back` Wochen gekürzt (Default: ein rollierendes Jahr, wie
    GrippeWeb/ARE-Konsultationsinzidenz), voller Backfill via
    weeks_back=100_000 (--full-history).
    """
    if bundeslaender is None:
        bundeslaender = list(RKI_BUNDESLAENDER)

    regions: list[tuple[str, str | None]] = [("Deutschland", None)]
    for name in bundeslaender:
        code = RKI_BUNDESLAENDER.get(name)
        if code:
            regions.append((name, code))
        else:
            print(t(f"    RKI SurvStat: unbekanntes Bundesland '{name}', übersprungen",
                    f"    RKI SurvStat: unknown federal state '{name}', skipped"))

    cutoff_year, cutoff_week, _ = (date.today() - timedelta(weeks=weeks_back)).isocalendar()
    now = datetime.now(timezone.utc).isoformat()
    inserted = 0

    for region_label, bl_code in regions:
        for disease_display, (disease_caption, slug) in RKI_DISEASES.items():
            time.sleep(0.3)
            body = _rki_soap_call("GetOlapData", _rki_olap_data_request(disease_caption, bl_code))
            if body is None:
                continue
            grid = _rki_parse_olap_grid(body)

            for (year, week), count in grid.items():
                if (year, week) < (cutoff_year, cutoff_week):
                    continue
                try:
                    date_start = date.fromisocalendar(year, week, 1).isoformat()
                except ValueError:
                    continue
                severity = "low" if count < 10 else "medium" if count < 50 else "high"
                title = (f"{disease_display} (RKI SurvStat {year}-W{week:02d}) — "
                        f"{region_label}: {count} Fälle")
                try:
                    conn.execute("""
                        INSERT OR IGNORE INTO outbreak_events
                        (source, disease, syndrome_slug, country, country_iso,
                         region, date_reported, date_start,
                         severity, title, fetched_at, person)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                    """, ("rki_survstat", disease_display, slug,
                          "Deutschland", "DE", region_label,
                          date_start, date_start, severity, title, now, _OWN_PERSON_ID))
                    if conn.execute("SELECT changes()").fetchone()[0]:
                        inserted += 1
                except DB_ERRORS as e:
                    print(t(f"    DB-Fehler: {e}", f"    DB error: {e}"))

    conn.commit()
    print(t(f"    RKI SurvStat: {inserted} neue Einträge",
            f"    RKI SurvStat: {inserted} new entries"))
    return inserted


# ── RKI GrippeWeb ─────────────────────────────────────────────────────────────
# Bevölkerungsbasierte, wöchentliche ARE-/ILI-Inzidenzschätzungen aus
# freiwilligen Selbstauskünften (citizen-reported, nicht meldepflichtig) —
# ergänzt SurvStat (meldepflichtige Einzeldiagnosen) um ein Hintergrundsignal
# für grippeähnliche Aktivität in der Bevölkerung, z.B. um einen Symptom-Crash
# gegen "war da gerade eine ARE/ILI-Welle in der Region" einzuordnen.
# Datensatz: https://github.com/robert-koch-institut/GrippeWeb_Daten_des_Wochenberichts
# CC-BY 4.0, wöchentlich freitags aktualisiert.

_GRIPPEWEB_TSV_URL = (
    "https://raw.githubusercontent.com/robert-koch-institut/"
    "GrippeWeb_Daten_des_Wochenberichts/main/GrippeWeb_Daten_des_Wochenberichts.tsv"
)

# ILI ("Influenza-like Illness") ist Influenza-spezifisch genug für den
# bestehenden "influenza"-Slug (s. RKI_DISEASES oben); ARE ist unspezifischer
# akuter Atemwegsinfekt ohne eigenen Slug -> "generic", gleiches Muster wie
# West-Nil-Virus-Erkrankung/Leptospirose in RKI_DISEASES.
_GRIPPEWEB_SLUGS = {"ARE": "generic", "ILI": "influenza"}

# GrippeWeb-Regionen sind grobe Sammelregionen (kein Bundesland-Level) —
# ungefährer Mittelpunkt je Region für die outbreak_events-Koordinatenspalten.
_GRIPPEWEB_REGION_COORDS = {
    "Bundesweit":    (51.0, 10.0),
    "Norden (West)": (53.3,  9.0),
    "Mitte (West)":  (50.3,  8.5),
    "Sueden":        (48.5, 11.3),
    "Osten":         (51.3, 12.4),
}


def _fetch_grippeweb_tsv() -> str | None:
    """Rohtext-Download der GrippeWeb-Wochenbericht-TSV von GitHub."""
    try:
        req = urllib.request.Request(
            _GRIPPEWEB_TSV_URL, headers={"User-Agent": "Kyoro-HealthHub/1.0"}
        )
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(t(f"    GrippeWeb Fehler: {e}", f"    GrippeWeb error: {e}"))
        return None


def fetch_grippeweb(conn: sqlite3.Connection, weeks_back: int = 52) -> int:
    """RKI GrippeWeb TSV → outbreak_events (bevölkerungsbasierte ARE-/ILI-Inzidenz).

    Importiert nur die letzten `weeks_back` Kalenderwochen je Region/Erkrankung
    (nicht die komplette Historie seit Saison 2010/11, ~19000 Zeilen) — ein
    rollierendes Fenster reicht für den Zweck (aktueller Hintergrundkontext),
    ältere Wochen ändern sich ohnehin nicht mehr. INSERT OR IGNORE macht
    wiederholte Läufe idempotent, bereits vorhandene Wochen werden übersprungen.
    """
    tsv = _fetch_grippeweb_tsv()
    if not tsv:
        return 0

    lines = tsv.strip().split("\n")
    if len(lines) < 2:
        return 0
    header = lines[0].split("\t")
    idx = {name: i for i, name in enumerate(header)}
    required = ("Kalenderwoche", "Altersgruppe", "Region", "Erkrankung", "Inzidenz")
    if not all(name in idx for name in required):
        print(t("    GrippeWeb: unerwartetes TSV-Format, übersprungen",
                "    GrippeWeb: unexpected TSV format, skipped"))
        return 0

    rows = [line.split("\t") for line in lines[1:] if line.strip()]
    weeks_present = sorted({r[idx["Kalenderwoche"]] for r in rows if len(r) > idx["Kalenderwoche"]})
    recent_weeks = set(weeks_present[-weeks_back:])

    now = datetime.now(timezone.utc).isoformat()
    inserted = 0
    for r in rows:
        if len(r) <= max(idx.values()):
            continue
        week = r[idx["Kalenderwoche"]]
        if week not in recent_weeks:
            continue
        # Nur Gesamtbevölkerung, keine Alterskohorten-Einzelwerte — das Signal
        # ist "gab es eine Welle", keine altersspezifische Analyse.
        if r[idx["Altersgruppe"]] != "00+":
            continue

        region   = r[idx["Region"]]
        disease  = r[idx["Erkrankung"]]
        try:
            incidence = float(r[idx["Inzidenz"]])
        except ValueError:
            continue

        slug = _GRIPPEWEB_SLUGS.get(disease, "generic")
        lat, lon = _GRIPPEWEB_REGION_COORDS.get(region, (51.0, 10.0))
        severity = "low" if incidence < 500 else "medium" if incidence < 2000 else "high"
        try:
            # ISO-Kalenderwoche ("2026-W28") -> Wochenmontag als Datum
            date_start = datetime.strptime(f"{week}-1", "%G-W%V-%u").strftime("%Y-%m-%d")
        except ValueError:
            date_start = now[:10]
        title = f"{disease} (RKI GrippeWeb {week}) — {region}: {incidence:.0f}/100.000"

        try:
            conn.execute("""
                INSERT OR IGNORE INTO outbreak_events
                (source, disease, syndrome_slug, country, country_iso,
                 region, lat, lon, date_reported, date_start,
                 severity, title, fetched_at, person)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, ("rki_grippeweb", disease, slug,
                  "Deutschland", "DE", region,
                  lat, lon, date_start, date_start, severity, title, now, _OWN_PERSON_ID))
            if conn.execute("SELECT changes()").fetchone()[0]:
                inserted += 1
        except DB_ERRORS as e:
            print(t(f"    DB-Fehler: {e}", f"    DB error: {e}"))

    conn.commit()
    print(t(f"    RKI GrippeWeb: {inserted} neue Einträge",
            f"    RKI GrippeWeb: {inserted} new entries"))
    return inserted


# ── RKI ARE-Konsultationsinzidenz (AGI-Sentinel) ─────────────────────────────
# Wie GrippeWeb, aber aus echten Arztkonsultationen im AGI-Sentinelpraxen-
# Netzwerk statt Bürger-Selbstauskunft — UND pro Bundesland statt nur den
# groben GrippeWeb-Sammelregionen, also z.B. Bayern-spezifisch verfügbar.
# Datensatz: https://github.com/robert-koch-institut/ARE-Konsultationsinzidenz
# CC-BY 4.0, wöchentlich aktualisiert.

_ARE_KONSULTATION_TSV_URL = (
    "https://raw.githubusercontent.com/robert-koch-institut/"
    "ARE-Konsultationsinzidenz/main/ARE-Konsultationsinzidenz.tsv"
)

# Ungefähre Landeshauptstadt-Koordinaten je Bundesland (gleiche Rolle wie
# _GRIPPEWEB_REGION_COORDS oben, nur feinere Auflösung).
_BUNDESLAND_COORDS = {
    "Bundesweit":           (51.0,  10.0),
    "Baden-Wuerttemberg":   (48.78,  9.18),
    "Bayern":               (48.14, 11.58),
    "Berlin":               (52.52, 13.40),
    "Brandenburg":          (52.40, 13.06),
    "Bremen":               (53.08,  8.80),
    "Hamburg":              (53.55, 10.00),
    "Hessen":               (50.08,  8.24),
    "Mecklenburg-Vorpommern": (53.63, 11.41),
    "Niedersachsen":        (52.37,  9.73),
    "Nordrhein-Westfalen":  (51.23,  6.77),
    "Rheinland-Pfalz":      (49.99,  8.27),
    "Saarland":             (49.24,  6.99),
    "Sachsen":              (51.05, 13.74),
    "Sachsen-Anhalt":       (52.13, 11.64),
    "Schleswig-Holstein":   (54.32, 10.14),
    "Thueringen":           (50.98, 11.03),
}


def _fetch_are_konsultationsinzidenz_tsv() -> str | None:
    """Rohtext-Download der ARE-Konsultationsinzidenz-TSV von GitHub."""
    try:
        req = urllib.request.Request(
            _ARE_KONSULTATION_TSV_URL, headers={"User-Agent": "Kyoro-HealthHub/1.0"}
        )
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(t(f"    ARE-Konsultationsinzidenz Fehler: {e}",
                f"    ARE consultation incidence error: {e}"))
        return None


def fetch_are_konsultationsinzidenz(conn: sqlite3.Connection, weeks_back: int = 52) -> int:
    """RKI ARE-Konsultationsinzidenz TSV → outbreak_events (pro Bundesland).

    Gleiches rollierendes-Fenster-Prinzip wie fetch_grippeweb (s. dort) —
    keine komplette Historie seit Saison 2012/13 bei jedem normalen Lauf.
    """
    tsv = _fetch_are_konsultationsinzidenz_tsv()
    if not tsv:
        return 0

    lines = tsv.strip().split("\n")
    if len(lines) < 2:
        return 0
    header = lines[0].split("\t")
    idx = {name: i for i, name in enumerate(header)}
    required = ("Kalenderwoche", "Altersgruppe", "Bundesland", "ARE_Konsultationsinzidenz")
    if not all(name in idx for name in required):
        print(t("    ARE-Konsultationsinzidenz: unerwartetes TSV-Format, übersprungen",
                "    ARE consultation incidence: unexpected TSV format, skipped"))
        return 0

    rows = [line.split("\t") for line in lines[1:] if line.strip()]
    weeks_present = sorted({r[idx["Kalenderwoche"]] for r in rows if len(r) > idx["Kalenderwoche"]})
    recent_weeks = set(weeks_present[-weeks_back:])

    now = datetime.now(timezone.utc).isoformat()
    inserted = 0
    for r in rows:
        if len(r) <= max(idx.values()):
            continue
        week = r[idx["Kalenderwoche"]]
        if week not in recent_weeks:
            continue
        if r[idx["Altersgruppe"]] != "00+":
            continue

        region = r[idx["Bundesland"]]
        try:
            incidence = float(r[idx["ARE_Konsultationsinzidenz"]])
        except ValueError:
            continue

        lat, lon = _BUNDESLAND_COORDS.get(region, (51.0, 10.0))
        severity = "low" if incidence < 500 else "medium" if incidence < 2000 else "high"
        try:
            date_start = datetime.strptime(f"{week}-1", "%G-W%V-%u").strftime("%Y-%m-%d")
        except ValueError:
            date_start = now[:10]
        title = f"ARE (RKI Konsultationsinzidenz {week}) — {region}: {incidence:.0f}/100.000"

        try:
            conn.execute("""
                INSERT OR IGNORE INTO outbreak_events
                (source, disease, syndrome_slug, country, country_iso,
                 region, lat, lon, date_reported, date_start,
                 severity, title, fetched_at, person)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, ("rki_are_konsultationsinzidenz", "ARE", "generic",
                  "Deutschland", "DE", region,
                  lat, lon, date_start, date_start, severity, title, now, _OWN_PERSON_ID))
            if conn.execute("SELECT changes()").fetchone()[0]:
                inserted += 1
        except DB_ERRORS as e:
            print(t(f"    DB-Fehler: {e}", f"    DB error: {e}"))

    conn.commit()
    print(t(f"    ARE-Konsultationsinzidenz: {inserted} neue Einträge",
            f"    ARE consultation incidence: {inserted} new entries"))
    return inserted


# ── LGL Bayern / RKI FSME-Risikogebiete ──────────────────────────────────────

# FSME-Risikokreise Bayern (95 von 96 Kreisen; einzig SK Schweinfurt ist kein
# Risikogebiet). Quelle: RKI Epid. Bull. 9/2026, "FSME: Risikogebiete in
# Deutschland" (Stand 15.1.2026), Tab. 1, doi:10.25646/13864.2 — ersetzt eine
# deutlich unvollstaendigere Vorversion (67 statt 95 Kreise; u.a. fehlten
# separate Stadt/Landkreis-Eintraege wie SK Fürth, SK Hof, SK Landshut,
# SK Nürnberg, SK Passau, SK Regensburg, SK Rosenheim, SK Würzburg, die im
# aktuellen Stand alle EIGENSTAENDIGE Risikogebiete neben ihrem jeweiligen
# Landkreis sind).
# Landkreis-genaue Koordinaten (Kreisstadt/Verwaltungssitz als Referenzpunkt,
# ~10-20km Genauigkeit -- dieselbe Praezisionsklasse wie die Tigermuecken-
# Landkreise). Ersetzt einen einzelnen bayernweiten Punkt, der jeden
# bayerischen Aufenthalt gegen alle 95 Kreise gleichzeitig hatte matchen
# lassen (gefunden beim Testlauf gegen die echte Wohnsitz-/Reise-Historie).
FSME_RISIKOKREISE_BAYERN: list[tuple[str, float, float]] = [
    ("Aichach-Friedberg", 48.46, 11.13), ("Altötting", 48.23, 12.68),
    ("Amberg (Stadt)", 49.44, 11.85), ("Amberg-Sulzbach", 49.50, 11.75),
    ("Ansbach (Stadt)", 49.30, 10.57), ("Ansbach (Landkreis)", 49.35, 10.65),
    ("Aschaffenburg (Stadt)", 49.98, 9.15),
    ("Aschaffenburg (Landkreis)", 49.90, 9.30),
    ("Augsburg (Landkreis)", 48.40, 10.85), ("Augsburg (Stadt)", 48.37, 10.90),
    ("Bad Kissingen", 50.20, 10.08), ("Bad Tölz-Wolfratshausen", 47.76, 11.56),
    ("Bamberg (Stadt)", 49.89, 10.89), ("Bamberg (Landkreis)", 49.95, 10.95),
    ("Bayreuth (Stadt)", 49.95, 11.58), ("Bayreuth (Landkreis)", 49.95, 11.70),
    ("Berchtesgadener Land", 47.73, 12.88), ("Cham", 49.22, 12.66),
    ("Coburg (Stadt)", 50.26, 10.96), ("Coburg (Landkreis)", 50.25, 11.05),
    ("Dachau", 48.26, 11.43), ("Deggendorf", 48.83, 12.96),
    ("Dillingen a.d. Donau", 48.57, 10.49), ("Dingolfing-Landau", 48.64, 12.50),
    ("Donau-Ries", 48.72, 10.77), ("Ebersberg", 48.08, 11.97),
    ("Eichstätt", 48.89, 11.19), ("Erding", 48.31, 11.91),
    ("Erlangen (Stadt)", 49.60, 11.00), ("Erlangen-Höchstadt", 49.72, 10.80),
    ("Forchheim", 49.72, 11.06), ("Freising", 48.40, 11.75),
    ("Freyung-Grafenau", 48.81, 13.55), ("Fürstenfeldbruck", 48.18, 11.26),
    ("Fürth (Stadt)", 49.48, 10.99), ("Fürth (Landkreis)", 49.45, 10.90),
    ("Garmisch-Partenkirchen", 47.49, 11.10), ("Günzburg", 48.45, 10.28),
    ("Haßberge", 50.03, 10.51), ("Hof (Stadt)", 50.31, 11.92),
    ("Hof (Landkreis)", 50.25, 11.85), ("Ingolstadt", 48.76, 11.43),
    ("Kaufbeuren (Stadt)", 47.88, 10.62), ("Kelheim", 48.92, 11.87),
    ("Kempten (Stadt)", 47.73, 10.32), ("Kitzingen", 49.74, 10.16),
    ("Kronach", 50.24, 11.33), ("Kulmbach", 50.10, 11.45),
    ("Landsberg am Lech", 48.05, 10.88), ("Landshut (Stadt)", 48.54, 12.15),
    ("Landshut (Landkreis)", 48.55, 12.10), ("Lichtenfels", 50.15, 11.06),
    ("Lindau", 47.55, 9.68), ("Main-Spessart", 49.96, 9.77),
    ("Memmingen (Stadt)", 47.99, 10.18), ("Miesbach", 47.79, 11.83),
    ("Miltenberg", 49.71, 9.26), ("Mühldorf a. Inn", 48.25, 12.52),
    ("München (Landkreis)", 48.05, 11.70), ("München (Stadt)", 48.14, 11.58),
    ("Neuburg-Schrobenhausen", 48.73, 11.18), ("Neumarkt i.d. OPf.", 49.28, 11.46),
    ("Neustadt a.d. Waldnaab", 49.73, 12.18),
    ("Neustadt/Aisch-Bad Windsheim", 49.57, 10.61), ("Neu-Ulm", 48.39, 10.00),
    ("Nürnberg (Stadt)", 49.45, 11.08), ("Nürnberger Land", 49.51, 11.28),
    ("Oberallgäu", 47.52, 10.28), ("Ostallgäu", 47.78, 10.61),
    ("Passau (Stadt)", 48.57, 13.43), ("Passau (Landkreis)", 48.60, 13.30),
    ("Pfaffenhofen a.d. Ilm", 48.53, 11.52), ("Regen", 49.01, 13.13),
    ("Regensburg (Stadt)", 49.02, 12.10), ("Regensburg (Landkreis)", 49.05, 12.05),
    ("Rhön-Grabfeld", 50.32, 10.22), ("Rosenheim (Stadt)", 47.86, 12.13),
    ("Rosenheim (Landkreis)", 47.90, 12.05), ("Roth", 49.25, 11.09),
    ("Rottal-Inn", 48.43, 12.94), ("Schwabach (Stadt)", 49.33, 11.02),
    ("Schwandorf", 49.33, 12.11), ("Schweinfurt (Landkreis)", 50.00, 10.30),
    ("Starnberg", 47.99, 11.34), ("Straubing (Stadt)", 48.88, 12.57),
    ("Straubing-Bogen", 48.91, 12.69), ("Tirschenreuth", 49.88, 12.33),
    ("Traunstein", 47.87, 12.64), ("Unterallgäu", 48.04, 10.49),
    ("Weiden i.d. OPf. (Stadt)", 49.68, 12.16), ("Weilheim-Schongau", 47.84, 11.15),
    ("Weißenburg-Gunzenhausen", 49.03, 10.97),
    ("Wunsiedel i.Fichtelgebirge", 50.03, 12.00),
    ("Würzburg (Stadt)", 49.79, 9.93), ("Würzburg (Landkreis)", 49.85, 9.95),
]

# Weitere FSME-Risikogebiete ausserhalb Bayerns (RKI Epid. Bull. 9/2026,
# "FSME: Risikogebiete in Deutschland", Stand 15.1.2026, Tab. 1) — Bayern und
# Baden-Württemberg tragen zusammen den Grossteil der bundesweit 185
# Risikokreise, aber FSME ist explizit KEIN rein bayerisches/sueddeutsches
# Risiko mehr: einzelne Kreise auch in Mittelhessen, im Saarland und in
# Rheinland-Pfalz, und die noerdliche Ausbreitung nach Niedersachsen,
# Nordrhein-Westfalen, Sachsen-Anhalt und Brandenburg nimmt laut RKI seit
# 2019-2022 zu.
# Koordinaten = Kreisstadt/Verwaltungssitz, dieselbe Praezisionsklasse wie
# Bayern oben (~10-25km). Fuer die hier weniger vertrauten Regionen (v.a.
# Sachsen, Thueringen, Brandenburg) mit etwas groesserer Unsicherheit als bei
# Bayern behaftet -- daher radius_km=25 statt 20 in fetch_lgl_fsme() unten.
FSME_RISIKOKREISE_BADEN_WUERTTEMBERG: list[tuple[str, float, float]] = [
    ("Alb-Donau-Kreis", 48.30, 9.85), ("Baden-Baden (Stadt)", 48.76, 8.24),
    ("Biberach", 48.10, 9.79), ("Böblingen", 48.68, 9.01),
    ("Bodenseekreis", 47.65, 9.48), ("Breisgau-Hochschwarzwald", 47.90, 8.15),
    ("Calw", 48.72, 8.74), ("Emmendingen", 48.12, 7.85),
    ("Enzkreis", 48.89, 8.70), ("Esslingen", 48.74, 9.31),
    ("Freiburg i. Breisgau (Stadt)", 48.00, 7.84), ("Freudenstadt", 48.47, 8.41),
    ("Göppingen", 48.70, 9.65), ("Heidelberg (Stadt)", 49.41, 8.69),
    ("Heidenheim", 48.68, 10.15), ("Heilbronn (Landkreis)", 49.10, 9.30),
    ("Hohenlohekreis", 49.28, 9.68), ("Karlsruhe (Stadt)", 49.01, 8.40),
    ("Karlsruhe (Landkreis)", 49.05, 8.55), ("Konstanz", 47.66, 9.18),
    ("Lörrach", 47.61, 7.66), ("Ludwigsburg", 48.90, 9.19),
    ("Main-Tauber-Kreis", 49.62, 9.66), ("Mannheim (Stadt)", 49.49, 8.47),
    ("Neckar-Odenwald-Kreis", 49.35, 9.15), ("Ortenaukreis", 48.47, 7.94),
    ("Ostalbkreis", 48.84, 10.09), ("Pforzheim (Stadt)", 48.89, 8.70),
    ("Rastatt", 48.86, 8.20), ("Ravensburg", 47.78, 9.61),
    ("Rems-Murr-Kreis", 48.83, 9.42), ("Reutlingen", 48.49, 9.21),
    ("Rhein-Neckar-Kreis", 49.35, 8.75), ("Rottweil", 48.17, 8.63),
    ("Schwäbisch Hall", 49.11, 9.74), ("Schwarzwald-Baar-Kreis", 48.06, 8.46),
    ("Sigmaringen", 48.09, 9.22), ("Stuttgart (Stadt)", 48.78, 9.18),
    ("Tübingen", 48.52, 9.06), ("Tuttlingen", 47.98, 8.82),
    ("Ulm (Stadt)", 48.40, 9.99), ("Waldshut", 47.62, 8.21),
    ("Zollernalbkreis", 48.27, 8.85),
]
FSME_RISIKOKREISE_HESSEN: list[tuple[str, float, float]] = [
    ("Bergstraße", 49.64, 8.64), ("Darmstadt (Stadt)", 49.87, 8.65),
    ("Darmstadt-Dieburg", 49.90, 8.85), ("Fulda", 50.55, 9.68),
    ("Groß-Gerau", 49.92, 8.48), ("Main-Kinzig-Kreis", 50.20, 9.19),
    ("Marburg-Biedenkopf", 50.81, 8.77), ("Odenwaldkreis", 49.67, 8.99),
    ("Offenbach (Stadt)", 50.10, 8.76), ("Offenbach (Landkreis)", 50.01, 8.77),
]
FSME_RISIKOKREISE_THUERINGEN: list[tuple[str, float, float]] = [
    ("Altenburger Land", 50.99, 12.44), ("Gera (Stadt)", 50.88, 12.08),
    ("Greiz", 50.66, 12.20), ("Hildburghausen", 50.43, 10.73),
    ("Ilm-Kreis", 50.84, 10.95), ("Jena (Stadt)", 50.93, 11.59),
    ("Saale-Holzland-Kreis", 50.97, 11.90), ("Saale-Orla-Kreis", 50.58, 11.82),
    ("Saalfeld-Rudolstadt", 50.65, 11.37), ("Schmalkalden-Meiningen", 50.57, 10.41),
    ("Sonneberg", 50.36, 11.17), ("Suhl (Stadt)", 50.61, 10.69),
    ("Weimarer Land", 51.02, 11.51),
]
FSME_RISIKOKREISE_SACHSEN: list[tuple[str, float, float]] = [
    ("Bautzen", 51.18, 14.43), ("Chemnitz (Stadt)", 50.83, 12.92),
    ("Dresden (Stadt)", 51.05, 13.74), ("Erzgebirgskreis", 50.58, 13.00),
    ("Görlitz", 51.15, 14.99), ("Meißen", 51.16, 13.47),
    ("Mittelsachsen", 50.91, 13.34), ("Nordsachsen", 51.56, 12.94),
    ("Sächsische Schweiz-Osterzgebirge", 50.96, 13.94),
    ("Vogtlandkreis", 50.49, 12.14), ("Zwickau", 50.72, 12.49),
]
FSME_RISIKOKREISE_BRANDENBURG: list[tuple[str, float, float]] = [
    ("Elbe-Elster", 51.68, 13.23), ("Frankfurt (Oder) (Stadt)", 52.35, 14.55),
    ("Oberspreewald-Lausitz", 51.52, 14.00), ("Oder-Spree", 52.17, 14.24),
    ("Spree-Neiße", 51.74, 14.63),
]
FSME_RISIKOKREISE_SACHSEN_ANHALT: list[tuple[str, float, float]] = [
    ("Anhalt-Bitterfeld", 51.75, 11.97), ("Dessau-Roßlau (Stadt)", 51.83, 12.24),
    ("Halle (Saale) (Stadt)", 51.48, 11.97),
]
FSME_RISIKOKREISE_NIEDERSACHSEN: list[tuple[str, float, float]] = [
    ("Celle", 52.62, 10.08), ("Emsland", 52.69, 7.29),
]
FSME_RISIKOKREISE_NORDRHEIN_WESTFALEN: list[tuple[str, float, float]] = [
    ("Solingen (Stadt)", 51.17, 7.08),
]
FSME_RISIKOKREISE_RHEINLAND_PFALZ: list[tuple[str, float, float]] = [
    ("Birkenfeld", 49.65, 7.17),
]
FSME_RISIKOKREISE_SAARLAND: list[tuple[str, float, float]] = [
    ("Saarpfalz-Kreis", 49.32, 7.34),
]

# Bundesland -> Liste (Kreis, lat, lon). Alle 185 Kreise bundesweit haben jetzt
# Landkreis-genaue Koordinaten (kein gemeinsamer Punkt pro Bundesland mehr) --
# ein einzelner Punkt pro Land hatte Aufenthalte faelschlich ueber
# Landesgrenzen hinweg matchen lassen (z.B. Bayern-Wohnsitz traf faelschlich
# alle 43 Baden-Wuerttemberg-Kreise, gefunden beim Testlauf gegen echte
# Wohnsitz-Historie).
FSME_RISIKOKREISE_BUNDESWEIT: dict[str, list[tuple[str, float, float]]] = {
    "Bayern": FSME_RISIKOKREISE_BAYERN,
    "Baden-Württemberg":   FSME_RISIKOKREISE_BADEN_WUERTTEMBERG,
    "Hessen":              FSME_RISIKOKREISE_HESSEN,
    "Thüringen":           FSME_RISIKOKREISE_THUERINGEN,
    "Sachsen":             FSME_RISIKOKREISE_SACHSEN,
    "Brandenburg":         FSME_RISIKOKREISE_BRANDENBURG,
    "Sachsen-Anhalt":      FSME_RISIKOKREISE_SACHSEN_ANHALT,
    "Niedersachsen":       FSME_RISIKOKREISE_NIEDERSACHSEN,
    "Nordrhein-Westfalen": FSME_RISIKOKREISE_NORDRHEIN_WESTFALEN,
    "Rheinland-Pfalz":     FSME_RISIKOKREISE_RHEINLAND_PFALZ,
    "Saarland":            FSME_RISIKOKREISE_SAARLAND,
}


def fetch_lgl_fsme(conn: sqlite3.Connection) -> int:
    """RKI FSME-Risikogebiete (bundesweit) → outbreak_events.

    Versucht zuerst die RKI-Webseite zu scrapen; fällt auf die eingebettete,
    nach Bundesland strukturierte Risikokreis-Liste zurück wenn kein
    Netzwerkzugriff besteht (FSME_RISIKOKREISE_BUNDESWEIT oben) — deckt ganz
    Deutschland ab, nicht nur Bayern (frueher Bug: der Fallback kannte nur
    Bayern und beschriftete auch gescrapte, tatsaechlich anderswo liegende
    Kreise pauschal als "Bayern").
    """
    now = datetime.now(timezone.utc).isoformat()
    inserted = 0
    year = datetime.now().year

    # Versuche RKI-Seite zu laden für aktuellste Liste. RKI hat die Site-Struktur
    # von /DE/Content/... auf /DE/Themen/... umgestellt (die alten Content-URLs
    # sind seit mind. 2026 tot, gefunden per echtem curl-Test) -- die jaehrliche
    # Risikogebiets-Tabelle selbst steckt in einem PDF (Epid. Bull., i.d.R.
    # Ausgabe 9, Ende Februar) und ist nicht zuverlaessig aus HTML scrapebar;
    # die Themenseite dient hier nur als Existenz-/Aenderungssignal.
    rki_url = "https://www.rki.de/DE/Themen/Infektionskrankheiten/Infektionskrankheiten-A-Z/F/FSME/fsme-node.html"
    html = _fetch_url(rki_url)

    # Fallback URLs
    if not html:
        for fallback_url in [
            "https://www.rki.de/DE/Themen/Infektionskrankheiten/Infektionskrankheiten-A-Z/F/FSME/FSME.html",
        ]:
            html = _fetch_url(fallback_url)
            if html:
                rki_url = fallback_url
                break

    # (Bundesland, Kreis, lat, lon) — Bundesland bei gescrapten Treffern
    # unbekannt (RKI-Seite listet sie ohne Bundesland-Zuordnung im HTML),
    # daher generischer Deutschland-Punkt statt der frueheren Bayern-Annahme.
    entries: list[tuple[str, str, float, float]] = []
    if html:
        # Einfaches HTML-Scraping: Kreise stehen als Listenelemente
        kreise_matches = re.findall(
            r"<li[^>]*>([A-Za-zÄÖÜäöüß\s\-\.()]+(?:Landkreis|Stadt|a\.d\.|i\.d\.)?[^<]*)</li>",
            html
        )
        rki_kreise = [k.strip() for k in kreise_matches if len(k.strip()) > 4][:200]
        entries = [("Deutschland", kreis, 51.0, 10.0) for kreis in rki_kreise]

    if not entries:
        for bundesland, kreise in FSME_RISIKOKREISE_BUNDESWEIT.items():
            entries.extend((bundesland, kreis, lat, lon) for kreis, lat, lon in kreise)

    for bundesland, kreis, lat, lon in entries:
        title = f"FSME-Risikogebiet {bundesland}: {kreis} ({year})"
        # idx_outbreak_url ist UNIQUE auf (source, COALESCE(url, title||date_reported)) --
        # dieselbe rki_url fuer alle Kreise wuerde sie unter derselben Quelle als
        # Duplikate erscheinen lassen und "INSERT OR IGNORE" liesse nur den ersten
        # Kreis durch (realer Bug, gefunden beim Testlauf gegen die echte DB: vor
        # diesem Fix wurde bei jedem fetch_lgl_fsme()-Fallback-Lauf nur 1 Zeile
        # eingefuegt, unabhaengig von der Anzahl der Kreise). Fragment pro Kreis
        # macht die URL eindeutig, bleibt aber ein gueltiger Link zur echten Quelle.
        kreis_url = f"{rki_url}#{kreis.replace(' ', '_')}"
        # Alle Bundeslaender haben jetzt Landkreis-genaue Koordinaten. Bayern
        # (heute am gruendlichsten geprueft) etwas enger als der Rest, wo die
        # Kreisstadt-Koordinaten aus Allgemeinwissen statt Kartenabgleich
        # stammen und daher etwas grosszuegiger toleriert werden.
        radius_km = 20.0 if bundesland == "Bayern" else 25.0
        try:
            conn.execute("""
                INSERT OR IGNORE INTO outbreak_events
                (source, disease, syndrome_slug, country, country_iso,
                 region, lat, lon, date_reported, date_start,
                 severity, url, title, fetched_at, person, radius_km)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, ("lgl_fsme", "Frühsommermeningoenzephalitis (FSME)", "fsme",
                  "Deutschland", "DE", kreis,
                  lat, lon,
                  f"{year}-01-01", f"{year}-04-01",
                  "medium", kreis_url, title, now, _OWN_PERSON_ID, radius_km))
            if conn.execute("SELECT changes()").fetchone()[0]:
                inserted += 1
        except DB_ERRORS:
            pass

    conn.commit()
    return inserted


# ── WAHIS / WOAH Tierseuchenberichte ─────────────────────────────────────────
# Der offizielle WOAH-Endpunkt (POST /pi/getReportList) ist per Cloudflare-
# Bot-Schutz blockiert (HTTP 403 "Attention Required", auch mit realistischen
# Browser-Headern -- verifiziert per curl) und WOAH selbst verweist (Stand
# dieser Recherche, wahis-support.woah.org/support/solutions/articles/
# 51000034446) NUR auf einen manuellen Support-Kontakt fuer einen Excel-Export,
# keine automatisierte API. Deshalb stattdessen: die von EcoHealth Alliance
# (etablierte Public-Health-Forschungsorganisation) gepflegte oeffentliche
# SQL-Spiegelung der WAHIS-Rohdaten auf DoltHub (github.com/ecohealthalliance/
# wahis, dolthub.com/repositories/ecohealthalliance/wahisdb) -- kein Auth, kein
# Cloudflare-Block, sauberes JSON ueber einen simplen HTTP-GET mit SQL-Query
# als Parameter, verifiziert per echtem curl-Test (147522 Zeilen, reale
# Koordinaten/Verwaltungsebenen). EINSCHRAENKUNG, die ehrlich benannt werden
# muss: dieser Datensatz ist eine EINMALIGE Spiegelung, eingefroren bei
# 2024-03-22 (per Live-Test verifiziert, MAX(outbreak_start_date)) -- keine
# laufenden Updates von EcoHealth Alliance seither erkennbar. Fuer "aktuelle
# Ausbruchswarnung" (wie who/ecdc) ist das ungeeignet; fuer den eigentlichen
# Zweck dieses Projekts -- Abgleich vergangener Aufenthaltsorte gegen bekannte
# Tierseuchen-Ausbruchsorte -- ist ein historischer 2005-2024-Datensatz mit
# echten Koordinaten sogar besser geeignet als ein reiner "letzte 12 Monate"-
# Feed. Sollte WOAH die angekuendigte oeffentliche API veroeffentlichen oder
# der Cloudflare-Block fallen, waere eine erneute Umstellung auf die Live-
# Quelle (fuer echte Aktualitaet) ein sinnvolles Folge-Update -- der direkte
# POST-Endpunkt-Code aus dem vorherigen Anlauf wurde hier bewusst NICHT
# dormant stehen gelassen (anders als z.B. beim urspruenglichen WAHIS-Versuch),
# da eine kuenftige offizielle API ohnehin vermutlich eine andere Form haette.
_WAHISDB_API = "https://www.dolthub.com/api/v1alpha1/ecohealthalliance/wahisdb/main"

# (Anzeigename, Slug, Kurzcode, Such-Stichwort in wahis_outbreaks.disease_eng)
# -- das Stichwort ist bewusst NICHT identisch zum Anzeigenamen: wahisdb nutzt
# OIE-Langform-Bezeichnungen ("brucella abortus (inf. with)" statt
# "Brucellosis"), verifiziert per Live-Abfrage der DISTINCT disease_eng-Werte.
# Leptospirose/Tularaemie liefern dort KEINE Treffer -- beide sind offenbar
# nicht Teil der WOAH-Pflichtmeldeliste (bleiben trotzdem hier stehen, falls
# sich das aendert oder eine kuenftige offizielle API sie doch fuehrt).
WAHIS_DISEASES = [
    ("Q Fever",           "q_fieber",      "QF",   "q fever"),
    ("Brucellosis",       "brucellose",    "BR",   "brucella"),
    ("West Nile Fever",   "west_nile",     "WNF",  "west nile"),
    ("Leptospirosis",     "leptospirose",  "LEPT", "leptospir"),
    ("Tularemia",         "tularaemie",    "TUL",  "tular"),
]


def _fetch_wahisdb(sql: str) -> list[dict] | None:
    """GET-Query gegen die oeffentliche DoltHub-SQL-API (s. Kommentar oben).

    Gibt None bei jeglichem Fehler zurueck, inkl. einem SQL-/Server-Fehler,
    den DoltHub mit HTTP 200 aber query_execution_status != "Success" meldet
    (deshalb explizite Pruefung statt nur auf HTTP-Fehler zu verlassen).
    """
    url = f"{_WAHISDB_API}?q={urllib.parse.quote(sql)}"
    raw = _fetch_url(url, timeout=20)
    if not raw:
        print(t("  WAHIS: nicht erreichbar", "  WAHIS: not reachable"))
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        print(t(f"  WAHIS: JSON-Fehler: {e}", f"  WAHIS: JSON error: {e}"))
        return None
    if data.get("query_execution_status") != "Success":
        print(t(f"  WAHIS: SQL-API nicht erreichbar (Fehler: {data.get('query_execution_message')})",
                f"  WAHIS: SQL API not reachable (error: {data.get('query_execution_message')})"))
        return None
    return data.get("rows") or []


def _fetch_wahis_outbreaks(is_wild: bool) -> list[dict] | None:
    keywords = " OR ".join(f"LOWER(disease_eng) LIKE '%{kw}%'" for *_, kw in WAHIS_DISEASES)
    sql = (
        "SELECT report_outbreak_species_id_unique, disease_eng, country_name, "
        "level1_name, latitude, longitude, outbreak_start_date, cases, is_wild "
        f"FROM wahis_outbreaks WHERE is_wild = {1 if is_wild else 0} AND ({keywords})"
    )
    return _fetch_wahisdb(sql)


def _wahis_disease_match(disease_eng: str) -> tuple[str, str] | None:
    low = (disease_eng or "").lower()
    for name, slug, _code, kw in WAHIS_DISEASES:
        if kw in low:
            return name, slug
    return None


def _insert_wahis_rows(conn: sqlite3.Connection, rows: list[dict], source: str,
                        default_severity: str) -> int:
    now = datetime.now(timezone.utc).isoformat()
    inserted = 0
    for row in rows:
        match = _wahis_disease_match(row.get("disease_eng"))
        if not match:
            continue
        disease_name, slug = match
        country_name = (row.get("country_name") or "").strip()
        region = (row.get("level1_name") or "").strip() or None
        iso = _iso_from_country(country_name) if country_name else None
        date_ = str(row.get("outbreak_start_date") or "")[:10] or None
        try:
            lat = float(row["latitude"]) if row.get("latitude") not in (None, "") else None
            lon = float(row["longitude"]) if row.get("longitude") not in (None, "") else None
        except (TypeError, ValueError):
            lat = lon = None
        cases = row.get("cases")
        try:
            cases_n = float(cases) if cases not in (None, "") else None
        except (TypeError, ValueError):
            cases_n = None
        severity = (default_severity if cases_n is None else
                    "low" if cases_n < 5 else "medium" if cases_n < 50 else "high")
        title = f"{disease_name} ({source}) — {country_name or '?'}"
        # Eindeutige URL pro Ausbruch noetig, sonst greift
        # idx_outbreak_url UNIQUE(source, COALESCE(url, title||date_reported))
        # nach dem ersten Insert fuer alle weiteren Zeilen (identisches
        # Muster wie der fetch_lgl_fsme()-Dedup-Bug frueher in dieser Session:
        # live beobachtet, ohne diesen Fix wurde nur 1 von 914 Zeilen
        # eingefuegt).
        outbreak_pk = row.get("report_outbreak_species_id_unique") or f"{disease_name}{country_name}{date_}"
        url = f"https://dolthub.com/repositories/ecohealthalliance/wahisdb#{outbreak_pk}"
        try:
            conn.execute("""
                INSERT OR IGNORE INTO outbreak_events
                (source, disease, syndrome_slug, country, country_iso, region,
                 lat, lon, date_reported, date_start, severity, url, title,
                 fetched_at, person)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (source, disease_name, slug, country_name or None, iso, region,
                  lat, lon, date_, date_, severity, url,
                  title, now, _OWN_PERSON_ID))
            if conn.execute("SELECT changes()").fetchone()[0]:
                inserted += 1
        except DB_ERRORS as e:
            print(t(f"  DB-Fehler: {e}", f"  DB error: {e}"))

    conn.commit()
    return inserted


# ── WAHIS Live-Bruecke (schliesst die Luecke 2024-03-22 -> heute) ───────────
# Der ALTE, community-dokumentierte Endpunkt (POST /pi/getReportList, s.
# github.com/loicleray/WOAH_WAHIS.ReportRetriever) existiert offenbar nicht
# mehr in dieser Form -- per Live-Test per echtem Browser (Playwright,
# Netzwerk-Mitschnitt der echten WAHIS-Startseite) gefunden: der TATSAECHLICH
# von der Webseite selbst genutzte aktuelle Endpunkt ist
# POST /api/v1/pi/event/filtered-list. Der fruehere Cloudflare-403 betraf nur
# den falschen/veralteten Endpunkt -- dieser hier ist per PLAIN HTTP-POST
# erreichbar, OHNE Browser, OHNE Session-Cookie, verifiziert per curl (Status
# 200, echte Berichte bis zum aktuellen Tagesdatum). Die Absicherung erfolgt
# nicht durch Cloudflare-Bot-Erkennung, sondern durch statische App-Header
# (token/clientid), die die Anfrage als von der offiziellen Webseite kommend
# ausweisen -- kein Auth im eigentlichen Sinn, aber ohne diese Header liefert
# der Endpunkt vermutlich 400/403 (nicht einzeln getestet, alle Header
# beibehalten wie vom echten Browser gesendet, sicherheitshalber).
_WAHIS_LIVE_API = "https://wahis.woah.org/api/v1/pi/event/filtered-list"
_WAHIS_LIVE_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "token": "#PIPRD202006#",
    "clientid": "OIEwebsite",
    "env": "PRD",
    "referer": "https://wahis.woah.org/",
    "accept-language": "en",
    "User-Agent": "Mozilla/5.0 (Kyoro-HealthHub/1.0)",
}


def _fetch_wahis_live_page(page_number: int, page_size: int = 200) -> dict | None:
    """Eine Seite Immediate-Notification-Berichte (reportTypes=IN) vom echten
    Live-Endpunkt. Gibt None bei jeglichem Fehler zurueck."""
    payload = {
        "animalTypes": [], "countries": [], "eventIds": [], "eventStartDate": None,
        "eventStatuses": [], "firstDiseases": [], "reasons": [], "reportIds": [],
        "reportStatuses": [], "reportTypes": ["IN"], "secondDiseases": [],
        "sortColumn": "submissionDate", "sortOrder": "desc", "submissionDate": None,
        "typeStatuses": [], "pageNumber": page_number, "pageSize": page_size,
    }
    try:
        req = urllib.request.Request(
            f"{_WAHIS_LIVE_API}?language=en", method="POST",
            data=json.dumps(payload).encode("utf-8"),
            headers=_WAHIS_LIVE_HEADERS,
        )
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read().decode("utf-8", errors="replace"))
    except Exception as e:
        print(t(f"  WAHIS-Live: nicht erreichbar ({e})", f"  WAHIS-Live: not reachable ({e})"))
        return None


def _fetch_wahis_live_events(max_pages: int = 10, page_size: int = 200) -> list[dict]:
    """Paginiert durch alle aktuellen Immediate-Notification-Berichte.

    max_pages=10 x page_size=200 = bis zu 2000 Berichte Kopfraum -- die
    komplette IN-Historie umfasste bei Verifikation dieser Quelle 973
    Berichte insgesamt, waechst also nur langsam.
    """
    events: list[dict] = []
    for page in range(max_pages):
        data = _fetch_wahis_live_page(page, page_size)
        if not data:
            break
        batch = data.get("list") or []
        events.extend(batch)
        if len(batch) < page_size or len(events) >= (data.get("totalSize") or 0):
            break
    return events


def _insert_wahis_live_rows(conn: sqlite3.Connection, rows: list[dict]) -> int:
    """Live-Berichte -> outbreak_events. Nur Land-Ebene (kein lat/lon in
    dieser Liste, anders als bei den DoltHub-Zeilen) -- konsistent mit dem
    Praezisions-Niveau anderer aktueller Quellen wie WHO DON/ECDC."""
    now = datetime.now(timezone.utc).isoformat()
    inserted = 0
    for row in rows:
        match = _wahis_disease_match(row.get("disease"))
        if not match:
            continue
        disease_name, slug = match
        country_name = (row.get("country") or "").strip()
        iso = _iso_from_country(country_name) if country_name else None
        date_ = str(row.get("eventStartDate") or row.get("submissionDate") or "")[:10] or None
        event_id = row.get("eventId") or row.get("reportId")
        title = f"{disease_name} (WAHIS aktuell) — {country_name or '?'}"
        url = f"https://wahis.woah.org/#/in-event/{event_id}"
        try:
            conn.execute("""
                INSERT OR IGNORE INTO outbreak_events
                (source, disease, syndrome_slug, country, country_iso,
                 date_reported, date_start, severity, url, title, fetched_at, person)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """, ("wahis", disease_name, slug, country_name or None, iso,
                  date_, date_, "medium", url, title, now, _OWN_PERSON_ID))
            if conn.execute("SELECT changes()").fetchone()[0]:
                inserted += 1
        except DB_ERRORS as e:
            print(t(f"  DB-Fehler: {e}", f"  DB error: {e}"))

    conn.commit()
    return inserted


def fetch_wahis(conn: sqlite3.Connection) -> int:
    """WOAH/WAHIS Tierseuchenberichte bei Nutztieren → outbreak_events.

    Zwei kombinierte Quellen: (1) reale historische Ausbrueche (Q-Fieber,
    Brucellose, WNV etc. -- Zoonosen mit humanmedizinischer Relevanz) aus der
    EcoHealth-Alliance-Spiegelung der WAHIS-Rohdaten (s. Kommentar bei
    _WAHISDB_API), gefiltert auf is_wild=0, mit echten Koordinaten, aber
    eingefroren bei 2024-03-22; (2) der Live-Endpunkt (s. Kommentar bei
    _WAHIS_LIVE_API) fuer alles seither bis heute, nur auf Land-Ebene (kein
    Wild/Nutztier-Filter dort verifizierbar -- ein Test mit
    animalTypes=["Wild"] lieferte HTTP 400 "IllegalArgumentException", der
    gueltige Enum-Wert wurde nicht ermittelt; alle Live-Berichte laufen daher
    hier unter "wahis", s. fetch_wahis_wild()-Docstring fuer die daraus
    folgende Deckungsluecke bei Wildtier-Ausbruechen nach 2024-03-22).
    """
    inserted = 0
    historical = _fetch_wahis_outbreaks(is_wild=False)
    if historical:
        inserted += _insert_wahis_rows(conn, historical, "wahis", "medium")
    live = _fetch_wahis_live_events()
    if live:
        inserted += _insert_wahis_live_rows(conn, live)
    return inserted


def fetch_wahis_wild(conn: sqlite3.Connection) -> int:
    """WAHIS-Ausbrueche bei Wildtieren → outbreak_events.

    Dieselbe EcoHealth-Alliance-Spiegelung wie fetch_wahis(), aber gefiltert
    auf is_wild=1. HINWEIS zur Begriffsverschiebung: das urspruengliche WOAH-
    "WAHIS-Wild"-Modul meint freiwillige Meldungen ausserhalb der
    Pflichtmeldeliste (z.B. Tollwut bei Wildtieren) -- dieser Datensatz bildet
    stattdessen den Wildtier-vs-Nutztier-Split INNERHALB der Pflichtmeldeliste
    ab (is_wild-Flag in wahis_outbreaks). Fachlich dieselbe Kernfrage
    (Zoonose-Risiko aus Wildtier-Reservoiren vs. Nutztierbestaenden), aber
    nicht 1:1 deckungsgleich mit dem offiziellen Modulnamen -- deshalb hier
    explizit dokumentiert statt stillschweigend gleichgesetzt.

    LUECKE nach dem Stichtag der historischen Spiegelung (s. _WAHISDB_API-
    Kommentar): anders als fetch_wahis() hat diese Funktion KEINE
    Live-Bruecke -- der Live-Endpunkt liefert keinen verifizierten Wild/
    Nutztier-Filter (s. fetch_wahis()-Docstring), daher bleiben aktuelle
    Wildtier-Ausbrueche hier unerfasst, bis ein gueltiger Filterwert gefunden
    wird oder WOAH eine eigene API veroeffentlicht.
    """
    rows = _fetch_wahis_outbreaks(is_wild=True)
    if not rows:
        return 0
    return _insert_wahis_rows(conn, rows, "wahis_wild", "low")


# ── WHO EMRO (Mittelmeer / Naher Osten) ───────────────────────────────────────

def _fetch_url_retrying(url: str, attempts: int = 3, delay: float = 2.0) -> str | None:
    """Wie _fetch_url(), aber mit kurzen Wiederholungsversuchen.

    Nur fuer Quellen mit belegter Backend-Instabilitaet gedacht (aktuell nur
    WHO EMRO, s. dortiger Docstring) -- bewusst NICHT der Default in
    _fetch_url() selbst, um bei echt toten Domains nicht unnoetig die
    Gesamtlaufzeit zu verlaengern (ein totes DNS/Timeout wird durch Wiederholen
    nicht funktionierend).
    """
    for attempt in range(attempts):
        result = _fetch_url(url)
        if result:
            return result
        if attempt < attempts - 1:
            time.sleep(delay)
    return None


def fetch_who_emro(conn: sqlite3.Connection) -> int:
    """WHO EMRO Ausbruchs-RSS (Mittelmeer, Naher Osten) → outbreak_events.

    Kein URL-Problem, sondern belegte Backend-Instabilitaet: per wiederholtem
    Live-Test verifiziert, dieselbe URL liefert abwechselnd HTTP 200 (echter
    Inhalt) und 502 "Bad Gateway" (Microsoft-Azure-Application-Gateway) --
    ca. jeder zweite Versuch schlaegt fehl, unabhaengig von der konkreten URL.
    Deshalb per _fetch_url_retrying() mit kurzen Wiederholungen statt einmalig
    _fetch_url(). Die RSS-spezifischen Pfade (rss.xml, feed/rss.html) waren in
    mehreren Testreihen durchgehend 502 (moeglicherweise ein separat
    ausgefallener RSS-Generierungsdienst hinter demselben Gateway, waehrend
    normale HTML-Seiten von einem anderen, stabileren Backend bedient werden)
    -- deshalb zusaetzlich ein HTML-Scraping-Fallback der Newsroom-Listing-
    Seite, die in Tests deutlich zuverlaessiger echten Inhalt lieferte.
    """
    rss_candidates = [
        "https://www.emro.who.int/health-topics/disease-outbreaks/feed/rss.html",
        "https://www.emro.who.int/pandemic-epidemic-diseases/about/feed/rss.html",
        "https://www.emro.who.int/media/disease-outbreaks/rss.xml",
        "https://www.emro.who.int/node/feed",
        "https://www.emro.who.int/media/news/rss.xml",
    ]
    for u in rss_candidates:
        xml = _fetch_url_retrying(u)
        if xml and "<item>" in xml:
            return _parse_generic_rss(conn, xml, "who_emro", "medium")

    html = _fetch_url_retrying("https://www.emro.who.int/media/news/")
    if not html:
        print(t("  WHO EMRO: kein RSS erreichbar", "  WHO EMRO: no RSS reachable"))
        return 0

    now = datetime.now(timezone.utc).isoformat()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    inserted = 0
    health_kw = {
        "outbreak", "disease", "fever", "virus", "infection", "epidemic",
        "alert", "health", "fieber", "ausbruch", "krankheit",
    }
    seen_links = set()
    for href, title in re.findall(r'href="(/media/news/[^"]+\.html)"\s+title="([^"]{5,200})"', html):
        if href in seen_links:
            continue
        seen_links.add(href)
        title = title.strip()
        if not any(k in title.lower() for k in health_kw):
            continue
        slug = _slug_from_disease(title)
        link = f"https://www.emro.who.int{href}"
        try:
            conn.execute("""
                INSERT OR IGNORE INTO outbreak_events
                (source, disease, syndrome_slug, date_reported, severity,
                 url, title, fetched_at, person)
                VALUES (?,?,?,?,?,?,?,?,?)
            """, ("who_emro", title, slug, today, "medium", link, title, now, _OWN_PERSON_ID))
            if conn.execute("SELECT changes()").fetchone()[0]:
                inserted += 1
        except DB_ERRORS as e:
            print(t(f"  DB-Fehler: {e}", f"  DB error: {e}"))

    conn.commit()
    return inserted


# ── WHO AFRO (Afrika) ─────────────────────────────────────────────────────────

def fetch_who_afro(conn: sqlite3.Connection) -> int:
    """WHO AFRO Ausbruchs-RSS (Afrika) → outbreak_events."""
    candidates = [
        "https://www.afro.who.int/feed",
        "https://www.afro.who.int/rss.xml",
        "https://www.afro.who.int/media-centre/news/feed",
        "https://www.afro.who.int/health-topics/disease-outbreaks/outbreaks-and-other-emergencies/rss.xml",
        "https://www.afro.who.int/node/feed",
    ]
    xml = None
    for u in candidates:
        xml = _fetch_url(u)
        if xml and "<item>" in xml:
            break
    if not xml:
        print(t("  WHO AFRO: kein RSS erreichbar", "  WHO AFRO: no RSS reachable"))
        return 0

    return _parse_generic_rss(conn, xml, "who_afro", "medium")


def _parse_generic_rss(conn: sqlite3.Connection, xml_text: str,
                       source: str, default_severity: str) -> int:
    """Hilfsfunktion: Parst einen generischen RSS-Feed → outbreak_events."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        print(t(f"  XML-Fehler ({source}): {e}", f"  XML error ({source}): {e}"))
        return 0

    now = datetime.now(timezone.utc).isoformat()
    inserted = 0
    health_kw = {
        "outbreak", "disease", "fever", "virus", "infection", "epidemic",
        "alert", "health", "fieber", "ausbruch", "krankheit",
    }

    for item in root.iter("item"):
        title    = (item.findtext("title") or "").strip()
        link     = (item.findtext("link") or "").strip()
        pub_date = (item.findtext("pubDate") or "").strip()

        if not any(k in title.lower() for k in health_kw):
            continue

        date_rep = _parse_rss_date(pub_date) if pub_date else \
                   datetime.now(timezone.utc).strftime("%Y-%m-%d")

        parts   = re.split(r"\s[–—-]\s", title, maxsplit=1)
        disease = parts[0].strip() if parts else title
        country = parts[1].strip() if len(parts) > 1 else ""
        iso     = _iso_from_country(country) if country else None
        slug    = _slug_from_disease(disease)

        try:
            conn.execute("""
                INSERT OR IGNORE INTO outbreak_events
                (source, disease, syndrome_slug, country, country_iso,
                 date_reported, severity, url, title, fetched_at, person)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """, (source, disease, slug, country or None, iso,
                  date_rep, default_severity, link, title, now, _OWN_PERSON_ID))
            if conn.execute("SELECT changes()").fetchone()[0]:
                inserted += 1
        except DB_ERRORS:
            pass

    conn.commit()
    return inserted


# ── WHO Regionalbüros (PAHO · SEARO · EURO · WPRO) ───────────────────────────
# Ergänzt EMRO (Naher Osten) und AFRO (Afrika) — deckt alle 6 WHO-Regionen ab

_WHO_REGIONAL_FEEDS: dict[str, list[str]] = {
    "who_paho": [                                          # Amerika -- eigene
        "https://www.paho.org/en/node/feed",                # Alt-Subdomain,
        "https://www.paho.org/en/rss.xml",                   # RSS funktioniert
        "https://www.paho.org/hq/index.php?format=feed&type=rss",
    ],
}


def _fetch_who_regional(conn: sqlite3.Connection, source_key: str) -> int:
    for url in _WHO_REGIONAL_FEEDS[source_key]:
        xml = _fetch_url(url)
        if xml and "<item>" in xml:
            return _parse_generic_rss(conn, xml, source_key, "medium")
    label = source_key.upper().replace("_", " ")
    print(t(f"  {label}: kein RSS erreichbar", f"  {label}: no RSS reachable"))
    return 0


def fetch_who_paho(conn: sqlite3.Connection) -> int:
    return _fetch_who_regional(conn, "who_paho")


# SEARO/EURO/WPRO haben (anders als EMRO/AFRO/PAHO) KEINE eigene Alt-Subdomain
# mit funktionierendem RSS mehr -- alle vorherigen RSS-Kandidaten-URLs waren
# tot (404/DNS-Fehler). Per echtem Browser-Traffic-Mitschnitt (Playwright) der
# jeweiligen who.int/<region>/news-room-Seite gefunden: alle drei nutzen
# dieselbe generische News-API wie fetch_who_don() (dort global, hier per
# sf_provider-Parameter auf die Region eingegrenzt), verifiziert per curl
# (aktuelle Eintraege bis zum Tagesdatum). EMRO/AFRO/PAHO brauchen das nicht,
# da ihre Alt-Subdomains weiterhin eigenes RSS anbieten.
_WHO_NEWS_API = "https://www.who.int/api/news/newsitems"

# (sf_provider, zusaetzlicher $filter, URL-Praefix fuer ItemDefaultUrl) je
# Region. EURO braucht zusaetzlich einen publishingoffices-GUID-Filter (ohne
# ihn lieferte die API im Test globale statt Europa-spezifische Eintraege);
# SEARO/WPRO filtern allein schon ueber sf_provider korrekt.
_WHO_REGION_NEWS_API: dict[str, tuple[str, str, str]] = {
    "who_euro": ("newsProvider29",
                 "&$filter=publishingoffices/any(s:s%20eq%209be40736-df8d-4fb1-a7f8-9ec7c8da7aff)",
                 "https://www.who.int/europe"),
    "who_searo": ("newsProvider16", "", "https://www.who.int/southeastasia"),
    "who_wpro": ("newsProvider2", "", "https://www.who.int/westernpacific"),
}


def _fetch_who_region_news(conn: sqlite3.Connection, source_key: str) -> int:
    sf_provider, extra_filter, url_prefix = _WHO_REGION_NEWS_API[source_key]
    url = (
        f"{_WHO_NEWS_API}?sf_provider={sf_provider}&sf_culture=en"
        "&$top=50&$orderby=PublicationDateAndTime%20desc"
        "&$select=Title,ItemDefaultUrl,FormatedDate,NewsType"
        f"{extra_filter}&$format=json&$count=true"
    )
    text = _fetch_url(url)
    if not text:
        label = source_key.upper().replace("_", " ")
        print(t(f"  {label}: kein RSS erreichbar", f"  {label}: no RSS reachable"))
        return 0
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        print(t(f"  XML-Fehler ({source_key}): {e}", f"  XML error ({source_key}): {e}"))
        return 0

    # Dieselbe Stichwort-Heuristik wie _parse_generic_rss() -- die News-API
    # liefert ALLE Newsroom-Meldungen der Region (Personal, Statements,
    # Presseerklaerungen etc.), nicht nur Ausbruchsmeldungen.
    health_kw = {
        "outbreak", "disease", "fever", "virus", "infection", "epidemic",
        "alert", "health", "fieber", "ausbruch", "krankheit",
    }
    now = datetime.now(timezone.utc).isoformat()
    inserted = 0
    for item in data.get("value", []):
        title = (item.get("Title") or "").strip()
        if not title or not any(k in title.lower() for k in health_kw):
            continue
        path = item.get("ItemDefaultUrl") or ""
        link = f"{url_prefix}{path}" if path else url_prefix
        date_raw = item.get("FormatedDate") or ""
        try:
            date_rep = datetime.strptime(date_raw, "%d %B %Y").strftime("%Y-%m-%d")
        except ValueError:
            date_rep = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        parts = re.split(r"\s[–—-]\s", title, maxsplit=1)
        disease = parts[0].strip() if parts else title
        country = parts[1].strip() if len(parts) > 1 else ""
        iso = _iso_from_country(country) if country else None
        slug = _slug_from_disease(disease)
        try:
            conn.execute("""
                INSERT OR IGNORE INTO outbreak_events
                (source, disease, syndrome_slug, country, country_iso,
                 date_reported, severity, url, title, fetched_at, person)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """, (source_key, disease, slug, country or None, iso,
                  date_rep, "medium", link, title, now, _OWN_PERSON_ID))
            if conn.execute("SELECT changes()").fetchone()[0]:
                inserted += 1
        except DB_ERRORS as e:
            print(t(f"  DB-Fehler: {e}", f"  DB error: {e}"))

    conn.commit()
    return inserted


def fetch_who_searo(conn: sqlite3.Connection) -> int:
    return _fetch_who_region_news(conn, "who_searo")


def fetch_who_euro(conn: sqlite3.Connection) -> int:
    return _fetch_who_region_news(conn, "who_euro")


def fetch_who_wpro(conn: sqlite3.Connection) -> int:
    return _fetch_who_region_news(conn, "who_wpro")


# ── CDC Travel Health Notices ──────────────────────────────────────────────────
# Level 1 (Watch) → low, Level 2 (Alert) → medium, Level 3 (Warning) → high

_CDC_LEVELS = [
    ("warning", "high"),
    ("alert",   "medium"),
    ("watch",   "low"),
]


def fetch_cdc_travel(conn: sqlite3.Connection) -> int:
    """CDC Travel Health Notices (Level 1–3) → outbreak_events."""
    inserted = 0
    now   = datetime.now(timezone.utc).isoformat()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    for level, severity in _CDC_LEVELS:
        xml = None
        for tmpl in [
            "https://wwwnc.cdc.gov/travel/rss/notices.xml",
            f"https://wwwnc.cdc.gov/travel/notices/warning/rss.xml",
            f"https://wwwnc.cdc.gov/travel/notices/alert/rss.xml",
            f"https://wwwnc.cdc.gov/travel/notices/watch/rss.xml",
            f"https://wwwnc.cdc.gov/travel/notices/{level}.rss",
            f"https://wwwnc.cdc.gov/travel/notices/{level}/rss.xml",
        ]:
            xml = _fetch_url(tmpl)
            if xml and "<item>" in xml:
                break

        if xml and "<item>" in xml:
            inserted += _parse_generic_rss(conn, xml, "cdc_travel", severity)
            time.sleep(0.3)
            continue

        # Fallback: HTML-Scraping der Notice-Übersichtsseite
        html = _fetch_url("https://wwwnc.cdc.gov/travel/notices")
        if not html:
            continue
        # Titel-Zeilen im Format "Disease – Country (Level N)"
        matches = re.findall(
            r'href="(/travel/notices/[^"]+)"[^>]*>\s*([^<]{5,120})</a>',
            html
        )
        for path, title in matches[:60]:
            title = title.strip()
            if not any(k in title.lower() for k in
                       {"disease", "fever", "virus", "outbreak", "infection",
                        "alert", "health", "warning", "cholera", "dengue"}):
                continue
            m = re.search(r"\bin\s+([A-Z][A-Za-z\s\-]{2,40})(?:\s*[\(\[]|$)", title)
            country_name = m.group(1).strip() if m else ""
            iso  = _iso_from_country(country_name) if country_name else None
            slug = _slug_from_disease(title)
            url  = ("https://wwwnc.cdc.gov" + path
                    if path.startswith("/") else path)
            try:
                conn.execute("""
                    INSERT OR IGNORE INTO outbreak_events
                    (source, disease, syndrome_slug, country, country_iso,
                     date_reported, severity, url, title, fetched_at, person)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?)
                """, ("cdc_travel", title, slug,
                      country_name or None, iso,
                      today, severity, url, title, now, _OWN_PERSON_ID))
                if conn.execute("SELECT changes()").fetchone()[0]:
                    inserted += 1
            except DB_ERRORS:
                pass
        conn.commit()

    return inserted


# ── HealthMap (Boston Children's Hospital) ────────────────────────────────────
# Automatisierte globale Ausbruchs-Surveillance via News-Mining + Netzwerk

_HEALTHMAP_ALERTS_URL = (
    "https://healthmap.org/getAlerts.php"
    "?locations=&diseases=&sources=&species=&category%5B%5D=1&category%5B%5D=2"
    "&category%5B%5D=29&vaccines=&time_interval=1+week"
    "&zoom_lat=15.000000&zoom_lon=18.000000&zoom_level=2"
    "&displayapi=&heatscore=1&partner=hm"
)


def fetch_healthmap(conn: sqlite3.Connection) -> int:
    """HealthMap globale Ausbruchs-Surveillance → outbreak_events.

    Kein RSS-Feed mehr (die alten /rss-Kandidaten sind alle 403/404) --
    per echtem Browser-Traffic-Mitschnitt (Playwright) gefunden: die Karte
    auf der Startseite laedt ihre Daten von getAlerts.php, einem oeffentlichen
    GET-Endpunkt ohne Auth, verifiziert per curl. Jeder "marker" ist ein
    geokodierter Ort mit einem "label"-Feld, das eine kommagetrennte Liste
    ALLER dort in den letzten `time_interval` getrackten Themen ist -- nicht
    nur Krankheiten, sondern auch Kategorien wie "Conflict", "Poisoning",
    "Environmental", "Undiagnosed" (per Live-Test verifiziert). Gefiltert wird
    daher ueber _slug_from_disease() gegen die bestehende DISEASE_SLUG_MAP
    (None = keine erkannte Infektionskrankheit -> verworfen), nicht ueber
    HealthMaps eigene category-Parameter, die trotz Filterung im Request
    weiterhin themenfremde Eintraege im label-Feld mischen.
    """
    raw = _fetch_url(_HEALTHMAP_ALERTS_URL, timeout=20)
    if not raw:
        print(t("  HealthMap: nicht erreichbar", "  HealthMap: not reachable"))
        return 0
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        print(t(f"  HealthMap: JSON-Fehler: {e}", f"  HealthMap: JSON error: {e}"))
        return 0

    markers = data.get("markers") or []
    if not markers:
        print(t("  HealthMap: kein RSS erreichbar", "  HealthMap: no RSS reachable"))
        return 0

    now = datetime.now(timezone.utc).isoformat()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    inserted = 0
    for marker in markers:
        place_name = (marker.get("place_name") or "").strip()
        place_id = marker.get("place_id")
        lat, lon = marker.get("lat"), marker.get("lon")
        country_name = place_name.rsplit(",", 1)[-1].strip() if place_name else ""
        iso = _iso_from_country(country_name) if country_name else None
        labels = [x.strip() for x in (marker.get("label") or "").split(",")]
        for label in labels:
            if not label:
                continue
            slug = _slug_from_disease(label)
            if slug is None:
                continue
            title = f"{label} — {place_name or '?'}"
            url = f"https://healthmap.org/en/#{place_id}-{slug}-{today}"
            try:
                conn.execute("""
                    INSERT OR IGNORE INTO outbreak_events
                    (source, disease, syndrome_slug, country, country_iso, region,
                     lat, lon, date_reported, severity, url, title, fetched_at, person)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, ("healthmap", label, slug, country_name or None, iso,
                      place_name or None, lat, lon, today, "medium",
                      url, title, now, _OWN_PERSON_ID))
                if conn.execute("SELECT changes()").fetchone()[0]:
                    inserted += 1
            except DB_ERRORS as e:
                print(t(f"  DB-Fehler: {e}", f"  DB error: {e}"))

    conn.commit()
    return inserted


# ── Eurosurveillance Rapid Communications ─────────────────────────────────────
# Peer-reviewed Schnellmeldungen zu neuen Ausbrüchen in Europa (ECDC Journal)

def fetch_eurosurveillance(conn: sqlite3.Connection) -> int:
    """Eurosurveillance Rapid Communications → outbreak_events."""
    candidates = [
        "https://www.eurosurveillance.org/rss/content/eurosurveillance/latestarticles?fmt=rss",
        "https://www.eurosurveillance.org/content/eurosurveillance?TRACK=RSS",
        "https://www.eurosurveillance.org/content/feed",
        "https://www.eurosurveillance.org/rss",
        "https://www.eurosurveillance.org/rss.xml",
    ]
    for url in candidates:
        xml = _fetch_url(url)
        if xml and "<item>" in xml:
            return _parse_generic_rss(conn, xml, "eurosurveillance", "medium")
    print(t("  Eurosurveillance: kein RSS erreichbar", "  Eurosurveillance: no RSS reachable"))
    return 0


# ── ReliefWeb (UN OCHA) ───────────────────────────────────────────────────────
# Humanitäre Lage- und Ausbruchsberichte — besonders relevant für Reisen in
# Krisenregionen; kostenlose REST-API ohne API-Key

_RELIEFWEB_API = "https://api.reliefweb.int/v2/reports"
_RELIEFWEB_PARAMS = (
    "?query[value]=disease+outbreak+epidemic+health+emergency"
    "&fields[include][]=title"
    "&fields[include][]=date.created"
    "&fields[include][]=primary_country.name"
    "&fields[include][]=url_alias"
    "&sort[]=date.created:desc"
    "&limit=50"
    "&appname=kyoro-healthhub"
)


def fetch_reliefweb(conn: sqlite3.Connection) -> int:
    """ReliefWeb (UN OCHA) Gesundheitsberichte → outbreak_events.

    AEHNLICH wie ProMED (s. dortiger Docstring): kein technisches Problem,
    sondern eine bewusste Zugriffsregel des Betreibers. Seit dem in der
    ReliefWeb-API-Doku (apidoc.reliefweb.int/parameters#appname) genannten
    Stichtag ist ein VORAB GENEHMIGTER appname Pflicht -- verifiziert per
    Live-Test: HTTP 403 "You are not using an approved appname", mit Verweis
    auf ein Antragsformular, das ReliefWeb manuell prueft und per E-Mail
    beantwortet. appname="kyoro-healthhub" (frueher hier verwendet) war nie
    eine echte Genehmigung, nur ein Platzhalter, der solange funktionierte,
    wie die Pruefung noch nicht durchgesetzt wurde. Ein neuer appname muesste
    ueber das Formular beantragt werden -- das erfordert Kontakt-/
    Organisationsangaben des Nutzers gegenueber ReliefWeb und kann daher
    nicht automatisiert im Code geloest werden.
    """
    text = _fetch_url(_RELIEFWEB_API + _RELIEFWEB_PARAMS)
    if not text:
        print(t("  ReliefWeb: nicht erreichbar", "  ReliefWeb: not reachable"))
        return 0
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return 0

    now      = datetime.now(timezone.utc).isoformat()
    inserted = 0

    for item in data.get("data", []):
        f     = item.get("fields", {})
        title = f.get("title", "").strip()
        if not title:
            continue

        date_raw  = (f.get("date") or {}).get("created", "")
        date_rep  = date_raw[:10] if date_raw else datetime.now().strftime("%Y-%m-%d")
        countries = f.get("primary_country") or []
        country_name = countries[0].get("name", "") if countries else ""
        iso   = _iso_from_country(country_name) if country_name else None
        slug  = _slug_from_disease(title)
        url   = ("https://reliefweb.int" + f.get("url_alias", "")
                 if f.get("url_alias", "").startswith("/")
                 else f.get("url_alias", "https://reliefweb.int"))

        # Severity: outbreak-Reports als high, sonst low
        severity = "high" if any(k in title.lower() for k in
                                 {"outbreak", "epidemic", "emergency", "alert",
                                  "cholera", "ebola", "mpox", "dengue"}) else "low"

        try:
            conn.execute("""
                INSERT OR IGNORE INTO outbreak_events
                (source, disease, syndrome_slug, country, country_iso,
                 date_reported, severity, url, title, fetched_at, person)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """, ("reliefweb", title, slug,
                  country_name or None, iso,
                  date_rep, severity, url, title, now, _OWN_PERSON_ID))
            if conn.execute("SELECT changes()").fetchone()[0]:
                inserted += 1
        except DB_ERRORS:
            pass

    conn.commit()
    return inserted


# ── CRM (Centrum für Reisemedizin, Deutschland) ───────────────────────────────
# Deutsche Reisemedizin-Gesellschaft — aktuelle Impf- und Gesundheitshinweise
#
# Frueher als "DEAD (Timeout auf allen Endpunkten)" markiert -- per echtem
# Browser-Traffic-Mitschnitt (Playwright) und Live-Test widerlegt: nicht die
# Seite ist tot, nur www.crm.de (die Domain zog auf das bare crm.de um,
# www.crm.de beantwortet seither gar keine Anfragen mehr, auch nicht im
# echten Browser). Der allgemeine RSS-Feed (crm.de/feed/) existiert zwar,
# enthaelt aber nur Seminar-/Blog-Beitraege, keine echten Krankheits-
# Hinweise -- die eigentlichen "aktuellen reisemedizinischen Meldungen"
# werden auf einer dedizierten Seite per WordPress-AJAX clientseitig
# nachgeladen (im rohen HTML nicht vorhanden), gefunden per Netzwerk-
# Mitschnitt der echten Seite. Das dafuer noetige AJAX-Nonce steht aber
# direkt (nicht per weiterem AJAX-Call) im HTML der Seite
# ("var ajaxObject = {...,"ajax_nonce":"..."}"), daher per einfachem
# GET+POST ohne Browser reproduzierbar -- verifiziert per curl (360
# strukturierte Laender-/Krankheits-Eintraege, u.a. ein am aktuellen
# Tagesdatum aktualisierter Polio-Eintrag fuer Afghanistan).

_CRM_ALERTS_PAGE = "https://crm.de/aktuelle-reisemedizinische-meldungen-auf-einen-blick/"
_CRM_AJAX_URL = "https://crm.de/wp-admin/admin-ajax.php"
_CRM_NONCE_RE = re.compile(r'"ajax_nonce":"([a-f0-9]+)"')


def _fetch_crm_alerts() -> list[dict] | None:
    html = _fetch_url(_CRM_ALERTS_PAGE)
    if not html:
        return None
    m = _CRM_NONCE_RE.search(html)
    if not m:
        print(t("  CRM: AJAX-Nonce nicht gefunden (Seite umgebaut?)",
                "  CRM: AJAX nonce not found (page restructured?)"))
        return None
    nonce = m.group(1)
    payload = f"action=crm_get_news_xml_data&country=all&nonce={nonce}".encode("ascii")
    try:
        req = urllib.request.Request(
            _CRM_AJAX_URL, method="POST", data=payload,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": "Kyoro-HealthHub/1.0",
            },
        )
        with urllib.request.urlopen(req, timeout=15) as r:
            raw = r.read().decode("utf-8", errors="replace")
        # Antwort ist ein JSON-String, der selbst wieder JSON enthaelt
        # (doppelt kodiert) -- verifiziert per Live-Test, kein Parsing-Fehler.
        data = json.loads(raw)
        if isinstance(data, str):
            data = json.loads(data)
        return data if isinstance(data, list) else None
    except Exception as e:
        print(t(f"  CRM: nicht erreichbar ({e})", f"  CRM: not reachable ({e})"))
        return None


def fetch_crm(conn: sqlite3.Connection) -> int:
    """CRM Reisemedizin aktuelle Meldungen → outbreak_events.

    Siehe Kommentar oben -- nutzt den echten AJAX-Endpunkt hinter der
    "aktuelle reisemedizinische Meldungen"-Seite statt des allgemeinen
    (fuer diesen Zweck ungeeigneten) Blog-RSS-Feeds.
    """
    rows = _fetch_crm_alerts()
    if not rows:
        return 0

    now = datetime.now(timezone.utc).isoformat()
    inserted = 0
    for row in rows:
        disease = (row.get("keyword_name") or row.get("item_title") or "").strip()
        if not disease:
            continue
        slug = _slug_from_disease(disease)
        country_name = (row.get("country_name") or "").strip()
        iso = _iso_from_country(country_name) if country_name else None
        date_ = str(row.get("release_date") or "")[:10] or None
        anchor = f"{row.get('country_ID')}-{row.get('keyword_id')}-{date_}"
        url = f"{_CRM_ALERTS_PAGE}#{anchor}"
        title = f"{disease} — {country_name or '?'}"
        try:
            conn.execute("""
                INSERT OR IGNORE INTO outbreak_events
                (source, disease, syndrome_slug, country, country_iso,
                 date_reported, date_start, severity, url, title, fetched_at, person)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """, ("crm", disease, slug, country_name or None, iso,
                  date_, date_, "medium", url, title, now, _OWN_PERSON_ID))
            if conn.execute("SELECT changes()").fetchone()[0]:
                inserted += 1
        except DB_ERRORS as e:
            print(t(f"  DB-Fehler: {e}", f"  DB error: {e}"))

    conn.commit()
    return inserted


# ── FLI TSIS (Landkreis-genau, Voegel + Pferde/Gefluegel) ────────────────────
# Einzige Quellen in dieser Datei, die einen echten Browser brauchen
# (Playwright) statt reinem urllib -- das FLI-TierSeuchenInformationsSystem
# (TSIS) laeuft auf "Cadenza" (kommerzielles GIS-/BI-Tool von Disy), das
# keine dokumentierte REST-API bietet.
#
# Erster Anlauf (verworfen): Rechteck-Mehrfachauswahl auf der Kartenansicht
# (Shift+Ziehen ueber ein festes Kachel-Raster) lieferte reale Fallobjekte
# mit Punktkoordinate, aber nur fuer "dieses Jahr" UND nur die gerade als
# Kartenlayer sichtbaren -- bei West-Nil-Virus 11 von ~24 Faellen dieses
# Jahres (Randfaelle an Kachelgrenzen fehlten), bei Aviaerer Influenza sogar
# nur 1-2 (die Kartenansicht zeigt dort standardmaessig NUR "Aktive Faelle",
# nicht die vollen 1700+/Jahr).
#
# Zweiter, verwendeter Anlauf: JEDE Tierseuchen-Ansicht hat unter dem
# "Uebersicht"-Dropdown eine alternative Tabellenansicht "Auflistung der
# Einzelfaelle", und die dortige "Mehr > Exportieren > Alle Tabellen
# (*.xlsx)"-Funktion liefert die KOMPLETTE Fallhistorie (WNV: 630 Zeilen
# seit 2006, Aviaere Influenza: 11820 Zeilen seit 2006) als sauberen Excel-
# Export -- ohne Kartenausschnitt-Limit, ohne "nur aktive Faelle"-Filter,
# ohne Kachel-Rateraten. Kein Punktkoordinate mehr enthalten (nur Kreis-
# Name), dafuer vollstaendig und zuverlaessig -- der bessere Kompromiss für
# den eigentlichen Zweck (welcher Landkreis, nicht auf den Meter genau wo).
_FLI_TSIS_URL = "https://tsis.fli.de/cadenza/"


def _fetch_fli_tsis_export(disease_navigator_text: str, log_label: str) -> list[dict]:
    """Oeffnet TSIS per Playwright, navigiert zur "Auflistung der
    Einzelfaelle"-Tabellenansicht der gegebenen Tierseuche und laedt deren
    vollstaendigen Excel-Export herunter. Gibt eine leere Liste bei
    jeglichem Fehler zurueck (fehlendes Playwright/Chromium/openpyxl
    eingeschlossen)."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print(t(f"  {log_label}: Playwright nicht installiert (siehe requirements.txt / "
                "'python3 -m playwright install chromium')",
                f"  {log_label}: Playwright not installed (see requirements.txt / "
                "'python3 -m playwright install chromium')"))
        return []
    try:
        import pandas as pd
    except ImportError:
        print(t(f"  {log_label}: pandas/openpyxl fehlt", f"  {log_label}: pandas/openpyxl missing"))
        return []

    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        xlsx_path = Path(tmpdir) / "export.xlsx"
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                               "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
                    viewport={"width": 1400, "height": 900},
                    accept_downloads=True,
                )
                page = context.new_page()
                page.goto(_FLI_TSIS_URL, timeout=30000, wait_until="networkidle")
                page.wait_for_timeout(2000)
                page.click("text=Ausgewählte Tierseuchen", timeout=8000)
                page.wait_for_timeout(1500)
                page.click(f"text={disease_navigator_text}", timeout=8000)
                page.wait_for_timeout(3000)
                page.click("text=Übersicht >> nth=0", timeout=5000)
                page.wait_for_timeout(1000)
                page.click("text=Auflistung der Einzelfälle", timeout=5000)
                page.wait_for_timeout(3000)
                page.click("text=Mehr", timeout=5000)
                page.wait_for_timeout(1000)
                page.hover("text=Exportieren >> nth=1", timeout=5000)
                page.wait_for_timeout(1000)
                with page.expect_download(timeout=30000) as dl_info:
                    page.click("text=Alle Tabellen", timeout=5000)
                dl_info.value.save_as(str(xlsx_path))
                browser.close()
        except Exception as e:
            print(t(f"  {log_label}: nicht erreichbar ({e})", f"  {log_label}: not reachable ({e})"))
            return []

        try:
            df = pd.read_excel(xlsx_path, sheet_name="Auflistung der Einzelfälle")
        except Exception as e:
            print(t(f"  {log_label}: Excel-Fehler ({e})", f"  {log_label}: Excel error ({e})"))
            return []
        df = df.where(df.notna(), None)
        return df.to_dict("records")


def _insert_fli_rows(conn: sqlite3.Connection, rows: list[dict], source: str,
                      disease: str, slug: str) -> int:
    now = datetime.now(timezone.utc).isoformat()
    inserted = 0
    for row in rows:
        oid = row.get("Seuchenobjektkennung")
        kreis = row.get("Kreis")
        date_raw = row.get("Datum Feststellung")
        date_ = date_raw.strftime("%Y-%m-%d") if hasattr(date_raw, "strftime") else None
        kulturform = row.get("Kulturform") or "?"
        tierart = row.get("Tierart")
        title = f"{disease} ({kulturform}" + (f", {tierart}" if tierart else "") + f") — {kreis or '?'}"
        url = f"{_FLI_TSIS_URL}#{slug}-{oid}"
        try:
            conn.execute("""
                INSERT OR IGNORE INTO outbreak_events
                (source, disease, syndrome_slug, country, country_iso, region,
                 date_reported, date_start, severity, url, title, fetched_at, person)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (source, disease, slug, "Deutschland", "DE",
                  kreis, date_, date_, "medium", url, title, now, _OWN_PERSON_ID))
            if conn.execute("SELECT changes()").fetchone()[0]:
                inserted += 1
        except DB_ERRORS as e:
            print(t(f"  DB-Fehler: {e}", f"  DB error: {e}"))

    conn.commit()
    return inserted


def fetch_fli_wnv(conn: sqlite3.Connection) -> int:
    """FLI West-Nil-Virus-Fallhistorie (Voegel + Pferde) → outbreak_events.

    Vollstaendige Fallhistorie seit 2006 (Landkreis-genau, kein Punkt-
    koordinate) per Excel-Export -- s. Modul-Kommentar oben.
    """
    rows = _fetch_fli_tsis_export("West-Nil-Virus", "FLI WNV")
    if not rows:
        return 0
    return _insert_fli_rows(conn, rows, "fli_wnv", "West-Nil-Virus", "west_nile")


def fetch_fli_avian_influenza(conn: sqlite3.Connection) -> int:
    """FLI Aviaere-Influenza-Fallhistorie (Voegel + Gefluegel) → outbreak_events.

    Vollstaendige Fallhistorie seit 2006 (Landkreis-genau, kein Punkt-
    koordinate) per Excel-Export -- s. Modul-Kommentar oben. Die
    Kartenansicht dieser Tierseuche zeigt standardmaessig NUR "Aktive
    Faelle" (aktuell 1-2 bundesweit) statt der vollen ~1800 Faelle/Jahr --
    deshalb ist der Tabellen-Export hier besonders wichtig, nicht nur eine
    Praezisions-Verbesserung wie bei WNV.
    """
    rows = _fetch_fli_tsis_export("Aviäre Influenza", "FLI Aviäre Influenza")
    if not rows:
        return 0
    return _insert_fli_rows(conn, rows, "fli_avian_influenza", "Aviäre Influenza", "aviaere_influenza")


# ── Main ──────────────────────────────────────────────────────────────────────

_ALL_SOURCES_DEFAULT = [
    "who",              # WHO DON — JSON REST API (who.int/api/news/diseaseoutbreaknews)
    "ecdc",             # ECDC — Taxonomy-Feeds (ecdc.europa.eu/en/taxonomy/term/*/feed)
    "rki",              # RKI SurvStat OLAP/MDX-SOAP — tools.rki.de (repariert)
    "grippeweb",        # RKI GrippeWeb — ARE/ILI-Hintergrundinzidenz (GitHub TSV)
    "are_konsultation", # RKI ARE-Konsultationsinzidenz — AGI-Sentinel, pro Bundesland (GitHub TSV)
    "lgl",              # LGL Bayern FSME — statische Kreisliste als Fallback
    "efsa",             # EFSA — RSS-Feed, live verifiziert (30 aktuelle Eintraege)
    "gdelt",            # GDELT DOC 2.0 API — offen, aber strikt rate-limitiert
                        # (s. fetch_gdelt-Docstring); ein 429 in einem Lauf ist normal
    "wahis",            # WAHIS/WOAH Tierseuchen (Nutztiere) — ueber die
                        # EcoHealth-Alliance-Spiegelung auf DoltHub (der
                        # offizielle Endpunkt bleibt per Cloudflare blockiert,
                        # s. Kommentar bei _WAHISDB_API); Datensatz eingefroren
                        # bei 2024-03-22, s. dortiger Docstring
    "wahis_wild",       # Dieselbe Quelle, Wildtier-Ausbrueche (is_wild=1)
    "who_emro",         # WHO EMRO — neue Feed-URLs (emro.who.int/health-topics/...)
    "who_afro",         # WHO AFRO — neue Feed-URL-Kandidaten (afro.who.int/feed)
    "who_paho",         # WHO PAHO — erste URL (node/feed) 404, zweite (rss.xml) laeuft;
                        # per echtem Testlauf verifiziert (5 neue Eintraege)
    "who_searo",        # WHO SEARO — alte Alt-Subdomain (searo.who.int) tot,
                        # nutzt jetzt WHOs generische News-API (sf_provider),
                        # s. _fetch_who_region_news-Kommentar
    "who_euro",         # WHO EURO — dieselbe News-API, mit Region-GUID-Filter
    "who_wpro",         # WHO WPRO — dieselbe News-API
    "cdc_travel",       # CDC Travel Notices — neue URL /travel/rss/notices.xml
    "healthmap",        # HealthMap — kein RSS mehr, aber getAlerts.php (die
                        # von der Karte selbst genutzte Daten-API) offen und
                        # funktionsfaehig, s. fetch_healthmap-Docstring
    "eurosurveillance", # Eurosurveillance — neue URL ?TRACK=RSS
    # "reliefweb",      # DEAD seit 1.11.2025: appname jetzt vorab-
                        # genehmigungspflichtig (HTTP 403 "not using an
                        # approved appname"), erfordert manuelle Registrierung
                        # durch den Nutzer, s. fetch_reliefweb-Docstring
    "crm",              # CRM Reisemedizin — Domain-Umzug www.crm.de -> crm.de
                        # (www. timeoutete komplett, auch im echten Browser)
    "fli_wnv",          # FLI West-Nil-Virus (Voegel+Pferde) — Excel-Export
                        # per Playwright, s. dortiger Modul-Kommentar
    "fli_avian_influenza", # FLI Aviaere Influenza (Voegel+Gefluegel) — dieselbe
                        # Export-Methode; Kartenansicht allein zeigt nur
                        # "Aktive Faelle", s. fetch_fli_avian_influenza-Docstring
    "endemic",          # statische Endemie-Referenzdaten — immer verfügbar
]

# promedmail: DEAD seit 14.07.2023, absichtlich (Login-Abo-Modell explizit
# gegen Scraping), s. fetch_promedmail-Docstring -- kein technischer Fix
# gesucht/moeglich. reliefweb: s. Kommentar oben, ebenfalls kein
# automatisierter Fix moeglich, aber ueber --sources weiterhin waehlbar
# (z.B. nach manueller appname-Registrierung durch den Nutzer).
_ALL_SOURCES_CHOICES = _ALL_SOURCES_DEFAULT + ["promedmail", "reliefweb"]

_FETCHERS = {
    "who":             (fetch_who_don,          "WHO DON"),
    "ecdc":            (fetch_ecdc,             "ECDC NewsRoom"),
    "efsa":            (fetch_efsa,             "EFSA (Zoonosen/Lebensmittelsicherheit)"),
    "gdelt":           (fetch_gdelt,            "GDELT (globale Nachrichten-Ereignisse)"),
    "promedmail":      (fetch_promedmail,        "ProMED"),
    "rki":             (fetch_rki_survstat,      "RKI SurvStat"),
    "grippeweb":       (fetch_grippeweb,         "RKI GrippeWeb"),
    "are_konsultation":(fetch_are_konsultationsinzidenz, "RKI ARE-Konsultationsinzidenz"),
    "lgl":             (fetch_lgl_fsme,          "LGL Bayern FSME"),
    "wahis":           (fetch_wahis,             "WAHIS/WOAH (Tierseuchen, Nutztiere)"),
    "wahis_wild":      (fetch_wahis_wild,        "WAHIS/WOAH (Tierseuchen, Wildtiere)"),
    "who_emro":        (fetch_who_emro,          "WHO EMRO"),
    "who_afro":        (fetch_who_afro,          "WHO AFRO"),
    "who_paho":        (fetch_who_paho,          "WHO PAHO (Amerika)"),
    "who_searo":       (fetch_who_searo,         "WHO SEARO (Südostasien)"),
    "who_euro":        (fetch_who_euro,          "WHO EURO"),
    "who_wpro":        (fetch_who_wpro,          "WHO WPRO (Westpazifik)"),
    "cdc_travel":      (fetch_cdc_travel,        "CDC Travel Notices"),
    "healthmap":       (fetch_healthmap,         "HealthMap"),
    "eurosurveillance":(fetch_eurosurveillance,  "Eurosurveillance"),
    "reliefweb":       (fetch_reliefweb,         "ReliefWeb (UN OCHA)"),
    "crm":             (fetch_crm,               "CRM Reisemedizin"),
    "fli_wnv":         (fetch_fli_wnv,           "FLI West-Nil-Virus (Landkreise)"),
    "fli_avian_influenza": (fetch_fli_avian_influenza, "FLI Aviäre Influenza (Landkreise)"),
    "endemic":         (import_endemic_reference,"Endemie-Referenz"),
}

# Quellen mit rollierendem Zeitfenster (s. fetch_grippeweb docstring) statt
# vollständiger Historie beim normalen Lauf — via --full-history explizit
# einmalig komplett nachladbar.
_FULL_HISTORY_CAPABLE = {
    "grippeweb":        fetch_grippeweb,
    "are_konsultation": fetch_are_konsultationsinzidenz,
    "rki":              fetch_rki_survstat,
}


def _backfill_missing_slugs(conn: sqlite3.Connection) -> int:
    """Bestehende Zeilen ohne syndrome_slug erneut gegen DISEASE_SLUG_MAP prüfen.

    DISEASE_SLUG_MAP wächst mit jedem neu aufgenommenen Erreger — Zeilen, die
    beim ursprünglichen Import noch keinen passenden Eintrag hatten (z.B.
    ältere who_don-Meldungen zu Pest/Milzbrand, die vor den entsprechenden
    Syndrom-Dateien importiert wurden), sollen nicht dauerhaft ohne
    Syndromzuordnung bleiben, ohne dass das manuell nachgestoßen werden muss.
    """
    rows = conn.execute(
        "SELECT rowid, title FROM outbreak_events WHERE syndrome_slug IS NULL"
    ).fetchall()
    updated = 0
    for rowid, title in rows:
        slug = _slug_from_disease(title or "")
        if slug:
            conn.execute(
                "UPDATE outbreak_events SET syndrome_slug = ? WHERE rowid = ?",
                (slug, rowid),
            )
            updated += 1
    return updated


def run(conn: sqlite3.Connection = None,
        sources: list[str] = None,
        dry_run: bool = False,
        lang: str | None = None) -> ImportResult:
    """Ausbruchsdaten importieren."""
    if lang:
        set_lang(lang)
    sources = sources or _ALL_SOURCES_DEFAULT
    close = conn is None
    if conn is None:
        conn = open_db()

    total = 0
    if not dry_run:
        for key in sources:
            if key not in _FETCHERS:
                print(t(f"  Unbekannte Quelle: {key}", f"  Unknown source: {key}"))
                continue
            fn, label = _FETCHERS[key]
            try:
                n = fn(conn)
                print(t(f"    {label}: {n} neue Einträge", f"    {label}: {n} new entries"))
                total += n
            except Exception as e:
                print(t(f"    {label}: Fehler — {e}", f"    {label}: error — {e}"))
            time.sleep(0.5)
    else:
        print(t(f"  [dry-run] Würde abfragen: {', '.join(sources)}",
                f"  [dry-run] Would query: {', '.join(sources)}"))

    if not dry_run:
        n_backfilled = _backfill_missing_slugs(conn)
        if n_backfilled:
            print(t(f"    Syndrom-Zuordnung nachgetragen: {n_backfilled} Einträge",
                    f"    Syndrome mapping backfilled: {n_backfilled} entries"))
        # person=None explizit: WHO/ECDC/RKI-Ausbruchsdaten sind nicht
        # personenbezogen (bereits in add-importer-person-override-convention
        # geprueft und bewusst NICHT parametrisiert — s. dortige tasks.md,
        # Punkt 5). OWN_PERSON_ID einzutragen waere hier irrefuehrend.
        log_import(conn, 'outbreak_data', '', total, person=None)
        conn.commit()
    if close:
        conn.close()

    return ImportResult(source="outbreak_data", rows_inserted=total)


def main():
    ap = argparse.ArgumentParser(
        description=(
            "Ausbruchsdaten importieren — WHO (alle 6 Regionen), ECDC, ProMED, "
            "RKI, LGL, WAHIS, CDC Travel, HealthMap, Eurosurveillance, "
            "ReliefWeb, CRM, Endemie-Referenz"
        )
    )
    ap.add_argument("--sources", nargs="+",
                    choices=_ALL_SOURCES_CHOICES,
                    default=_ALL_SOURCES_DEFAULT,
                    help="Quellen (Standard: alle außer promedmail)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--list-sources", action="store_true",
                    help="Alle verfügbaren Quellen auflisten und beenden")
    ap.add_argument("--full-history", action="store_true",
                    help=(
                        "Einmaliger Backfill der GESAMTEN Historie für Quellen mit "
                        "rollierendem Zeitfenster (GrippeWeb seit Saison 2010/11, "
                        "ARE-Konsultationsinzidenz seit Saison 2012/13, RKI SurvStat "
                        "seit Beginn der jeweiligen Meldepflicht z.B. Borreliose seit "
                        "2001) statt nur des Fensters, das der normale Lauf holt. "
                        "Idempotent (INSERT OR IGNORE) — beliebig oft wiederholbar, "
                        "danach reicht wieder ein normaler Lauf für aktuelle Wochen."
                    ))
    add_lang_arg(ap)
    args = ap.parse_args()
    apply_lang_from_args(args)

    if args.list_sources:
        print(t("Verfügbare Quellen:", "Available sources:"))
        for key, (_, label) in _FETCHERS.items():
            default = t(" [Standard]", " [default]") if key in _ALL_SOURCES_DEFAULT else ""
            print(f"  {key:<20} {label}{default}")
        return

    if args.full_history:
        conn = open_db()
        total = 0
        for key, fn in _FULL_HISTORY_CAPABLE.items():
            label = _FETCHERS[key][1]
            print(t(f"{label}: vollständiger Backfill ...",
                    f"{label}: full backfill ..."))
            n = fn(conn, weeks_back=100_000)
            total += n
        conn.close()
        print(t(f"\n{total} neue Einträge importiert.", f"\n{total} new entries imported."))
        return

    print(t("Ausbruchsdaten importieren...", "Importing outbreak data..."))
    result = run(sources=args.sources, dry_run=args.dry_run)
    print(t(f"\nGesamt: {result.rows_inserted} neue Ausbruchsmeldungen importiert",
            f"\nTotal: {result.rows_inserted} new outbreak reports imported"))

    # Statistik: alle Quellen mit Einträgen
    conn = open_db()
    rows = conn.execute(
        "SELECT source, COUNT(*) FROM outbreak_events GROUP BY source ORDER BY source"
    ).fetchall()
    if rows:
        print(t("\nDatenbank-Stand:", "\nDatabase status:"))
        for src, n in rows:
            print(t(f"  {src:<22} {n:>5} Einträge", f"  {src:<22} {n:>5} entries"))
    conn.close()


if __name__ == "__main__":
    main()
