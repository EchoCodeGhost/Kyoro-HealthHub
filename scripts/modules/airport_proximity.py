# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Flughafennähe-Erkennung: strukturelles Standortrisiko unabhängig von Ausbrüchen

@tier        heuristic
@refs        Isaäcson M (1989). Airport malaria: a review. Bulletin of the World Health Organization, 67(6), 737-743. PMID:2699278
             Alenou LD, Etang J (2021). Airport Malaria in Non-Endemic Areas: New Insights into Mosquito Vectors, Case Management and Major Challenges. Microorganisms, 9(10), 2160. doi:10.3390/microorganisms9102160
@relevance.de Erkennt automatisch, ob der aktuelle Wohnort in der Nähe eines großen internationalen
             Flughafens liegt — ein strukturelles, dauerhaftes Risiko für lokal (nicht reiseassoziiert)
             übertragene, mit dem Flugzeug eingeschleppte Erkrankungen wie "Flughafenmalaria". Anders als
             die Ausbruchs-/Endemie-Analyse (analyse_outbreak_exposure.py, analyse_pathogen_exposure.py)
             ist dies KEIN Abgleich gegen konkrete gemeldete Ausbruchsereignisse, sondern eine
             Vortest-Wahrscheinlichkeits-Erhöhung, die unabhängig davon gilt, ob gerade ein Ausbruch
             gemeldet wurde — genau die Lücke, die eine rein reise-/ausbruchsbasierte Anamnese hat
             (Malaria wird ohne Reiseanamnese üblicherweise gar nicht erst in Betracht gezogen).
@relevance.en Automatically detects whether the current home location lies near a major international
             airport — a structural, standing risk factor for locally acquired (non-travel-associated)
             aircraft-imported diseases such as "airport malaria". Unlike the outbreak/endemic analysis
             (analyse_outbreak_exposure.py, analyse_pathogen_exposure.py), this is NOT matched against
             concrete reported outbreak events — it raises pretest probability regardless of whether an
             outbreak has been reported, closing the gap a travel-/outbreak-only history has (malaria is
             often not even considered in practice without a travel history).
@purpose.de  Bestimmt den aktuellen Wohnort aus location_stays (is_home=1) und prüft die Distanz zum
             nächstgelegenen großen internationalen Flughafen aus einer kuratierten Referenzliste.
             Liefert bei Unterschreitung eines Radius-Schwellwerts einen Dauerrisiko-Eintrag im selben
             Format wie known_risk_exposures.json, zur Zusammenführung mit den manuell gepflegten
             Einträgen im Ausbruchs-Expositionsbericht.
@purpose.en  Determines the current home location from location_stays (is_home=1) and checks the
             distance to the nearest major international airport from a curated reference list. Below a
             radius threshold, returns a standing-risk entry in the same shape as known_risk_exposures.json,
             for merging with the manually curated entries in the outbreak exposure report.
@method.de   Haversine-Distanz zum nächstgelegenen Flughafen in MAJOR_INTERNATIONAL_AIRPORTS (kuratierte,
             nicht erschöpfende Liste großer internationaler Hubs, Schwerpunkt Europa/Deutschland).
             Zwei Radius-Stufen: <5 km = "hoch" (klassische "Airport-Malaria"-Zone, Isaäcson 1989),
             5-15 km = "mittel" (weiterer Zone, Gepäck-/Fahrzeug-Vektor statt Flugzeugkabine).
@method.en   Haversine distance to the nearest airport in MAJOR_INTERNATIONAL_AIRPORTS (curated, non-
             exhaustive list of major international hubs, weighted toward Europe/Germany). Two radius
             tiers: <5 km = "high" (classic "airport malaria" zone per Isaäcson 1989), 5-15 km = "medium"
             (wider zone, baggage/vehicle vector rather than aircraft cabin).
@limits.de   Flughafenliste ist eine kuratierte Auswahl großer internationaler Hubs (Schwerpunkt Europa),
             keine vollständige Weltliste — ein fehlender Flughafen führt zu einem False Negative, nicht
             zu einer falschen Warnung. Radius-Schwellen (5/15 km) sind eine grobe, projektinterne
             Heuristik ohne formale epidemiologische Kalibrierung; dokumentierte Fälle liegen laut
             Isaäcson 1989 überwiegend im Nahbereich (wenige km) des Flughafens, Einzelfälle auch weiter
             entfernt (Gepäck-/Fahrzeugtransport der Mücke). Nur Malaria ist für dieses Phänomen gut
             dokumentiert; andere Aedes-/Anopheles-übertragene Erkrankungen (Dengue, Chikungunya, Zika)
             sind über denselben Transportweg theoretisch denkbar, aber nicht in vergleichbarem Maß in der
             Literatur belegt — deshalb hier bewusst nicht mit demselben Konfidenzgrad getaggt.
@limits.en   Airport list is a curated selection of major international hubs (Europe-weighted), not an
             exhaustive world list — a missing airport causes a false negative, not a false alarm. Radius
             thresholds (5/15 km) are a rough, project-internal heuristic without formal epidemiological
             calibration; documented cases per Isaäcson 1989 mostly occur close (a few km) to the
             airport, with isolated cases further away (baggage/vehicle-transported mosquito). Only
             malaria is well documented for this phenomenon; other Aedes-/Anopheles-borne diseases
             (dengue, chikungunya, zika) are theoretically plausible via the same transport route but not
             comparably documented in the literature — deliberately not tagged with the same confidence.
@reads       location_stays, location_stays_geocoded
@writes      keine (reine Berechnungsfunktion, kein DB-Schreibzugriff — der Aufrufer entscheidet, was mit dem Ergebnis geschieht)
@scoring     Zwei Radius-Stufen (Haversine-Distanz Wohnort zu nächstem Flughafen aus
             MAJOR_INTERNATIONAL_AIRPORTS):
               AIRPORT_RADIUS_HOCH_KM   = 5.0 km  -> level "high"   (klassische "Airport-Malaria"-Zone, Isaäcson 1989)
               AIRPORT_RADIUS_MITTEL_KM = 15.0 km -> level "medium" (weitere Zone, Gepäck-/Fahrzeugvektor)
               > 15 km -> kein Treffer, leere Liste
             Rückgabe ist ein einzelner known_risk_exposures-artiger Eintrag (slug "malaria",
             level, description, notes, auto=True), kein numerischer Score — heuristisch,
             keine epidemiologische Validierung der Radius-Schwellen.
@usage
    python3 -c "from modules.airport_proximity import nearest_airport; print(nearest_airport(50.05, 8.57))"
    python3 -c "from modules.db import open_db; from modules.airport_proximity import home_airport_risk_exposures; print(home_airport_risk_exposures(open_db()))"
"""
import math
import sqlite3

# ── Kuratierte Liste großer internationaler Flughäfen ────────────────────────
# (Name, IATA, lat, lon) — Schwerpunkt Europa/Deutschland + globale Hubs mit
# realistischen Interkontinental-/Endemiegebiets-Verbindungen. Nicht erschöpfend,
# s. @limits oben. Koordinaten: Flughafen-Referenzpunkt, keine Landebahn-Präzision.

MAJOR_INTERNATIONAL_AIRPORTS: list[tuple[str, str, float, float]] = [
    # ── Deutschland ───────────────────────────────────────────────────────────
    ("Frankfurt am Main",      "FRA", 50.0379,   8.5622),
    ("München",                "MUC", 48.3538,  11.7861),
    ("Berlin Brandenburg",     "BER", 52.3667,  13.5033),
    ("Düsseldorf",             "DUS", 51.2895,   6.7668),
    ("Hamburg",                "HAM", 53.6304,   9.9882),
    ("Stuttgart",              "STR", 48.6899,   9.2220),
    ("Köln/Bonn",              "CGN", 50.8659,   7.1427),
    ("Nürnberg",               "NUE", 49.4987,  11.0669),
    ("Hannover",               "HAJ", 52.4611,   9.6851),
    ("Leipzig/Halle",          "LEJ", 51.4239,  12.2364),
    # ── Österreich / Schweiz ──────────────────────────────────────────────────
    ("Wien",                   "VIE", 48.1103,  16.5697),
    ("Zürich",                 "ZRH", 47.4647,   8.5492),
    ("Genf",                   "GVA", 46.2381,   6.1090),
    ("Basel/Mulhouse",         "BSL", 47.5896,   7.5299),
    # ── Benelux ───────────────────────────────────────────────────────────────
    ("Amsterdam Schiphol",     "AMS", 52.3105,   4.7683),
    ("Brüssel",                "BRU", 50.9014,   4.4844),
    # ── Frankreich ────────────────────────────────────────────────────────────
    ("Paris Charles de Gaulle","CDG", 49.0097,   2.5479),
    ("Paris Orly",             "ORY", 48.7233,   2.3794),
    ("Lyon",                   "LYS", 45.7256,   5.0811),
    ("Nizza",                  "NCE", 43.6584,   7.2159),
    # ── UK / Irland ───────────────────────────────────────────────────────────
    ("London Heathrow",        "LHR", 51.4700,  -0.4543),
    ("London Gatwick",         "LGW", 51.1481,  -0.1903),
    ("Manchester",             "MAN", 53.3537,  -2.2750),
    ("Dublin",                 "DUB", 53.4213,  -6.2701),
    # ── Iberische Halbinsel ───────────────────────────────────────────────────
    ("Madrid",                 "MAD", 40.4983,  -3.5676),
    ("Barcelona",              "BCN", 41.2971,   2.0785),
    ("Lissabon",               "LIS", 38.7813,  -9.1359),
    # ── Italien ───────────────────────────────────────────────────────────────
    ("Rom Fiumicino",          "FCO", 41.8003,  12.2389),
    ("Mailand Malpensa",       "MXP", 45.6306,   8.7281),
    # ── Skandinavien ──────────────────────────────────────────────────────────
    ("Kopenhagen",             "CPH", 55.6180,  12.6560),
    ("Stockholm Arlanda",      "ARN", 59.6519,  17.9186),
    ("Oslo",                   "OSL", 60.1976,  11.1004),
    ("Helsinki",               "HEL", 60.3172,  24.9633),
    # ── Ost-/Südosteuropa ─────────────────────────────────────────────────────
    ("Warschau",               "WAW", 52.1657,  20.9671),
    ("Prag",                   "PRG", 50.1008,  14.2600),
    ("Budapest",               "BUD", 47.4298,  19.2611),
    ("Bukarest",               "OTP", 44.5711,  26.0850),
    ("Sofia",                  "SOF", 42.6952,  23.4062),
    ("Athen",                  "ATH", 37.9364,  23.9445),
    ("Istanbul",               "IST", 41.2753,  28.7519),
    ("Istanbul Sabiha Gökçen", "SAW", 40.8986,  29.3092),
    # ── Naher Osten ───────────────────────────────────────────────────────────
    ("Dubai",                  "DXB", 25.2532,  55.3657),
    ("Abu Dhabi",              "AUH", 24.4330,  54.6511),
    ("Doha",                   "DOH", 25.2731,  51.6081),
    ("Riad",                   "RUH", 24.9576,  46.6988),
    ("Jeddah",                 "JED", 21.6796,  39.1565),
    ("Tel Aviv",               "TLV", 32.0114,  34.8867),
    # ── Afrika ────────────────────────────────────────────────────────────────
    ("Kairo",                  "CAI", 30.1219,  31.4056),
    ("Casablanca",             "CMN", 33.3675,  -7.5898),
    ("Johannesburg",           "JNB",-26.1392,  28.2460),
    ("Nairobi",                "NBO", -1.3192,  36.9278),
    ("Addis Abeba",            "ADD",  8.9779,  38.7993),
    ("Lagos",                  "LOS",  6.5774,   3.3212),
    ("Accra",                  "ACC",  5.6052,  -0.1668),
    # ── Südasien ──────────────────────────────────────────────────────────────
    ("Mumbai",                 "BOM", 19.0896,  72.8656),
    ("Delhi",                  "DEL", 28.5562,  77.1000),
    ("Colombo",                "CMB",  7.1808,  79.8842),
    # ── Südostasien ───────────────────────────────────────────────────────────
    ("Bangkok Suvarnabhumi",   "BKK", 13.6900, 100.7501),
    ("Singapur Changi",        "SIN",  1.3644, 103.9915),
    ("Kuala Lumpur",           "KUL",  2.7456, 101.7099),
    ("Jakarta",                "CGK", -6.1256, 106.6559),
    ("Manila",                 "MNL", 14.5086, 121.0198),
    ("Ho-Chi-Minh-Stadt",      "SGN", 10.8188, 106.6520),
    # ── Ostasien ──────────────────────────────────────────────────────────────
    ("Hongkong",               "HKG", 22.3080, 113.9185),
    ("Tokio Narita",           "NRT", 35.7720, 140.3929),
    ("Tokio Haneda",           "HND", 35.5494, 139.7798),
    ("Peking",                 "PEK", 40.0799, 116.6031),
    ("Shanghai Pudong",        "PVG", 31.1443, 121.8083),
    ("Seoul Incheon",          "ICN", 37.4602, 126.4407),
    ("Taipeh",                 "TPE", 25.0797, 121.2342),
    # ── Ozeanien ──────────────────────────────────────────────────────────────
    ("Sydney",                 "SYD",-33.9399, 151.1753),
    ("Melbourne",              "MEL",-37.6690, 144.8410),
    ("Auckland",               "AKL",-37.0082, 174.7850),
    # ── Nordamerika ───────────────────────────────────────────────────────────
    ("New York JFK",           "JFK", 40.6413, -73.7781),
    ("Newark",                 "EWR", 40.6895, -74.1745),
    ("Los Angeles",            "LAX", 33.9416,-118.4085),
    ("Chicago O'Hare",         "ORD", 41.9742, -87.9073),
    ("Miami",                  "MIA", 25.7959, -80.2870),
    ("Atlanta",                "ATL", 33.6407, -84.4277),
    ("Washington Dulles",      "IAD", 38.9531, -77.4565),
    ("San Francisco",          "SFO", 37.6213,-122.3790),
    ("Houston",                "IAH", 29.9902, -95.3368),
    ("Toronto",                "YYZ", 43.6777, -79.6248),
    ("Vancouver",              "YVR", 49.1967,-123.1815),
    # ── Lateinamerika ─────────────────────────────────────────────────────────
    ("Mexiko-Stadt",           "MEX", 19.4363, -99.0721),
    ("São Paulo Guarulhos",    "GRU",-23.4356, -46.4731),
    ("Bogotá",                 "BOG",  4.7016, -74.1469),
    ("Lima",                   "LIM",-12.0219, -77.1143),
    ("Santiago de Chile",      "SCL",-33.3930, -70.7858),
    ("Buenos Aires Ezeiza",    "EZE",-34.8222, -58.5358),
    ("Panama-Stadt",           "PTY",  9.0714, -79.3835),
]

AIRPORT_RADIUS_HOCH_KM   = 5.0    # klassische "Airport-Malaria"-Zone (Isaäcson 1989)
AIRPORT_RADIUS_MITTEL_KM = 15.0   # weitere Zone (Gepäck-/Fahrzeugvektor)


def _geo_dist(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Haversine-Distanz in km."""
    r = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2)
    return r * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def nearest_airport(lat: float, lon: float) -> tuple[tuple[str, str, float, float], float] | None:
    """Gibt (Flughafen-Tupel, Distanz in km) für den nächstgelegenen Flughafen zurück."""
    if lat is None or lon is None:
        return None
    best = None
    best_dist = float("inf")
    for airport in MAJOR_INTERNATIONAL_AIRPORTS:
        _, _, a_lat, a_lon = airport
        d = _geo_dist(lat, lon, a_lat, a_lon)
        if d < best_dist:
            best_dist = d
            best = airport
    if best is None:
        return None
    return best, round(best_dist, 1)


def current_home_location(conn: sqlite3.Connection) -> dict | None:
    """Aktuellster Wohnsitz (is_home=1) aus location_stays, mit Geocoding falls vorhanden.

    Bevorzugt einen Eintrag ohne end_ts (noch aktueller Wohnsitz), sonst den
    mit dem jüngsten start_ts.
    """
    row = conn.execute("""
        SELECT ls.lat, ls.lon,
               COALESCE(g.city, ''), COALESCE(g.subregion, ''), COALESCE(g.country, '')
        FROM location_stays ls
        LEFT JOIN location_stays_geocoded g ON g.stay_id = ls.id
        WHERE ls.is_home = 1 AND ls.lat IS NOT NULL AND ls.lon IS NOT NULL
        ORDER BY (ls.end_ts IS NULL) DESC, ls.start_ts DESC
        LIMIT 1
    """).fetchone()
    if not row:
        return None
    lat, lon, city, subregion, country = row
    return {
        "lat": lat, "lon": lon,
        "label": city or subregion or country or f"{lat:.2f},{lon:.2f}",
    }


def home_airport_risk_exposures(conn: sqlite3.Connection) -> list[dict]:
    """Strukturelles Dauerrisiko "Wohnort in Flughafennähe", falls zutreffend.

    Rückgabeformat identisch zu known_risk_exposures.json-Einträgen
    (slug, level, description, notes), plus "auto": True als Herkunftsmarker
    für die Berichtsdarstellung (manuell vs. automatisch erkannt).
    Leere Liste, wenn kein Wohnort bekannt ist oder kein Flughafen im Radius liegt.
    """
    home = current_home_location(conn)
    if not home:
        return []

    result = nearest_airport(home["lat"], home["lon"])
    if not result:
        return []
    (name, iata, _, _), dist_km = result

    if dist_km <= AIRPORT_RADIUS_HOCH_KM:
        level = "high"
    elif dist_km <= AIRPORT_RADIUS_MITTEL_KM:
        level = "medium"
    else:
        return []

    return [{
        "slug": "malaria",
        "level": level,
        "description": (
            f"Wohnort ({home['label']}) liegt {dist_km} km vom internationalen "
            f"Flughafen {name} ({iata}) entfernt — strukturelles \"Flughafenmalaria\"-"
            f"Risiko durch mit dem Flugzeug eingeschleppte Anopheles-Mücken, "
            f"unabhängig von eigener Reiseanamnese."
        ),
        "notes": (
            "Automatisch erkannt aus location_stays (is_home=1) + Flughafen-Referenzliste, "
            "s. modules/airport_proximity.py. Nicht manuell in known_risk_exposures.json "
            "eingetragen — Isaäcson 1989 (Bull World Health Organ), keine epidemiologische "
            "Validierung der Radius-Schwellen."
        ),
        "auto": True,
    }]
