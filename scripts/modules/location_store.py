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
             region_of liefert das Bundesland/Land für Koordinaten.
             location_token generiert deterministische Tokens für Zellen.
             for_prompt und filter_prompt_text setzen die Outbound-Regeln durch.
@method.en   resolve_policy returns the applicable policy for an importer/file type.
             record stores a location in the registry (applying precision and zones).
             region_of returns the federal state/country for coordinates.
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
from modules.db import open_location_db
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


def _get_centre_coordinates() -> list[tuple[float, float]]:
    """Lädt alle Zonen-Zentren aus der Konfiguration.
    
    Zentren kommen aus:
    1. zones.centres aus location_privacy.json (mit Koordinaten)
    2. privacy_check.patient_places (wenn in health_config.json)
    3. privacy_check.patient_addresses (wenn in health_config.json)
    
    Returns:
        Liste von (lat, lon) Tuples
    """
    zones_cfg = _get_zones_config()
    centres = []
    
    # 1. Aus zones.centres
    if "centres" in zones_cfg:
        for centre_name, centre_data in zones_cfg["centres"].items():
            # Überspringe Kommentare (Beginnt mit _)
            if centre_name.startswith("_"):
                continue
            if isinstance(centre_data, dict):
                lat = centre_data.get("lat")
                lon = centre_data.get("lon")
                if lat is not None and lon is not None:
                    try:
                        centres.append((float(lat), float(lon)))
                    except (ValueError, TypeError):
                        warnings.warn(
                            t(f"Ungültige Koordinaten für Zonen-Zentrum '{centre_name}'.",
                              f"Invalid coordinates for zone centre '{centre_name}'.")
                        )
    
    # 2. Aus privacy_check.patient_places und patient_addresses
    cfg = Config()
    full_cfg = cfg._cfg
    
    # patient_places
    patient_places = full_cfg.get("privacy_check", {}).get("patient_places", [])
    for i, place in enumerate(patient_places):
        if isinstance(place, dict):
            # 0.0 ist eine gültige Koordinate, daher kein "or"
            lat = place.get("lat") if place.get("lat") is not None else place.get("latitude")
            lon = place.get("lon") if place.get("lon") is not None else place.get("longitude")
            if lat is not None and lon is not None:
                try:
                    centres.append((float(lat), float(lon)))
                except (ValueError, TypeError):
                    warnings.warn(
                        t(f"Ungültige Koordinaten für patient_places Eintrag #{i}.",
                          f"Invalid coordinates for patient_places entry #{i}.")
                    )
    
    # patient_addresses
    patient_addresses = full_cfg.get("privacy_check", {}).get("patient_addresses", [])
    for i, addr in enumerate(patient_addresses):
        if isinstance(addr, dict):
            # 0.0 ist eine gültige Koordinate, daher kein "or"
            lat = addr.get("lat") if addr.get("lat") is not None else addr.get("latitude")
            lon = addr.get("lon") if addr.get("lon") is not None else addr.get("longitude")
            if lat is not None and lon is not None:
                try:
                    centres.append((float(lat), float(lon)))
                except (ValueError, TypeError):
                    warnings.warn(
                        t(f"Ungültige Koordinaten für patient_addresses Eintrag #{i}.",
                          f"Invalid coordinates for patient_addresses entry #{i}.")
                    )
    
    # Home location aus Config
    home_lat = cfg.home_lat
    home_lon = cfg.home_lon
    if home_lat is not None and home_lon is not None:
        centres.append((float(home_lat), float(home_lon)))
    
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


def _apply_zone_precision(lat: float, lon: float, precision: int, zones_cfg: dict) -> tuple[float, float, int]:
    """Wendet Zonen-Präzision an wenn der Punkt in einer Zone liegt.
    
    Args:
        lat: Breitengrad
        lon: Längengrad
        precision: Ursprüngliche Präzision aus der Policy
        zones_cfg: Zonen-Konfiguration
    
    Returns:
        (lat, lon, precision) mit angepasster Präzision falls in Zone
    """
    zones_enabled = zones_cfg.get("enabled", True)
    if not zones_enabled:
        return lat, lon, precision
    
    zone_precision = zones_cfg.get("zone_precision", 2)
    radius_m = zones_cfg.get("radius_m", 500)
    
    # Zone ist nur relevant wenn die ursprüngliche Präzision feiner ist
    if precision <= zone_precision:
        return lat, lon, precision
    
    # Prüfe alle Zentren
    centres = _get_centre_coordinates()
    for centre_lat, centre_lon in centres:
        if _is_in_zone(lat, lon, centre_lat, centre_lon, radius_m):
            # Auf Zonen-Präzision runden
            lat_rounded = round(lat, zone_precision)
            lon_rounded = round(lon, zone_precision)
            return lat_rounded, lon_rounded, zone_precision
    
    return lat, lon, precision


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


# Grober Rahmen um Deutschland; innerhalb wird das nächstgelegene Bundesland
# genommen, außerhalb nur "Ausland". Kein Online-Geocoding (design.md).
_DE_BBOX = (47.2, 55.1, 5.8, 15.1)  # lat_min, lat_max, lon_min, lon_max


def region_of(lat: float, lon: float) -> str:
    """Ermittelt das Bundesland (in Deutschland) oder "Ausland".

    Offline über modules.geo_bundesland.nearest_bundesland. Grenznahe Punkte
    im Nachbarland können dem angrenzenden Bundesland zugeordnet werden;
    für die Stufe "region" ist diese Unschärfe gewollt.

    @limits.de   Die Zuordnung erfolgt über das nächstgelegene Bundesland-Zentrum und ein grobes
                Rechteck um Deutschland (5.8-15.1° Ost, 47.2-55.1° Nord). In Grenznähe
                kann ein falsches Bundesland herauskommen; bei Nachbarländern kann ein
                Bundesland statt "Ausland".
    @limits.en   Assignment is based on the nearest German federal state centre and a coarse
                bounding box around Germany (5.8-15.1° E, 47.2-55.1° N). In border
                areas, a wrong federal state may be returned; in neighbouring countries,
                a federal state may be returned instead of "Abroad".

    Args:
        lat: Breitengrad
        lon: Längengrad

    Returns:
        Bundesland-Name (z.B. "Bayern"), "Ausland"/"Abroad" oder
        "Unbekannt"/"Unknown" bei ungültigen Werten
    """
    try:
        lat_f, lon_f = float(lat), float(lon)
    except (TypeError, ValueError):
        return t("Unbekannt", "Unknown")
    lat_min, lat_max, lon_min, lon_max = _DE_BBOX
    if not (lat_min <= lat_f <= lat_max and lon_min <= lon_f <= lon_max):
        return t("Ausland", "Abroad")
    from modules.geo_bundesland import nearest_bundesland
    return nearest_bundesland(lat_f, lon_f)[0]


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
    Prüft Zonen und passt die Präzision an falls nötig.
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
        (z.B. weil Policy store: "none" ist oder required fields fehlen)
    
    Raises:
        Keine Exceptions - bei Fehlern: Warnung und False zurück
    """
    # 1. Policy auflösen
    policy = resolve_policy(importer, file_type)
    
    # 2. Prüfen ob Speicherung erlaubt ist
    # Logik: store ist explizit "none" -> keine Speicherung
    #        store ist explizit "region" -> nur Region speichern (nicht implementiert, return False)
    #        store ist nicht gesetzt aber precision ist gesetzt -> speichern mit precision
    #        store ist nicht gesetzt und precision ist nicht gesetzt -> keine Speicherung
    store = policy.get("store")
    has_precision = "precision" in policy
    
    if store == "none":
        # Explizit keine Speicherung
        return False
    
    if store == "region":
        # Nur Region speichern (derzeit nicht implementiert in Registry)
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
    
    # 4. Präzision aus Policy oder Default
    precision = policy.get("precision", 0)
    
    # 5. Zonen prüfen und Präzision anpassen
    zones_cfg = _get_zones_config()
    lat, lon, applied_precision = _apply_zone_precision(lat, lon, precision, zones_cfg)
    
    # 6. Auf Präzision runden
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
                ts, date, lat, lon, precision, ref_db, ref_table, ref_id, person,
                migrated_from
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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


def for_external_api(lat: float, lon: float) -> tuple[float, float]:
    """Wendet die external_api-Präzision auf Koordinaten an.
    
    Liest die Präzision aus location_privacy.json -> external_api.precision
    und rundet die Koordinaten entsprechend.
    
    Args:
        lat: Breitengrad
        lon: Längengrad
    
    Returns:
        (lat_rounded, lon_rounded) mit der konfigurierten Präzision
    """
    privacy_cfg = _load_location_privacy()
    external_api_cfg = privacy_cfg.get("external_api", {})
    precision = external_api_cfg.get("precision", 2)
    
    return round_coords(lat, lon, precision)



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
    - "region" → Liste von Dicts mit id, date, region (region_of)
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
            SELECT id, date, lat, lon, precision
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
        entry_id, date_val, lat_val, lon_val, precision_val = row
        entry = {"id": entry_id, "date": date_val}
        
        # lat/lon können None sein (z.B. bei region-only Speicherung)
        if lat_val is not None and lon_val is not None:
            # Numeric Level (N) → gerundete Koordinaten
            if isinstance(effective_level, int):
                applied_precision = min(effective_level, precision_val or 0)
                entry["lat"] = round(float(lat_val), applied_precision)
                entry["lon"] = round(float(lon_val), applied_precision)
            
            # Region-Level → region_of
            elif effective_level == "region":
                entry["region"] = region_of(float(lat_val), float(lon_val))
            
            # Token-Level → location_token
            elif effective_level == "token":
                token = location_token(float(lat_val), float(lon_val), precision_val or 0)
                if token is not None:
                    entry["token"] = token
        else:
            # Keine Koordinaten gespeichert (z.B. bei store: "region")
            if effective_level == "region":
                # Keine Koordinaten → kein Region-Resultat
                pass
            elif effective_level == "token":
                # Ohne Koordinaten kein Token
                pass
        
        result.append(entry)
    
    return result


# Convenience wrapper für direkte Nutzung
__all__ = [
    "resolve_policy",
    "record",
    "file_sha256",
    "region_of",
    "location_token",
    "get_caller_name",
    "for_external_api",
    "filter_prompt_text",
    "for_prompt",
    "round_coords",
    "COORDINATE_PLACEHOLDER",
]
