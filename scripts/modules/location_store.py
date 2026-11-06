# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
location_store.py — Zentrale GPS/Ortsdaten-Registrierung und Policy-Enforcement

@tier        infrastructure
@purpose.de  Zentrale Speicherung und Abfrage von GPS-Koordinaten und Ortsdaten.
             Implementiert die location-privacy-Policy aus location_privacy.json.
             Jede GPS-Koordinate wird nur hier gespeichert, nie in health.db oder medicine.db.
@purpose.en  Central storage and querying of GPS coordinates and location data.
             Implements the location-privacy policy from location_privacy.json.
             All GPS coordinates are stored here only, never in health.db or medicine.db.
@method.de   resolve_policy liefert die geltende Policy für einen Importer/Dateityp.
             record speichert einen Ort im Registry (mit Precision-Anwendung und Zonen).
             region_of liefert den ISO-3166-Code der Region (weltweit, offline).
             location_token generiert deterministische Tokens für Zellen.
             for_prompt und filter_prompt_text setzen die Outbound-Regeln durch.
@method.en   resolve_policy returns the applicable policy for an importer/file type.
             record stores a location in the registry (applying precision and zones).
             region_of returns the ISO 3166 region code (worldwide, offline).
             location_token generates deterministic tokens for cells.
             for_prompt and filter_prompt_text enforce the outbound rules.
@reads       location.db, location_privacy.json, identity.db (für Salt)
@writes      location.db (INSERT OR IGNORE)
@limits.de   Keine Speicherung ohne gültige Policy. Precision wird IMMER vor dem
             Schreiben angewendet und ist irreversibel. Keine echten Daten in Tests.
@limits.en   No storage without valid policy. Precision is ALWAYS applied before
             writing and is irreversible. No real data in tests.

@relevance.de  Kernmodul für Ortsdaten-Privatsphäre, essentiell für alle Importer
@relevance.en  Core module for location privacy, essential for all importers
@usage
    from modules.location_store import resolve_policy, record, file_sha256
    from modules.location_store import location_token, for_prompt, filter_prompt_text
    from modules.location_store import for_external_api, get_caller_name
    
    # Policy abfragen
    policy = resolve_policy("import_skin", ".jpg")
    
    # Ort speichern (im Importer)
    record(
        importer="import_skin",
        file_type=".jpg",
        lat=48.123456,
        lon=11.543210,
        ts="2024-01-15T10:30:00Z",
        date="2024-01-15",
        original_sha256=file_sha256("/path/to/original.jpg"),
        stored_sha256=file_sha256("/path/to/stored.jpg"),
        source_file="imports/skin/photo.jpg",
        ref_db="medicine",
        ref_table="imaging_files",
        ref_id=123,
        person=person_id
    )
    
    # Text für Cloud-Anbieter filtern
    filtered_text = filter_prompt_text("Befund bei 48.12345, 11.54321", "analyse_synthesis")
    
    # Koordinaten für externe API
    lat_rounded, lon_rounded = for_external_api(48.123456, 11.543210)
"""

import hashlib
import hmac
import json
import re
import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from health_config import Config
from modules.db import DB_ERRORS, open_location_db
from modules.i18n import t

# Template-Muster für Platzhalter
COORDINATE_PLACEHOLDER = t("[ORT_ENTFERNT]", "[LOCATION_REDACTED]")
LOCATION_TOKEN_PREFIX = "LOC-"


def _load_location_privacy() -> dict:
    """Lädt die location_privacy-Konfiguration. Gibt {} zurück wenn fehlend."""
    cfg = Config()
    return cfg.location_privacy


def _get_zones_config() -> dict:
    """Gibt die Zonen-Konfiguration zurück."""
    privacy_cfg = _load_location_privacy()
    return privacy_cfg.get("zones", {})


# Konfigurierte Orte ohne Zonen-Mittelpunkt nur einmal je Lauf melden
_missing_centres_warned = False
_ZIP_TOWN = re.compile(r"(?:D[-\s])?\d{5}\s+([^,;\n]+)")


def _norm_place(name: str) -> str:
    return " ".join(str(name).split()).casefold()


def _personal_places() -> tuple[list, list[str], tuple[float, float] | None]:
    """Liest patient_places, patient_addresses und die Wohnposition aus der Konfiguration."""
    cfg = Config()
    privacy_check = cfg._cfg.get("privacy_check", {}) or {}
    places = list(privacy_check.get("patient_places", []) or [])
    addresses = [str(a) for a in privacy_check.get("patient_addresses", []) or [] if str(a).strip()]
    location = cfg._cfg.get("location", {}) or {}
    home = None
    if location.get("lat") is not None and location.get("lon") is not None:
        try:
            home = (float(location["lat"]), float(location["lon"]))
        except (TypeError, ValueError):
            home = None
    return places, addresses, home


def _point(lat, lon) -> tuple[float, float] | None:
    try:
        return float(lat), float(lon)
    except (TypeError, ValueError):
        return None


def _get_centre_coordinates() -> list[tuple[float, float]]:
    """Lädt alle Zonen-Mittelpunkte aus der Konfiguration (nur im Speicher).

    Mittelpunkte kommen aus:
    1. zones.centres in location_privacy.json: Koordinaten je Ortsname
    2. Einträgen in privacy_check.patient_places, die selbst lat/lon haben
    3. der Wohnposition (location.lat/lon in health_config.json)

    Orte aus privacy_check.patient_places und Adressen aus
    privacy_check.patient_addresses (Adresse oder Ort hinter der PLZ) ohne
    Eintrag in zones.centres bekommen keine Zone; das wird einmal je Lauf
    gemeldet, nur mit Anzahl. Es gibt keine Online-Geokodierung.

    Returns:
        Liste von (lat, lon) Tuples
    """
    global _missing_centres_warned
    zones_cfg = _get_zones_config()
    centres: list[tuple[float, float]] = []
    named: set[str] = set()

    invalid = 0
    for name, data in (zones_cfg.get("centres") or {}).items():
        if str(name).startswith("_") or not isinstance(data, dict):
            continue
        point = _point(data.get("lat"), data.get("lon"))
        if point is None:
            invalid += 1
            continue
        centres.append(point)
        named.add(_norm_place(name))
    if invalid:
        warnings.warn(
            t(f"{invalid} Zonen-Mittelpunkt(e) in zones.centres ohne gültige Koordinaten — übersprungen.",
              f"{invalid} zone centre(s) in zones.centres without valid coordinates — skipped."))

    places, addresses, home = _personal_places()
    missing = 0
    for place in places:
        if isinstance(place, dict):
            # 0.0 ist eine gültige Koordinate, daher kein "or"
            lat = place.get("lat") if place.get("lat") is not None else place.get("latitude")
            lon = place.get("lon") if place.get("lon") is not None else place.get("longitude")
            point = _point(lat, lon)
            if point is not None:
                centres.append(point)
                continue
            name = place.get("name", "")
        else:
            name = place
        if _norm_place(name) not in named:
            missing += 1
    for address in addresses:
        keys = {_norm_place(address)} | {_norm_place(m.group(1)) for m in _ZIP_TOWN.finditer(address)}
        if not keys & named:
            missing += 1
    if missing and not _missing_centres_warned:
        _missing_centres_warned = True
        warnings.warn(
            t(f"{missing} konfigurierte(r) Ort(e) ohne Koordinaten in zones.centres — "
              f"dort gilt keine Privatsphäre-Zone.",
              f"{missing} configured place(s) without coordinates in zones.centres — "
              f"no privacy zone applies there."))

    if home is not None:
        centres.append(home)

    return centres


def _is_in_zone(lat: float, lon: float, centre_lat: float, centre_lon: float, radius_m: float) -> bool:
    """Prüft ob ein Punkt innerhalb des Radius um ein Zentrum liegt.
    
    Nutzt die Haversine-Formel für die Entfernung auf einer Kugel (Erde).
    
    Args:
        lat: Breitengrad des Punkts
        lon: Längengrad des Punkts
        centre_lat: Breitengrad des Zentrums
        centre_lon: Längengrad des Zentrums
        radius_m: Radius in Metern
    
    Returns:
        True wenn der Punkt innerhalb des Radius liegt
    """
    from math import radians, sin, cos, sqrt, asin
    
    # Haversine-Formel
    lat1, lon1 = radians(lat), radians(lon)
    lat2, lon2 = radians(centre_lat), radians(centre_lon)
    
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    
    a = sin(dlat / 2)**2 + cos(lat1) * cos(lat2) * sin(dlon / 2)**2
    c = 2 * asin(sqrt(a))
    
    # Erdradius in Metern
    R = 6371000.0
    distance_m = R * c
    
    return distance_m <= radius_m


_ZONE_INSIDE_MODES = ("hide", "coarsen")
_no_salt_warned = False


def _shifted_centre(lat: float, lon: float, radius_m: float) -> tuple[float, float]:
    """Verschiebt einen Zonen-Mittelpunkt fest, aber nicht vorhersagbar.

    Ohne Verschiebung verrät der Rand, an dem Tracks abgeschnitten werden,
    über viele Tracks den Kreis und damit den Mittelpunkt. Die Verschiebung
    (Richtung und Abstand bis radius_m/2, gleichverteilt in der Kreisfläche)
    kommt aus einem HMAC mit dem Salz aus identity.db: bei jedem Lauf gleich,
    ohne das Salz nicht nachrechenbar. Der echte Mittelpunkt liegt damit
    immer mindestens radius_m/2 innerhalb der Zone. Ohne Salz keine
    Verschiebung (einmalige Warnung).
    """
    global _no_salt_warned
    import math
    salt = _get_pseudonym_salt()
    if not salt:
        if not _no_salt_warned:
            _no_salt_warned = True
            warnings.warn(
                t("Kein Salz in identity.db — Privatsphäre-Zonen ohne Verschiebung des Mittelpunkts.",
                  "No salt in identity.db — privacy zones without shifted centre."))
        return lat, lon
    digest = hmac.new(salt.encode("utf-8"), f"zone|{lat:.5f}|{lon:.5f}".encode("utf-8"),
                      hashlib.sha256).digest()
    angle = int.from_bytes(digest[0:4], "big") / 2**32 * 2 * math.pi
    dist = math.sqrt(int.from_bytes(digest[4:8], "big") / 2**32) * radius_m / 2
    dlat = dist * math.cos(angle) / 111_320.0
    dlon = dist * math.sin(angle) / (111_320.0 * max(math.cos(math.radians(lat)), 1e-6))
    return lat + dlat, lon + dlon


def _zone_settings(zones_cfg: dict) -> tuple[int, float, str]:
    """(zone_precision, radius_m, inside) mit Standardwerten 2, 500, "hide"."""
    inside = zones_cfg.get("inside", "hide")
    if inside not in _ZONE_INSIDE_MODES:
        warnings.warn(
            t(f"Unbekannter Wert für zones.inside ({inside!r}) — verwende \"hide\".",
              f"Unknown value for zones.inside ({inside!r}) — using \"hide\"."))
        inside = "hide"
    return int(zones_cfg.get("zone_precision", 2)), float(zones_cfg.get("radius_m", 500)), inside


def zone_centres(zones_cfg: dict | None = None) -> list[tuple[float, float]]:
    """Verschobene Zonen-Mittelpunkte (nur im Speicher, nie gespeichert)."""
    if zones_cfg is None:
        zones_cfg = _get_zones_config()
    _, radius_m, _ = _zone_settings(zones_cfg)
    return [_shifted_centre(c_lat, c_lon, radius_m) for c_lat, c_lon in _get_centre_coordinates()]


def in_zone(lat: float, lon: float, centres: list[tuple[float, float]], radius_m: float) -> bool:
    """True, wenn der Punkt in einer der (verschobenen) Zonen liegt."""
    return any(_is_in_zone(lat, lon, c_lat, c_lon, radius_m) for c_lat, c_lon in centres)


def _zone_action(lat: float, lon: float, precision: int, zones_cfg: dict) -> str | None:
    """Was eine Privatsphäre-Zone mit dem Punkt macht.

    Returns:
        None (keine Zone betroffen), "hide" (nicht speichern) oder
        "coarsen" (mit zone_precision speichern). Zonen gelten nur für
        Quellen, die feiner als zone_precision speichern.
    """
    if not zones_cfg.get("enabled", True):
        return None
    zone_precision, radius_m, inside = _zone_settings(zones_cfg)
    if precision <= zone_precision:
        return None
    if in_zone(lat, lon, zone_centres(zones_cfg), radius_m):
        return inside
    return None


def resolve_policy(importer: str, file_type: str | None = None) -> dict:
    """Ermittelt die geltende Location-Policy für einen Importer und Dateityp.
    
    Auflösungsreihenfolge:
    1. importer + file_type
    2. importer + "*"
    3. default
    
    Args:
        importer: Name des Importers (z.B. "import_skin")
        file_type: Dateityp mit Punkt (z.B. ".jpg", ".pdf") oder None
    
    Returns:
        Policy-Dict mit Keys: store, precision, oder anderen Konfigurationswerten.
        Bei fehlender Konfiguration: {"store": "none"}
    """
    privacy_cfg = _load_location_privacy()
    
    if not privacy_cfg:
        # Keine Konfiguration → store nothing (sicherer Default)
        return {"store": "none"}
    
    importers_cfg = privacy_cfg.get("importers", {})
    
    # 1. Versuche importer + file_type
    if file_type and importer in importers_cfg:
        importer_cfg = importers_cfg[importer]
        if file_type in importer_cfg:
            return importer_cfg[file_type]
    
    # 2. Versuche importer + "*"
    if importer in importers_cfg:
        importer_cfg = importers_cfg[importer]
        if "*" in importer_cfg:
            return importer_cfg["*"]
    
    # 3. Default
    default_cfg = privacy_cfg.get("default", {})
    if default_cfg:
        return default_cfg
    
    # Fallback: store nothing
    return {"store": "none"}


def round_coords(lat: float, lon: float, precision: int) -> tuple[float, float]:
    """Rundet Koordinaten auf die angegebene Präzision.
    
    Args:
        lat: Breitengrad
        lon: Längengrad
        precision: Anzahl der Dezimalstellen (0-5)
    
    Returns:
        (lat_rounded, lon_rounded)
    """
    if precision < 0:
        precision = 0
    if precision > 5:
        precision = 5
    
    return round(lat, precision), round(lon, precision)


def file_sha256(filepath: str | Path) -> str:
    """Berechnet den SHA-256 Hash einer Datei.
    
    Args:
        filepath: Pfad zur Datei
    
    Returns:
        SHA-256 Hash als Hex-String, oder leer wenn Datei nicht lesbar
    """
    path = Path(filepath)
    if not path.exists():
        return ""
    
    sha256_hash = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            # In Blöcken lesen für große Dateien
            for chunk in iter(lambda: f.read(8192), b""):
                sha256_hash.update(chunk)
        return sha256_hash.hexdigest()
    except (IOError, OSError):
        return ""


def region_of(lat: float, lon: float) -> str:
    """ISO-3166-Code der ersten Verwaltungsebene am Punkt, weltweit und offline.

    Liefert z.B. "DE-BY", "ES-GC" oder "US-HI"; den Ländercode, wenn die
    Einheit keinen gültigen Unterteilungs-Code hat; "XX" bei ungültiger
    Eingabe oder offenem Meer (mehr als 5 km von jeder Einheit).

    @limits.de   Natural-Earth-Umrisse, auf ~2 km vereinfacht: Grenzstädte können
                 der Nachbareinheit zugeordnet werden. De-facto-Grenzen; umstrittene
                 Gebiete folgen dieser Darstellung. Kleine Einheiten (Stadtstaaten,
                 Paris) entsprechen fast dem Ort.
    @limits.en   Natural Earth outlines simplified to ~2 km: border towns can be
                 assigned to the neighbouring unit. De-facto boundaries; disputed
                 areas follow that depiction. Small units (city states, Paris)
                 nearly equal the town.

    Args:
        lat: Breitengrad
        lon: Längengrad

    Returns:
        ISO-3166-2-Code, ISO-3166-1-Ländercode oder "XX"
    """
    from modules.region_lookup import lookup
    return lookup(lat, lon)


def region_name(code: str) -> str:
    """Anzeigename einer Region in der aktiven Sprache; unbekannte Codes unverändert.

    Args:
        code: Code aus region_of (z.B. "DE-BY")

    Returns:
        Name (z.B. "Bayern" / "Bavaria") oder der Code selbst
    """
    from modules.region_lookup import unit_info
    info = unit_info(code)
    if info is None:
        return code
    return t(info["name_de"], info["name_en"])


def _cell_area_km2(lat: float, precision: int) -> float:
    """Fläche einer Rasterzelle bei precision Nachkommastellen am Breitengrad lat."""
    from math import cos, radians
    step_km = 111.32 * 10.0 ** (-precision)
    return step_km * step_km * max(cos(radians(lat)), 0.0)


def stored_region(lat, lon, precision: int | None) -> str:
    """Region, wie sie im Register gespeichert wird (D4).

    Die Region wird aus dem übergebenen (möglichst unrundeten) Punkt bestimmt.
    Ist die Einheit kleiner als die Rasterzelle der gespeicherten Präzision,
    wird nur der Ländercode gespeichert, damit die Region nie mehr verrät als
    die gespeicherten Koordinaten. Ohne precision (store: "region") gilt die
    Region unverändert.

    Args:
        lat: Breitengrad
        lon: Längengrad
        precision: gespeicherte Präzision, None bei reiner Regionsspeicherung

    Returns:
        Region-Code für die Spalte location_registry.region
    """
    code = region_of(lat, lon)
    if precision is None or "-" not in code:
        return code
    from modules.region_lookup import unit_info
    info = unit_info(code)
    if info is not None and info["area_km2"] < _cell_area_km2(float(lat), int(precision)):
        return info["country"]
    return code


def _get_pseudonym_salt() -> str:
    """Liest den Pseudonym-Salt aus identity.db (Tabelle pseudonym_salt).

    Nur lesen: den Salt legt identity_resolver beim ersten Pseudonym an.
    Der Pfad wird bei jedem Aufruf aus health_config.KYORO_CONFIG_DIR
    gebildet, damit Instanz-Konfigurationen und Tests greifen.

    Returns:
        Salt als Hex-String, oder "" falls identity.db/Salt fehlt
    """
    import sqlite3
    import health_config
    path = Path(health_config.KYORO_CONFIG_DIR) / "identity.db"
    if not path.exists():
        return ""
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        try:
            row = conn.execute(
                "SELECT salt_hex FROM pseudonym_salt WHERE id = 1"
            ).fetchone()
        finally:
            conn.close()
    except sqlite3.Error:
        return ""
    return row[0] if row and row[0] else ""


def location_token(lat: float, lon: float, precision: int) -> str | None:
    """Generiert ein deterministisches Location-Token für eine Raster-Zelle.

    Token-Format: LOC- + erste 8 Hex-Zeichen von
    HMAC-SHA256(salt, "<lat>|<lon>|<precision>")

    Gleiche Zelle → gleicher Token. Ohne Salt aus identity.db gibt es KEIN
    Token (None): ein ungesalzener Hash über ein Raster ließe sich durch
    Durchprobieren aller Zellen umkehren.

    Args:
        lat: Breitengrad
        lon: Längengrad
        precision: Präzision (0-5), auf die vorher gerundet wird

    Returns:
        Location-Token, oder None wenn kein Salt verfügbar ist
    """
    salt = _get_pseudonym_salt()
    if not salt:
        return None

    lat_rounded, lon_rounded = round_coords(lat, lon, precision)
    message = f"{lat_rounded}|{lon_rounded}|{precision}"
    token = hmac.new(
        salt.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()[:8]
    return f"{LOCATION_TOKEN_PREFIX}{token}"


def record(
    importer: str,
    file_type: str | None,
    lat: float,
    lon: float,
    ts: str | None,
    date: str,
    original_sha256: str | None = None,
    stored_sha256: str | None = None,
    source_file: str | None = None,
    ref_db: str | None = None,
    ref_table: str | None = None,
    ref_id: int | None = None,
    person: str | None = None,
    migrated_from: str | None = None,
) -> bool:
    """Speichert einen Ort im Location-Registry.
    
    WENDET die Policy-Präzision AN VOR DEM SCHREIBEN an.
    Privatsphäre-Zonen: Punkte in einer Zone werden weggelassen
    (zones.inside "hide", Standard) oder mit zone_precision gespeichert
    ("coarsen").
    Die Region (region_of) wird aus dem ungerundeten Punkt bestimmt
    (stored_region). Bei store: "region" werden nur Region und keine
    Koordinaten gespeichert.
    Nutzt INSERT OR IGNORE (kein Überschreiben).
    
    Args:
        importer: Name des Importers
        file_type: Dateityp (z.B. ".jpg"), None wenn unbekannt
        lat: Breitengrad (original, ungerundet)
        lon: Längengrad (original, ungerundet)
        ts: Zeitstempel (UTC ISO 8601), None wenn unbekannt
        date: Datum (YYYY-MM-DD)
        original_sha256: SHA-256 Hash der Originaldatei (vor Metadaten-Bereinigung)
        stored_sha256: SHA-256 Hash der gespeicherten Datei (nach Bereinigung)
        source_file: Relativer Pfad zur Quelldatei
        ref_db: Referenz-Datenbank (z.B. "medicine")
        ref_table: Referenz-Tabelle (z.B. "imaging_files")
        ref_id: Referenz-ID (z.B. Row-ID in imaging_files)
        person: Personen-Pseudonym (z.B. PER-XXXXXXXX)
        migrated_from: Herkunft bei Migrationen (z.B. "photo_locations"), sonst None

    Returns:
        True wenn der Eintrag gespeichert wurde, False wenn übersprungen
        (z.B. weil Policy store: "none" ist, der Punkt in einer Zone liegt
        oder required fields fehlen)
    
    Raises:
        Keine Exceptions - bei Fehlern: Warnung und False zurück
    """
    # 1. Policy auflösen
    policy = resolve_policy(importer, file_type)
    
    # 2. Prüfen ob Speicherung erlaubt ist
    # Logik: store ist explizit "none" -> keine Speicherung
    #        store ist explizit "region" -> nur Region speichern, keine Koordinaten
    #        store ist nicht gesetzt aber precision ist gesetzt -> speichern mit precision
    #        store ist nicht gesetzt und precision ist nicht gesetzt -> keine Speicherung
    store = policy.get("store")
    has_precision = "precision" in policy
    
    if store == "none":
        # Explizit keine Speicherung
        return False
    
    if store is None and not has_precision:
        # Keine Store- oder Precision-Angabe -> keine Speicherung
        return False
    
    # 3. Required fields prüfen
    if person is None:
        warnings.warn(
            t(f"Kein person-Pseudonym für location_store.record (importer={importer}) — Überspringe.",
              f"No person pseudonym for location_store.record (importer={importer}) — Skipping.")
        )
        return False
    
    try:
        lat, lon = float(lat), float(lon)
    except (TypeError, ValueError):
        warnings.warn(
            t(f"Ungültige Koordinaten für location_store.record (importer={importer}) — Überspringe.",
              f"Invalid coordinates for location_store.record (importer={importer}) — Skipping.")
        )
        return False

    if store == "region":
        # 4a. Nur Region: aus dem Originalpunkt, ohne Koordinaten
        region = stored_region(lat, lon, None)
        lat_rounded = lon_rounded = applied_precision = None
    else:
        # 4. Präzision aus Policy oder Default
        precision = policy.get("precision", 0)

        # 5. Privatsphäre-Zonen: Punkt weglassen oder vergröbern
        zones_cfg = _get_zones_config()
        action = _zone_action(lat, lon, precision, zones_cfg)
        if action == "hide":
            return False
        applied_precision = _zone_settings(zones_cfg)[0] if action == "coarsen" else precision

        # 6. Region aus dem Originalpunkt, dann auf Präzision runden
        region = stored_region(lat, lon, applied_precision)
        lat_rounded, lon_rounded = round_coords(lat, lon, applied_precision)
    
    # 7. In Datenbank speichern (Schema bei Bedarf anlegen)
    conn = None
    try:
        from utils.create_location_schema import ensure_location_schema
        conn = open_location_db()
        ensure_location_schema(conn)
        conn.execute("""
            INSERT OR IGNORE INTO location_registry (
                importer, file_type, source_file, original_sha256, stored_sha256,
                ts, date, lat, lon, precision, region, ref_db, ref_table, ref_id,
                person, migrated_from
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            importer,
            file_type,
            source_file,
            original_sha256 or None,
            stored_sha256 or None,
            ts,
            date,
            lat_rounded,
            lon_rounded,
            applied_precision,
            region,
            ref_db,
            ref_table,
            ref_id,
            person,
            migrated_from,
        ))
        conn.commit()
        # Auch ein schon vorhandener Eintrag (Duplikat) gilt als gespeichert.
        return True
    except Exception as e:
        warnings.warn(
            t(f"Fehler beim Speichern in location_registry: {e}",
              f"Error saving to location_registry: {e}")
        )
        return False
    finally:
        if conn is not None:
            conn.close()


class _PointFilter:
    """Wendet Policy und Privatsphäre-Zonen auf viele Punkte einer Quelle an.

    Policy und Zonen-Mittelpunkte werden einmal gelesen, nicht je Punkt.
    precision ist None, wenn die Policy keine Koordinaten erlaubt (store
    "none" oder "region", oder kein Eintrag). Mit allow_hide=False werden
    Punkte in einer Zone nie weggelassen, sondern nur auf zone_precision
    vergröbert (für Aufenthalte, deren Zeitraum und is_home erhalten
    bleiben müssen).
    """

    def __init__(self, importer: str, file_type: str | None = None, allow_hide: bool = True):
        policy = resolve_policy(importer, file_type)
        store = policy.get("store")
        if store in ("none", "region") or (store is None and "precision" not in policy):
            self.precision = None
            return
        self.precision = int(policy.get("precision", 0))
        zones_cfg = _get_zones_config()
        self.zone_active = bool(zones_cfg.get("enabled", True))
        self.zone_precision, self.radius_m, inside = _zone_settings(zones_cfg)
        self.inside = inside if allow_hide else "coarsen"
        self.centres = []
        if self.zone_active and self.precision > self.zone_precision:
            self.centres = zone_centres(zones_cfg)

    def apply(self, lat, lon) -> tuple[float, float] | None:
        """Gerundeter Punkt, oder None, wenn er nicht gespeichert wird."""
        point = _point(lat, lon)
        if point is None or self.precision is None:
            return None
        lat, lon = point
        if self.centres and in_zone(lat, lon, self.centres, self.radius_m):
            if self.inside == "hide":
                return None
            return round_coords(lat, lon, self.zone_precision)
        return round_coords(lat, lon, self.precision)


def _write_rows(sql: str, rows: list[tuple], conn=None) -> int:
    """Schreibt Zeilen in location.db (INSERT OR IGNORE), gibt neue Zeilen zurück."""
    if not rows:
        return 0
    from utils.create_location_schema import ensure_location_schema
    own = conn is None
    if own:
        conn = open_location_db()
    try:
        ensure_location_schema(conn)
        before = conn.total_changes
        conn.executemany(sql, rows)
        conn.commit()
        return conn.total_changes - before
    finally:
        if own:
            conn.close()


def store_track_points(importer: str, session_id: str, points, file_type: str | None = None,
                       conn=None) -> int:
    """Speichert Trackpunkte einer Session in location.db::session_tracks.

    Args:
        importer: Name des Importers (für die Policy)
        session_id: Verweis auf health.db::sessions
        points: Iterable von (ts, lat, lon, elevation_m, speed_ms)
        file_type: Dateityp für die Policy (z. B. ".gpx"), optional
        conn: offene location.db-Verbindung (optional, sonst eigene)

    Returns:
        Anzahl neu gespeicherter Punkte. Punkte in einer Privatsphäre-Zone
        (zones.inside "hide") werden nicht gespeichert; erlaubt die Policy
        keine Koordinaten, wird nichts gespeichert.
    """
    filt = _PointFilter(importer, file_type)
    if filt.precision is None:
        return 0
    rows = []
    for ts, lat, lon, elevation_m, speed_ms in points:
        point = filt.apply(lat, lon)
        if point is None:
            continue
        rows.append((session_id, ts, point[0], point[1], elevation_m, speed_ms))
    return _write_rows(
        "INSERT OR IGNORE INTO session_tracks (session_id, ts, lat, lon, elevation_m, speed_ms) "
        "VALUES (?, ?, ?, ?, ?, ?)", rows, conn)


def store_stays(importer: str, stays, file_type: str | None = None, conn=None) -> int:
    """Speichert Aufenthalte in location.db::location_stays.

    Args:
        stays: Iterable von (start_ts, end_ts, lat, lon, is_home, timezone,
            person, source)

    Returns:
        Anzahl neu gespeicherter Aufenthalte. In einer Privatsphäre-Zone wird
        ein Aufenthalt nur vergröbert, nie weggelassen.
    """
    filt = _PointFilter(importer, file_type, allow_hide=False)
    if filt.precision is None:
        return 0
    rows = []
    for start_ts, end_ts, lat, lon, is_home, tz, person, source in stays:
        point = filt.apply(lat, lon)
        if point is None:
            continue
        rows.append((start_ts, end_ts, point[0], point[1], is_home, tz, person, source))
    return _write_rows(
        "INSERT OR IGNORE INTO location_stays "
        "(start_ts, end_ts, lat, lon, is_home, timezone, person, source) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)", rows, conn)


def store_location_history(importer: str, entries, conn=None) -> int:
    """Speichert Standortverlauf in location.db::location_history.

    Args:
        entries: Iterable von (datetime, date, hour, state, lat, lon,
            gps_accuracy, zone, city, person, source); lat/lon dürfen None sein

    Returns:
        Anzahl neu gespeicherter Einträge. Koordinaten werden nach Policy
        gerundet und in einer Zone vergröbert; erlaubt die Policy keine
        Koordinaten, wird nichts gespeichert.
    """
    filt = _PointFilter(importer, None, allow_hide=False)
    if filt.precision is None:
        return 0
    rows = []
    for dt, date, hour, state, lat, lon, accuracy, zone, city, person, source in entries:
        point = filt.apply(lat, lon) if lat is not None and lon is not None else (None, None)
        if point is None:
            continue
        rows.append((dt, date, hour, state, point[0], point[1], accuracy, zone, city, person, source))
    return _write_rows(
        "INSERT OR IGNORE INTO location_history "
        "(datetime, date, hour, state, lat, lon, gps_accuracy, zone, city, person, source) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", rows, conn)


# ── Lesen aus location.db ────────────────────────────────────────────────────

# je Person: (Beginn aufsteigend, Ende, Zeitzone, laufendes Maximum der Enden)
_stay_tz_cache: dict[str, tuple[list, list, list, list]] = {}
_OPEN_END = "\uffff"   # sortiert nach jedem Zeitstempel (Aufenthalt ohne Ende)


def clear_read_caches() -> None:
    """Leert die Lese-Caches (nach Schreiben von Aufenthalten/Zeitzonen)."""
    _stay_tz_cache.clear()


def _load_stay_timezones(person: str) -> tuple[list, list, list, list]:
    rows = []
    try:
        from health_config import Config
        if Path(Config().location_db_path).exists():
            conn = open_location_db()
            try:
                rows = conn.execute(
                    "SELECT start_ts, end_ts, timezone FROM location_stays "
                    "WHERE person = ? AND timezone IS NOT NULL AND start_ts IS NOT NULL "
                    "ORDER BY start_ts", (person,)).fetchall()
            finally:
                conn.close()
    except (OSError, RuntimeError, *DB_ERRORS):
        # location.db fehlt, ist nicht lesbar oder ohne Tabelle: keine Zeitzone
        rows = []
    starts = [r[0] for r in rows]
    ends = [r[1] if r[1] is not None else _OPEN_END for r in rows]
    tzs = [r[2] for r in rows]
    max_end, running = [], ""
    for end in ends:
        running = max(running, end)
        max_end.append(running)
    return starts, ends, tzs, max_end


def stay_timezone(person: str, ts: str) -> str | None:
    """Zeitzone des Aufenthalts, der ts abdeckt (neuester Beginn zuerst).

    Liest location.db::location_stays über eine eigene Verbindung, damit
    Aufrufer mit offener health.db-Transaktion (resolve_timezone) nichts
    anhängen müssen. Die Aufenthalte einer Person werden einmal je Prozess
    geladen; die Suche nutzt eine Binärsuche über den Beginn und bricht ab,
    sobald kein früherer Aufenthalt mehr bis ts reichen kann. Gibt None
    zurück, wenn location.db fehlt oder kein Aufenthalt mit Zeitzone passt.
    """
    import bisect
    cached = _stay_tz_cache.get(person)
    if cached is None:
        cached = _stay_tz_cache[person] = _load_stay_timezones(person)
    starts, ends, tzs, max_end = cached
    i = bisect.bisect_right(starts, ts) - 1
    while i >= 0 and max_end[i] >= ts:
        if ends[i] >= ts:
            return tzs[i]
        i -= 1
    return None


def get_caller_name(explicit_caller: str | None = None) -> str:
    """Ermittelt den Namen des aufrufenden Skripts.
    
    Standardmäßig: Stammname von sys.argv[0] (ohne .py)
    Kann durch expliziten caller-Parameter überschrieben werden.
    
    Args:
        explicit_caller: Expliziter Caller-Name (überschreibt sys.argv[0])
    
    Returns:
        Caller-Name als String (z.B. "analyse_synthesis")
    """
    if explicit_caller:
        return explicit_caller
    
    if sys.argv and sys.argv[0]:
        # Pfad parsen und Stammname extrahieren
        path = Path(sys.argv[0])
        stem = path.stem
        if stem and stem != "__main__":
            return stem
    
    # Fallback
    return "unknown"


EXTERNAL_API_PRECISION = 1
EXTERNAL_API_PLACE_PRECISION = 2


def external_service_enabled(name: str) -> bool:
    """Prüft, ob ein externer Dienst in der Konfiguration freigegeben ist.
    
    Args:
        name: Name des Dienstes (z. B. "google_pollen")
    
    Returns:
        True wenn der Dienst freigegeben ist, False sonst (inkl. fehlende Datei oder Schlüssel)
    """
    privacy_cfg = _load_location_privacy()
    if not privacy_cfg:
        return False
    external_api_cfg = privacy_cfg.get("external_api", {})
    services_cfg = external_api_cfg.get("services", {})
    # Nur ein echtes true schaltet frei (ein String "false" darf nicht zählen)
    return services_cfg.get(name) is True


def for_external_api(lat: float, lon: float, place: bool = False) -> tuple[float, float]:
    """Rundet Koordinaten für Anfragen an externe Dienste (nicht LLM).

    Einzige Rundungsfunktion für ausgehende Anfragen. Standard ist
    external_api.precision (1 Stelle, ~11 km). Nur Abfragen, die einen
    Ortsnamen auf Gemeindeebene brauchen (Reverse-Geocoding), setzen
    place=True und nutzen external_api.place_precision (2 Stellen, ~1 km).
    Ohne location_privacy.json gelten diese Standardwerte.

    Args:
        lat: Breitengrad
        lon: Längengrad
        place: True nur für Ortsnamen-Abfragen

    Returns:
        (lat_rounded, lon_rounded)
    """
    external_api_cfg = _load_location_privacy().get("external_api", {})
    if place:
        precision = external_api_cfg.get("place_precision", EXTERNAL_API_PLACE_PRECISION)
    else:
        precision = external_api_cfg.get("precision", EXTERNAL_API_PRECISION)
    return round_coords(lat, lon, int(precision))



def _remove_coordinates_from_text(text: str, level: str) -> tuple[str, int]:
    """Entfernt oder rundet Koordinaten im Text basierend auf dem Level.
    
    Args:
        text: Der zu filternde Text
        level: Level aus der Policy ("none", "region", N, oder "token")
    
    Returns:
        (gefilterter Text, Anzahl der gefundenen/veränderten Koordinaten)
    """
    from modules.location_redaction import (
        find_coordinate_spans,
        find_place_spans,
        load_configured_places,
    )
    
    count = 0
    result = text
    
    if level == "none":
        # Koordinaten komplett entfernen
        coord_spans = find_coordinate_spans(result)
        for span in reversed(coord_spans):
            result = result[:span.start] + COORDINATE_PLACEHOLDER + result[span.end:]
            count += 1
    elif level == "region":
        # Koordinaten komplett entfernen
        coord_spans = find_coordinate_spans(result)
        for span in reversed(coord_spans):
            result = result[:span.start] + COORDINATE_PLACEHOLDER + result[span.end:]
            count += 1
    elif isinstance(level, int) or (isinstance(level, str) and level.isdigit()):
        # Raster-Präzision N: Koordinaten auf N Stellen runden
        precision = int(level)
        coord_spans = find_coordinate_spans(result)
        
        # Extrahiere und runde jede Koordinate
        for span in reversed(coord_spans):
            coord_text = result[span.start:span.end]
            # Koordinaten-Muster: Zahl, Zahl oder Zahl,Nummer Zahl,Numer
            # Versuche, die Zahlen zu extrahieren und zu runden
            coord_pattern = r'(-?\d+\.?\d*)[,\s]+(-?\d+\.?\d*)'
            match = re.search(coord_pattern, coord_text)
            if match:
                try:
                    lat_str, lon_str = match.groups()
                    lat_val = float(lat_str)
                    lon_val = float(lon_str)
                    lat_rounded = round(lat_val, precision)
                    lon_rounded = round(lon_val, precision)
                    
                    # Ersetze mit gerundeten Werten
                    # Format: lat, lon oder lat lon
                    separator = coord_text[match.end(1):match.start(2)]
                    new_coord = f"{lat_rounded}{separator}{lon_rounded}"
                    result = result[:span.start] + new_coord + result[span.end:]
                    count += 1
                except (ValueError, IndexError):
                    # Falls das Parsen fehlschlägt, entferne die Koordinate
                    result = result[:span.start] + COORDINATE_PLACEHOLDER + result[span.end:]
                    count += 1
            else:
                result = result[:span.start] + COORDINATE_PLACEHOLDER + result[span.end:]
                count += 1
    elif level == "token":
        # Koordinaten durch Tokens ersetzen
        coord_spans = find_coordinate_spans(result)
        for span in reversed(coord_spans):
            coord_text = result[span.start:span.end]
            # Extrahiere Koordinaten
            coord_pattern = r'(-?\d+\.?\d*)[,\s]+(-?\d+\.?\d*)'
            match = re.search(coord_pattern, coord_text)
            if match:
                try:
                    lat_str, lon_str = match.groups()
                    lat_val = float(lat_str)
                    lon_val = float(lon_str)
                    
                    # Standard-Präzision für Tokens (z.B. 2 für ~1km Zellen)
                    # Oder aus der Policy? Für jetzt: 2
                    token = location_token(lat_val, lon_val, 2)
                    result = (result[:span.start] + (token or COORDINATE_PLACEHOLDER)
                              + result[span.end:])
                    count += 1
                except (ValueError, IndexError):
                    result = result[:span.start] + COORDINATE_PLACEHOLDER + result[span.end:]
                    count += 1
            else:
                result = result[:span.start] + COORDINATE_PLACEHOLDER + result[span.end:]
                count += 1
    else:
        # Unbekanntes Level - entferne Koordinaten
        coord_spans = find_coordinate_spans(result)
        for span in reversed(coord_spans):
            result = result[:span.start] + COORDINATE_PLACEHOLDER + result[span.end:]
            count += 1
    
    # Orthsname immer entfernen (unabhängig vom Level)
    configured_places = load_configured_places()
    place_spans = find_place_spans(result, configured_places)
    for span in reversed(place_spans):
        result = result[:span.start] + COORDINATE_PLACEHOLDER + result[span.end:]
        count += 1
    
    return result, count


def filter_prompt_text(text: str, caller: str | None = None) -> tuple[str, int]:
    """Filtert Location-Daten aus Prompt-Text für Remote-LLM-Anbieter.
    
    WENDET die Policy für den Caller an:
    - "none" (default) und "region": Koordinaten und konfigurierte Ortsnamen entfernen
    - raster precision N: Koordinaten auf N Stellen runden, Ortsnamen entfernen
    - "token": Koordinaten durch Location-Token ersetzen, Ortsnamen entfernen
    
    Args:
        text: Der Prompt-Text
        caller: Name des aufrufenden Skripts (optional, sonst aus sys.argv[0])
    
    Returns:
        (gefilterter Text, Anzahl der gefundenen/veränderten Location-Referenzen)
    """
    # Caller ermitteln
    if caller is None:
        caller = get_caller_name()
    
    # Policy für den Caller laden
    privacy_cfg = _load_location_privacy()
    llm_cfg = privacy_cfg.get("llm", {})
    allow_cfg = llm_cfg.get("allow", {})
    default_level = llm_cfg.get("default", "none")
    
    # Level für diesen Caller
    level = allow_cfg.get(caller, default_level)
    
    return _remove_coordinates_from_text(text, level)


def for_prompt(caller: str, refs: list | None = None, level: str | None = None) -> list[dict]:
    """Gibt Location-Daten für Prompts basierend auf dem erlaubten Level zurück.
    
    Liest Einträge aus location_registry (location.db) für die gegebenen refs
    (location_registry.id Werte) und gibt sie je nach Level an:
    - "none" → leere Liste
    - "region" → Liste von Dicts mit id, date, region (gespeicherte Spalte region)
    - Zahl N (0-5) → Liste von Dicts mit id, date, lat, lon; lat/lon werden auf
      min(N, gespeicherte precision) Dezimalstellen gerundet, nie feiner als gespeichert
    - "token" → Liste von Dicts mit id, date, token (location_token); ist das Token
      None (kein Salz), wird der Eintrag ohne token-Feld zurückgegeben
    - Unbekannte Stufe → wie "none" mit Warnung
    
    Die Funktion folgt dem Outbound-Prinzip: nie genauere Daten als gespeichert
    oder erlaubt ausgeben.
    
    Args:
        caller: Name des aufrufenden Skripts (z.B. "analyse_travel")
        refs: Liste von location_registry.id Werten (Integer). Wenn None oder leer,
              wird eine leere Liste zurückgegeben.
        level: Optional explizites Level ("none", "region", N, "token") das die
               Policy überschreibt.
    
    Returns:
        Liste von Dicts mit den erlaubten Location-Daten. Jedes Dict enthält
        mindestens "id" und "date". Bei "none" oder unbekannter Stufe: leere Liste.
        Bei "token" und fehlerhaftem Salz: Dict ohne "token"-Feld.
    
    @limits.de   Nur lesend; gibt nie genauere Werte aus als gespeichert. Stufe als
                 Text ("2") liefert nur id und date.
    @limits.en   Read-only; never returns finer values than stored. A level given
                 as text ("2") returns id and date only.
    """
    # Keine refs → leere Liste
    if not refs:
        return []
    
    # Levelitteln
    privacy_cfg = _load_location_privacy()
    llm_cfg = privacy_cfg.get("llm", {})
    allow_cfg = llm_cfg.get("allow", {})
    default_level = llm_cfg.get("default", "none")
    
    effective_level = level if level is not None else allow_cfg.get(caller, default_level)
    
    # Bei "none" leere Liste zurückgeben
    if effective_level == "none":
        return []
    
    # Bei unbekannter Stufe: Warnung und leere Liste
    if effective_level not in ("region", "token") and not isinstance(effective_level, int):
        if not (isinstance(effective_level, str) and effective_level.isdigit()):
            warnings.warn(
                t(f"Unbekannte Location-Level '{effective_level}' für Caller '{caller}' — gebe keine Location-Daten aus.",
                  f"Unknown location level '{effective_level}' for caller '{caller}' — returning no location data.")
            )
            return []
    
    # Ref-IDs validieren (müssen Integer sein)
    valid_refs = [ref for ref in refs if isinstance(ref, int)]
    if not valid_refs:
        return []
    
    # Einträge aus location.db lesen
    conn = None
    try:
        conn = open_location_db()
        
        # Alle gewünschten refs in einer Query abfragen
        placeholders = ",".join("?" * len(valid_refs))
        query = f"""
            SELECT id, date, lat, lon, precision, region
            FROM location_registry
            WHERE id IN ({placeholders})
        """
        cursor = conn.execute(query, valid_refs)
        rows = cursor.fetchall()
        
    except Exception as e:
        warnings.warn(
            t(f"Fehler beim Lesen aus location.db für for_prompt: {e}",
              f"Error reading from location.db for for_prompt: {e}")
        )
        return []
    finally:
        if conn is not None:
            conn.close()
    
    # Ergebnisse verarbeiten
    result = []
    for row in rows:
        entry_id, date_val, lat_val, lon_val, precision_val, region_val = row
        entry = {"id": entry_id, "date": date_val}

        # Region-Level → gespeicherte Region, nie aus Koordinaten neu berechnet
        if effective_level == "region":
            if region_val:
                entry["region"] = region_val
            result.append(entry)
            continue

        # lat/lon können None sein (z.B. bei region-only Speicherung)
        if lat_val is not None and lon_val is not None:
            # Numeric Level (N) → gerundete Koordinaten
            if isinstance(effective_level, int):
                applied_precision = min(effective_level, precision_val or 0)
                entry["lat"] = round(float(lat_val), applied_precision)
                entry["lon"] = round(float(lon_val), applied_precision)
            
            # Token-Level → location_token
            elif effective_level == "token":
                token = location_token(float(lat_val), float(lon_val), precision_val or 0)
                if token is not None:
                    entry["token"] = token
        # Ohne Koordinaten (store: "region") gibt es weder Raster noch Token

        result.append(entry)
    
    return result


# Convenience wrapper für direkte Nutzung
__all__ = [
    "resolve_policy",
    "record",
    "file_sha256",
    "region_of",
    "region_name",
    "stored_region",
    "location_token",
    "get_caller_name",
    "external_service_enabled",
    "for_external_api",
    "filter_prompt_text",
    "for_prompt",
    "round_coords",
    "COORDINATE_PLACEHOLDER",
]
