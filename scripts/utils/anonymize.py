#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
anonymize — Zentrale Anonymisierungs- und Pseudonymisierungs-Hilfsfunktionen
from health_config import KYORO_CONFIG_DIR


@tier        infrastructure
@purpose.de  Zentrales Modul für alle Anonymisierungs- und Pseudonymisierungsfunktionen.
              Alle Funktionen, die extern übertragene oder gespeicherte Standort- oder Identitätsdaten
              berühren, sollten dieses Modul verwenden, um eine zentrale Stelle für Anpassungen von
              Präzision oder Scrubbing-Regeln zu haben.
@purpose.en  Central module for all anonymization and pseudonymization helper functions.
              All functions that touch externally transmitted or stored location/identity data should
              go through this module to have a single place to adjust precision or scrubbing rules.
@method.de   Bietet Funktionen für: GPS-Koordinaten-Rundung (Standard: 2 Dezimalstellen ≈ 1,1 km Raster),
              Geräte-Seriennummern-Pseudonymisierung (SN-XXXXXXXX Format mit SHA-256 Hash in identity.db),
              E-Mail-Adressen-Ersetzung, Telefon/Fax-Nummern-Erkennung und Pseudonymisierung,
              Versicherungsnummern und -namen Pseudonymisierung, Geburtsdaten-Ersetzung,
              Namen-Pseudonymisierung (Vorname, Nachname), Adressen- und Stadtnamen-Ersetzung,
              Compliance-Checks für die Datenbank, Apple Health sourceName-Bereinigung und
              HealthKit <Me> Attribut-Scrubbing. Speichert alle Pseudonymisierungen in einer
              separaten identity.db für Konsistenz.
@method.en   Provides functions for: GPS coordinate rounding (default: 2 decimal places ≈ 1.1km grid),
              device serial number pseudonymization (SN-XXXXXXXX format with SHA-256 hash in identity.db),
              email address replacement, phone/fax number detection and pseudonymization,
              insurance number and name pseudonymization, birthdate replacement,
              name pseudonymization (first name, last name), address and city name replacement,
              database compliance checks, Apple Health sourceName scrubbing and HealthKit
              <Me> attribute scrubbing. Stores all pseudonymizations in a separate identity.db
              for consistency.
@reads       identity.db.device_serial_map
@writes      identity.db.device_serial_map
@limits.de   GPS-Präzision auf 2 Dezimalstellen begrenzt (ca. 1,1 km Genauigkeit) - kann bei Bedarf angepasst werden.
              Pseudonymisierung ist deterministisch (gleiche Eingabe → gleiche Ausgabe) aber nicht umkehrbar.
              Identitätsdatenbank (identity.db) wird mit restriktiven Berechtigungen (600) angelegt.
              Compliance-Checks können falsch-positive Ergebnisse liefern, die manuelle Überprüfung erfordern.

@relevance.de  Ermöglicht die Anonymisierung von Gesundheitsdaten, essentiell für den Datenschutz und die Einhaltung von Compliance-Anforderungen
@relevance.en  Enables anonymization of health data, essential for data privacy and compliance requirements
@limits.en   GPS precision limited to 2 decimal places (approx. 1.1km accuracy) - can be adjusted if needed.
              Pseudonymization is deterministic (same input → same output) but not reversible.
              Identity database (identity.db) is created with restrictive permissions (600).
              Compliance checks may produce false positives requiring manual review.
@usage
    from utils.anonymize import round_coords, pseudonymize_device_serial, scrub_text_field
    from utils.anonymize import check_anonymization_compliance, print_compliance_report
    # GPS-Koordinaten rundet
    lat_rounded, lon_rounded = round_coords(52.5200, 13.4050)
    # Geräte-Seriennummer pseudonymisieren
    pseudo = pseudonymize_device_serial('ABC123XYZ', 'polar_m430')
    # Compliance-Check durchführen
    issues = check_anonymization_compliance('data/health.db')
    print_compliance_report(issues)
"""

import re
import sqlite3
import hashlib
from datetime import datetime, timezone
from pathlib import Path

from health_config import KYORO_CONFIG_DIR
from modules.db import DB_ERRORS, DB_OPERATIONAL_ERRORS

# Identity database path (separate from health.db for security)
_IDENTITY_DB = KYORO_CONFIG_DIR / "identity.db"

# ── GPS precision ─────────────────────────────────────────────────────────────

# 2 decimal places ≈ 1.1 km grid — sufficient for city-level weather / location
# without pinpointing home address or travel route.
_COORD_PRECISION = 2


def round_coords(lat: float, lon: float,
                 precision: int = _COORD_PRECISION) -> tuple[float, float]:
    """Round GPS coordinates to reduce spatial resolution.

    Default precision=2 gives ~1 km grid (≈1.1 km at equator).
    Use before any external API call and before storing in the database.
    """
    return round(lat, precision), round(lon, precision)


# ── Device serial pseudonymization ────────────────────────────────────────────


def pseudonymize_device_serial(serial_real: str, device_id: str) -> str:
    """Create or retrieve a deterministic pseudonym for a device serial number.
    
    Stores the mapping in identity.db for consistency across imports.
    Returns the pseudonym (format: SN-XXXXXXXX).
    
    Args:
        serial_real: The real device serial number
        device_id: The device identifier (e.g., 'garmin_fenix6')
        
    Returns:
        Pseudonym in format SN-XXXXXXXX (8 uppercase hex chars)
    """
    # Create deterministic pseudonym from serial
    pseudo_id = f"SN-{hashlib.sha256(serial_real.encode()).hexdigest()[:8].upper()}"
    
    # Store in identity.db
    _IDENTITY_DB.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(_IDENTITY_DB)
    con.execute(
        """
        INSERT OR IGNORE INTO device_serial_map 
        (pseudo_id, device_id, serial_real, created_at) 
        VALUES (?, ?, ?, ?)
        """,
        (pseudo_id, device_id, serial_real, datetime.now(timezone.utc).isoformat())
    )
    con.commit()
    con.close()
    _IDENTITY_DB.chmod(0o600)
    
    return pseudo_id


def get_device_pseudo(serial_real: str) -> str | None:
    """Retrieve existing pseudonym for a device serial, or None if not found."""
    if not _IDENTITY_DB.exists():
        return None
        
    con = sqlite3.connect(_IDENTITY_DB)
    result = con.execute(
        "SELECT pseudo_id FROM device_serial_map WHERE serial_real = ?",
        (serial_real,)
    ).fetchone()
    con.close()
    return result[0] if result else None


def get_all_device_mappings() -> dict[str, str]:
    """Return dict mapping real serials to pseudonyms."""
    if not _IDENTITY_DB.exists():
        return {}
        
    con = sqlite3.connect(_IDENTITY_DB)
    mappings = con.execute(
        "SELECT serial_real, pseudo_id FROM device_serial_map"
    ).fetchall()
    con.close()
    return {real: pseudo for real, pseudo in mappings}


# ── Email pseudonymization ─────────────────────────────────────────────────


def pseudonymize_email(email: str) -> str:
    """Replace email address with pseudonym, domain removed.

    Example: "john.doe@example.com" → "[EMAIL-ENTFERNT]"
    """
    return "[EMAIL-ENTFERNT]"


def scrub_text_field(text: str | None) -> str | None:
    """Remove or pseudonymize email addresses in text fields."""
    if not text or '@' not in text:
        return text
    
    # Simple email pattern matching
    import re
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    
    def replace_email(match):
        email = match.group(0)
        return pseudonymize_email(email)
    
    return re.sub(email_pattern, replace_email, text)


def pseudonymize_insurance_number(insurance_num: str) -> str:
    """Replace insurance number with pseudonym.
    
    Example: "123456789" → "INS-ABC123"
    """
    if not insurance_num or len(insurance_num) < 5:
        return insurance_num
    
    # Create deterministic pseudonym
    return f"INS-{hashlib.sha256(insurance_num.encode()).hexdigest()[:6].upper()}"


def pseudonymize_insurance_name(name: str) -> str:
    """Replace insurance name with generic term.
    
    Example: "AOK Bayern" → "Krankenkasse"
    """
    if not name:
        return name
    
    # Normalize and replace with generic term
    name_upper = name.strip().upper()
    if any(insurance in name_upper for insurance in ['AOK', 'TK', 'TECHNIKER', 'BARMER', 'DAK', 'KKH']):
        return "Krankenkasse"
    
    return "Versicherung"


def pseudonymize_first_name(name: str) -> str:
    """Replace first name with pseudonym while preserving gender context.
    
    Example: "Micha" → "Vorname-ABC123"
    """
    if not name or len(name.strip()) < 2:
        return name
    
    # Create deterministic pseudonym
    clean_name = name.strip()
    return f"Vorname-{hashlib.sha256(clean_name.encode()).hexdigest()[:6].upper()}"


def pseudonymize_zip_code(zip_code: str) -> str:
    """Replace ZIP code with pseudonym (German format: 5 digits).
    
    Example: "80331" → "PLZ-XXXXX"
    """
    if not zip_code or not re.match(r'^\d{5}$', zip_code.strip()):
        return zip_code
    
    return f"PLZ-{hashlib.sha256(zip_code.encode()).hexdigest()[:5].upper()}"


def pseudonymize_address(address: str) -> str:
    """Replace full address with pseudonym.
    
    Example: "Musterstraße 123, 80331 München" → "[ADRESSE-ENTFERNT]"
    """
    if not address or len(address.strip()) < 10:
        return address
    
    return "[ADRESSE-ENTFERNT]"


def pseudonymize_last_name(name: str) -> str:
    """Replace last name with pseudonym.
    
    Example: "Müller" → "Nachname-XXXXXX"
    """
    if not name or len(name.strip()) < 2:
        return name
    
    return f"Nachname-{hashlib.sha256(name.encode()).hexdigest()[:6].upper()}"


def pseudonymize_arzt_name(full_name: str) -> str:
    """Replace doctor name with pseudonym.
    
    Example: "Dr. med. Müller" → "Arzt-XXXXXX"
    """
    if not full_name or len(full_name.strip()) < 5:
        return full_name
    
    return f"Arzt-{hashlib.sha256(full_name.encode()).hexdigest()[:6].upper()}"


def pseudonymize_mvz_name(name: str) -> str:
    """Replace MVZ name with pseudonym.
    
    Example: "MVZ München" → "MVZ-XXXXXX"
    """
    if not name or len(name.strip()) < 5:
        return name
    
    return f"MVZ-{hashlib.sha256(name.encode()).hexdigest()[:6].upper()}"


def pseudonymize_fax_number(fax: str) -> str:
    """Replace fax number with pseudonym.
    
    Example: "Fax: 089/12345678" → "Fax: [FAX-ENTFERNT]"
    """
    if not fax or len(fax.strip()) < 5:
        return fax
    
    return "[FAX-ENTFERNT]"


def is_phone_or_fax_number(text: str) -> bool:
    """Check if text contains phone or fax number."""
    if not text:
        return False
    
    # Phone number patterns (German and international)
    phone_patterns = [
        r'\b(\+\d{2,3}[\s\-]?)?\(?\d{1,4}\)?[\s\-]?\d{1,4}[\s\-]?\d{1,4}\b',  # International
        r'\b0\d{1,5}[\s\-]?\d{1,8}\b',  # German landline
        r'\b\d{3}[\s\-]?\d{3}[\s\-]?\d{4}\b',  # XXX/XXX-XXXX
    ]
    
    # Fax number patterns
    fax_patterns = [
        r'\bFax[:\s]*[\d\s\-/]{8,}\b',
        r'\bTelefax[:\s]*[\d\s\-/]{8,}\b',
    ]
    
    for pattern in phone_patterns + fax_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return True
    
    return False


def extract_and_pseudonymize_phone_fax(text: str) -> str:
    """Extract and pseudonymize phone and fax numbers from text."""
    if not text:
        return text
    
    import re
    
    # Simpler approach: Look for common phone/fax indicators
    result = text
    
    # Pattern for phone numbers with common prefixes
    phone_with_prefix = r'\b(Tel|Telefon|Mobil|Handy|Phone|Tel\.?Nr)[.:\s]*([\d\s\-/]{7,})'
    phone_matches = re.finditer(phone_with_prefix, result, re.IGNORECASE)
    for match in phone_matches:
        full_match = match.group(0)
        number_part = match.group(2)
        if len(number_part.replace(' ', '').replace('-', '').replace('/', '')) >= 7:
            replacement = f"{match.group(1)}: [TELEFON-{hashlib.sha256(number_part.encode()).hexdigest()[:6].upper()}]"
            result = result.replace(full_match, replacement)
    
    # Pattern for standalone phone numbers (German format)
    standalone_phone = r'\b(\+\d{2,3}[\s\-]?\(?\d{1,4}\)?[\s\-]?\d{1,4}[\s\-]?\d{1,4})\b'
    phone_matches = re.finditer(standalone_phone, result)
    for match in phone_matches:
        matched_text = match.group(0)
        if len(matched_text.replace(' ', '').replace('-', '')) >= 8:
            replacement = f"[TELEFON-{hashlib.sha256(matched_text.encode()).hexdigest()[:6].upper()}]"
            result = result.replace(matched_text, replacement)
    
    # Pattern for fax numbers
    fax_pattern = r'\b(Fax|Telefax)[:\s]*([\d\s\-/]{7,})'
    fax_matches = re.finditer(fax_pattern, result, re.IGNORECASE)
    for match in fax_matches:
        full_match = match.group(0)
        number_part = match.group(2)
        if len(number_part.replace(' ', '').replace('-', '').replace('/', '')) >= 7:
            replacement = f"Fax: [FAX-{hashlib.sha256(number_part.encode()).hexdigest()[:6].upper()}]"
            result = result.replace(full_match, replacement)
    
    return result


def _load_name_lists() -> dict:
    """Load name lists from JSON configuration file."""
    import json
    from pathlib import Path
    
    # Try to load from name_lists/name_lists.json in the same directory
    name_lists_path = Path(__file__).parent / "name_lists" / "name_lists.json"
    
    if name_lists_path.exists():
        try:
            with open(name_lists_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: Could not load name lists from {name_lists_path}: {e}")
            print("Falling back to built-in name lists")
    
    # Fallback to built-in lists if file is missing or invalid
    return {
        "common_first_names": [
            'Micha', 'Michael', 'Sandra', 'Alexander', 'Thomas', 'Andreas',
            'Stefan', 'Christian', 'Daniel', 'Markus', 'Jan', 'Peter',
            'Anna', 'Julia', 'Lisa', 'Sarah', 'Laura', 'Maria', 'Sophie',
            'Hanna', 'Emma', 'Lea', 'Mia', 'Lena', 'Hannah', 'Johanna'
        ],
        "common_last_names": [
            'Müller', 'Schmidt', 'Schneider', 'Fischer', 'Weber', 'Meyer',
            'Wagner', 'Becker', 'Schulz', 'Hoffmann', 'Bauer', 'Richter',
            'Klein', 'Wolf', 'Schröder', 'Neumann', 'Schwarz', 'Zimmermann',
            'Braun', 'Krüger', 'Hofmann', 'Hartmann', 'Lange', 'Schmitt',
            'Werner', 'Schmitz', 'Krause', 'Meier', 'Lehmann', 'Schmid',
            'Schulze', 'Maier', 'Köhler', 'Herrmann', 'König', 'Walter',
            'Mayer', 'Huber', 'Kaiser', 'Fuchs', 'Peters', 'Lang'
        ],
        "common_arzt_titles": [
            r'Dr\. med\.', r'Dr\.', r'Prof\. Dr\. med\.', r'Prof\. Dr\.',
            'Arzt', 'Ärztin', 'Facharzt', 'Fachärztin',
            'Chefarzt', 'Chefärztin', 'Oberarzt', 'Oberärztin'
        ],
        "common_mvz_names": [
            'MVZ', 'Medizinisches Versorgungszentrum', 'Gemeinschaftspraxis',
            'Praxisgemeinschaft', 'Ärztehaus', 'Gesundheitszentrum'
        ]
    }


def get_common_german_first_names() -> list[str]:
    """Return list of common German first names for detection."""
    name_lists = _load_name_lists()
    return name_lists["common_first_names"]


def get_common_german_last_names() -> list[str]:
    """Return list of common German last names for detection."""
    name_lists = _load_name_lists()
    return name_lists["common_last_names"]


def get_common_arzt_titles() -> list[str]:
    """Return list of common German doctor titles."""
    name_lists = _load_name_lists()
    return name_lists["common_arzt_titles"]


def get_common_mvz_names() -> list[str]:
    """Return list of common MVZ name patterns."""
    name_lists = _load_name_lists()
    return name_lists["common_mvz_names"]


def pseudonymize_birthdate(birthdate: str) -> str:
    """Replace birthdate with age (only year is kept for age calculation).
    
    Example: "1985-05-15" → "Alter: 39" (assuming current year)
    """
    if not birthdate:
        return birthdate
    
    import re
    from datetime import datetime
    
    # Try to extract year from various date formats
    year_match = re.search(r'(\d{4})', birthdate)
    if year_match:
        try:
            birth_year = int(year_match.group(1))
            current_year = datetime.now().year
            age = current_year - birth_year
            return f"Alter: {age}"
        except ValueError:
            pass
    
    return "[DATUM-ENTFERNT]"


def scrub_sensitive_health_data(text: str | None, preserve_gender_age: bool = True) -> str | None:
    """Remove or pseudonymize all sensitive health data from text.
    
    Handles: emails, phone numbers, IP addresses, insurance numbers, 
    insurance names, birth dates, addresses, names
    
    Args:
        text: The text to scrub
        preserve_gender_age: If True, preserves gender and age references
    """
    if not text:
        return text
    
    import re
    
    # 1. Pseudonymize emails
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    text = re.sub(email_pattern, lambda m: pseudonymize_email(m.group(0)), text)
    
    # 2. Pseudonymize phone numbers (German format)
    phone_patterns = [
        r'\b(\+49|0)\s?[\d\s\-/]{8,}\b',  # +49 or 0 prefix
        r'\b\d{3}[\s\-/]\d{3}[\s\-/]\d{4}\b',  # XXX/XXX-XXXX
    ]
    for pattern in phone_patterns:
        text = re.sub(pattern, '[TELEFON-ENTFERNT]', text)
    
    # 3. Pseudonymize IP addresses
    ip_pattern = r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b'
    text = re.sub(ip_pattern, '[IP-ENTFERNT]', text)
    
    # 4. Pseudonymize insurance numbers (7+ digits)
    insurance_num_pattern = r'\b\d{7,}\b'
    text = re.sub(insurance_num_pattern, lambda m: pseudonymize_insurance_number(m.group(0)), text)
    
    # 5. Pseudonymize insurance names
    insurance_name_pattern = r'\b(AOK|TK|Techniker|Barmer|DAK|KKH|hkk)\b'
    text = re.sub(insurance_name_pattern, lambda m: pseudonymize_insurance_name(m.group(0)), text, flags=re.IGNORECASE)
    
    # 6. Pseudonymize birth dates (but preserve age if requested)
    if not preserve_gender_age:
        date_patterns = [
            (r'\b\d{2}\.\d{2}\.\d{4}\b', 'DD.MM.YYYY'),
            (r'\b\d{4}-\d{2}-\d{2}\b', 'YYYY-MM-DD'),
            (r'\b\d{1,2}/\d{1,2}/\d{2,4}\b', 'MM/DD/YY'),
        ]
        
        for pattern, format_type in date_patterns:
            text = re.sub(pattern, lambda m: pseudonymize_birthdate(m.group(0)), text)
    
    # 7. Pseudonymize full names (first + last name patterns)
    name_pattern = r'\b[A-Z][a-z]+\s[A-Z][a-z]+\b'
    text = re.sub(name_pattern, '[NAME-ENTFERNT]', text)
    
    # 8. Pseudonymize first names (common German names)
    common_first_names = get_common_german_first_names()
    for first_name in common_first_names:
        # Match whole words only
        first_name_pattern = rf'\b{re.escape(first_name)}\b'
        text = re.sub(first_name_pattern, lambda m: pseudonymize_first_name(m.group(0)), text, flags=re.IGNORECASE)
    
    # 9. Pseudonymize ZIP codes (German 5-digit format)
    zip_pattern = r'\b\d{5}\b'
    text = re.sub(zip_pattern, lambda m: pseudonymize_zip_code(m.group(0)), text)
    
    # 10. Extract and pseudonymize phone/fax numbers
    text = extract_and_pseudonymize_phone_fax(text)
    
    # 11. Pseudonymize last names (common German surnames)
    last_names = get_common_german_last_names()
    for last_name in last_names:
        last_name_pattern = rf'\b{re.escape(last_name)}\b'
        text = re.sub(last_name_pattern, lambda m: pseudonymize_last_name(m.group(0)), text, flags=re.IGNORECASE)
    
    # 12. Pseudonymize doctor names (with titles)
    arzt_titles = get_common_arzt_titles()
    for title in arzt_titles:
        # Match "Dr. med. Müller" or similar patterns
        arzt_pattern = rf'\b({re.escape(title)}\s+[A-Z][a-z]+)\b'
        text = re.sub(arzt_pattern, lambda m: pseudonymize_arzt_name(m.group(0)), text, flags=re.IGNORECASE)
    
    # 13. Pseudonymize MVZ names
    mvz_names = get_common_mvz_names()
    for mvz_name in mvz_names:
        mvz_pattern = rf'\b({re.escape(mvz_name)}\s*.*)'
        text = re.sub(mvz_pattern, lambda m: pseudonymize_mvz_name(m.group(0)), text, flags=re.IGNORECASE)
    
    # 8. Pseudonymize addresses (street patterns)
    street_pattern = r'\b(Stra\w+e|Allee|Weg|Gasse|Platz)\b'
    text = re.sub(street_pattern, '[STRASSE-ENTFERNT]', text, flags=re.IGNORECASE)
    
    # 9. Pseudonymize city names (common German cities)
    city_pattern = r'\b(Berlin|München|Hamburg|Köln|Frankfurt|Stuttgart|Düsseldorf|Dortmund|Essen|Bremen)\b'
    text = re.sub(city_pattern, '[STADT-ENTFERNT]', text, flags=re.IGNORECASE)
    
    # 10. Preserve gender references if requested
    if preserve_gender_age:
        # Keep gender-related terms
        gender_terms = ['männlich', 'weiblich', 'divers', 'male', 'female', 'diverse', 'gender']
        for term in gender_terms:
            # Restore if accidentally removed
            if f'[{term.upper()}' in text:
                text = text.replace(f'[{term.upper()}', term)
    
    # 11. Preserve age references if requested
    if preserve_gender_age:
        age_pattern = r'\[ALTER-\d+\]'
        text = re.sub(age_pattern, lambda m: m.group(0).replace('[ALTER-', 'Alter: '), text)
    
    return text


# ── Anonymization compliance checking ─────────────────────────────────────────


def check_anonymization_compliance(db_conn_or_path: sqlite3.Connection | str | Path) -> dict[str, int]:
    """Check database for anonymization compliance issues.
    
    Args:
        db_conn_or_path: Either a sqlite3 connection or a path to the database
        
    Returns a dict with counts of potential issues:
    - potential_personal_names: person_ids that look like real names/emails
    - high_precision_gps: GPS points with >5 decimal places
    - unpseudonymized_devices: devices without SN- prefix in serial
    - cleartext_emails: email addresses in text fields
    - cleartext_insurance: insurance numbers or health insurance names
    - cleartext_birthdates: birth dates (only age should be stored)
    """
    # Handle both connection and path input
    if isinstance(db_conn_or_path, (str, Path)):
        db_path = Path(db_conn_or_path)
        if not db_path.exists():
            return {
                'potential_personal_names': 0,
                'high_precision_gps': 0,
                'unpseudonymized_devices': 0,
                'cleartext_accounts': 0
            }
        con = sqlite3.connect(db_path)
        own_connection = True
    else:
        con = db_conn_or_path
        own_connection = False
    issues = {
        'potential_personal_names': 0,
        'high_precision_gps': 0,
        'unpseudonymized_devices': 0,
        'cleartext_emails': 0,
        'cleartext_insurance': 0,
        'cleartext_birthdates': 0
    }
    
    try:
        # 1. Check for potential personal names in person_ids
        # (contains spaces, @ symbols, or apostrophes - common in real names)
        issues['potential_personal_names'] = con.execute(
            """
            SELECT COUNT(*) FROM persons 
            WHERE person_id GLOB '* *'
            OR person_id LIKE '%@%'
            OR person_id LIKE '%''%' 
            """
        ).fetchone()[0]
        
        # 2. Check GPS precision (more than 5 decimal places indicates high precision)
        # Count lat/lon values with more than 5 decimal places
        issues['high_precision_gps'] = con.execute(
            """
            SELECT COUNT(*) FROM session_tracks 
            WHERE lat IS NOT NULL 
            AND (LENGTH(CAST(lat AS TEXT)) - INSTR(CAST(lat AS TEXT), '.') > 6
                 OR LENGTH(CAST(lon AS TEXT)) - INSTR(CAST(lon AS TEXT), '.') > 6)
            """
        ).fetchone()[0]
        
        # 3. Check for unpseudonymized devices (no SN- prefix in serial)
        issues['unpseudonymized_devices'] = con.execute(
            """
            SELECT COUNT(*) FROM devices 
            WHERE serial IS NOT NULL 
            AND serial != ''
            AND serial NOT LIKE 'SN-%'
            """
        ).fetchone()[0]
        
        # 4. Check for email addresses in ALL text fields
        email_pattern = '%_@_%'
        
        try:
            # Große EAV-Tabellen mit 10M+ Zeilen: DISTINCT vorab holen, dann im Python prüfen
            _HIGH_VOLUME: list[tuple[str, str]] = [
                ('measurements', 'source_app'),
                ('measurements', 'value_text'),
            ]
            tables_to_check = [
                ('sessions', 'source_app'),
                ('blood_pressure', 'source'),
                ('devices', 'notes'),
                ('persons', 'notes'),
                ('import_log', 'error_detail'),
                ('acute_events', 'notes'),
                ('sessions', 'device_id'),
                ('symptoms', 'value_text'),
                ('blood_pressure', 'notes'),
                ('medications', 'notes'),
                ('user_context', 'note'),
                ('lab_manual', 'kommentar'),
                ('ecg_sessions', 'device_id'),
                ('import_log', 'data_path'),
            ]

            def _like(val: str | None, pattern: str) -> bool:
                if not val:
                    return False
                pat = pattern.replace('%', '').replace('_', '')
                return pat.lower() in val.lower() if pat else bool(val)

            email_counts = []
            # Hochvolumen-Tabellen: nur DISTINCT-Werte
            for table, column in _HIGH_VOLUME:
                try:
                    rows = con.execute(
                        f"SELECT DISTINCT {column} FROM {table} WHERE {column} IS NOT NULL"
                    ).fetchall()
                    hits = sum(1 for (v,) in rows if v and '@' in v and '.' in v.split('@')[-1])
                    if hits:
                        email_counts.append(hits)
                except DB_OPERATIONAL_ERRORS:
                    pass
            # Normale Tabellen
            for table, column in tables_to_check:
                try:
                    count = con.execute(
                        f"SELECT COUNT(*) FROM {table} WHERE {column} LIKE ?",
                        (email_pattern,)
                    ).fetchone()[0]
                    if count > 0:
                        email_counts.append(count)
                except DB_OPERATIONAL_ERRORS:
                    pass
            
            issues['cleartext_emails'] = sum(email_counts)
            
        except DB_ERRORS as e:
            print(f"Warning: Email check error: {e}")
            issues['cleartext_emails'] = 0
        
        # 5. Check for insurance numbers (German health insurance format)
        try:
            # More specific patterns for German health insurance
            # Insurance numbers are typically 9-10 digits, often with spaces
            # Insurance names are specific keywords
            insurance_patterns = [
                ('%_ ______', 'Digit + Space + 7 digits'),  # z.B. "X 1234567"
                ('%_______', '8+ digits in sequence'),      # z.B. "12345678"
                ('%AOK%', 'AOK keyword'),
                ('%TK%', 'Techniker Krankenkasse'),
                ('%Barmer%', 'Barmer'),
                ('%DAK%', 'DAK'),
                ('%Techniker%', 'Techniker'),
                ('%Krankenkasse%', 'Krankenkasse'),
            ]
            
            insurance_counts = []
            for table, column in tables_to_check:
                try:
                    # First check for insurance names (more reliable)
                    for pattern, desc in insurance_patterns[2:]:
                        count = con.execute(
                            f"SELECT COUNT(*) FROM {table} WHERE {column} LIKE ?",
                            (pattern,)
                        ).fetchone()[0]
                        if count > 0:
                            # Verify it's actually an insurance reference, not a false positive
                            actual_matches = con.execute(
                                f"SELECT {column} FROM {table} WHERE {column} LIKE ? LIMIT 5",
                                (pattern,)
                            ).fetchall()
                            
                            # Filter out obvious false positives
                            valid_matches = [m[0] for m in actual_matches 
                                          if m[0] and len(m[0].strip()) > 2]
                            if valid_matches:
                                insurance_counts.append(count)
                            break
                except DB_OPERATIONAL_ERRORS:
                    pass
            
            issues['cleartext_insurance'] = sum(insurance_counts)
            
        except DB_ERRORS as e:
            print(f"Warning: Insurance check error: {e}")
            issues['cleartext_insurance'] = 0
        
        # 6. Check for birth dates (should only store age, not birth dates)
        #
        # KNOWN FALSE POSITIVES (do not alarm on these):
        #   lab_manual.kommentar — contains ISO dates as medical context
        #     (e.g. "Laborwert vom 2020-07-20", "Zeckenstich Mai–Jul 2020 25.11.2020").
        #     These are clinically relevant timestamps, not birthdates.
        #     Source: lab_manual import — all entries are intentionally dated.
        #   medications.notes — Klinikaufenthalt / Antibiose-Zeiträume
        #   blood_pressure.notes — Uhrzeitangaben im Schlafkontext
        # The YYYY-MM-DD pattern cannot distinguish between medical dates and
        # birthdates in free-text columns; manual review required for any hit.
        _KNOWN_BIRTHDATE_FP: set[tuple[str, str]] = {
            ('lab_manual',    'kommentar'),
            ('medications',   'notes'),
            ('blood_pressure','notes'),
        }
        try:
            # Look for date patterns like DD.MM.YYYY, YYYY-MM-DD, etc.
            date_patterns = [
                '%__.__.____',  # DD.MM.YYYY
                '____-__-__',   # YYYY-MM-DD
                '%/__/__',      # MM/DD/YY or DD/MM/YY
            ]

            birthdate_counts = []
            for table, column in tables_to_check:
                if (table, column) in _KNOWN_BIRTHDATE_FP:
                    continue
                try:
                    for pattern in date_patterns:
                        count = con.execute(
                            f"SELECT COUNT(*) FROM {table} WHERE {column} LIKE ?",
                            (pattern,)
                        ).fetchone()[0]
                        if count > 0:
                            birthdate_counts.append(count)
                            break
                except DB_OPERATIONAL_ERRORS:
                    pass

            issues['cleartext_birthdates'] = len(birthdate_counts)

        except DB_ERRORS as e:
            print(f"Warning: Birthdate check error: {e}")
            issues['cleartext_birthdates'] = 0
        
    except DB_ERRORS as e:
        print(f"Warning: Compliance check error: {e}")
    finally:
        if own_connection:
            con.close()
    
    return issues


def print_compliance_report(issues: dict[str, int]) -> None:
    """Print a human-readable compliance report."""
    print("\n=== Anonymisierungs-Compliance-Bericht ===")
    print("-" * 50)
    
    total_issues = sum(issues.values())
    if total_issues == 0:
        print("✅ Keine Probleme gefunden - Alle Daten sind korrekt anonymisiert!")
        return
    
    print(f"⚠️  {total_issues} potenzielle Probleme gefunden:\n")
    
    if issues['potential_personal_names'] > 0:
        print(f"  🚫 Potenzielle echte Namen: {issues['potential_personal_names']}")
        print("     → person_ids enthalten Leerzeichen, @-Symbole oder Apostrophe")
    
    if issues['high_precision_gps'] > 0:
        print(f"  🚫 GPS mit hoher Präzision: {issues['high_precision_gps']}")
        print("     → GPS-Punkte mit mehr als 5 Dezimalstellen (>1m Genauigkeit)")
    
    if issues['unpseudonymized_devices'] > 0:
        print(f"  🚫 Nicht-pseudonymisierte Geräte: {issues['unpseudonymized_devices']}")
        print("     → Geräte-Seriennummern ohne SN-Präfix")
    
    if issues['cleartext_emails'] > 0:
        print(f"  🚫 E-Mail-Adressen gefunden: {issues['cleartext_emails']}")
        print("     → Textfelder enthalten E-Mail-Adressen (@-Zeichen)")
    
    if issues['cleartext_insurance'] > 0:
        print(f"  🚫 Versicherungsdaten gefunden: {issues['cleartext_insurance']}")
        print("     → Textfelder enthalten Versicherungsnummern oder -namen")
    
    if issues['cleartext_birthdates'] > 0:
        print(f"  🚫 Mögliche Geburtsdaten gefunden: {issues['cleartext_birthdates']}")
        print("     → Textfelder enthalten YYYY-MM-DD/DD.MM.YYYY-Muster (nur Alter erlaubt)")
        print("     ⚠️  Achtung: lab_manual.kommentar, medications.notes, blood_pressure.notes")
        print("        sind als Known-False-Positives ausgenommen (medizinische Zeitangaben).")
    
    print("\n📋 Empfehlungen:")
    if issues['high_precision_gps'] > 0:
        print("  • Führe: python3 utils/reduce_gps_precision.py aus")
    if issues['unpseudonymized_devices'] > 0:
        print("  • Führe: python3 utils/pseudonymize_existing_devices.py aus")
    if issues['cleartext_emails'] > 0:
        print("  • Führe: python3 utils/scrub_emails.py aus")
    if issues['cleartext_insurance'] > 0 or issues['cleartext_birthdates'] > 0:
        print("  • Prüfe manuell die betroffenen Datensätze auf Versicherungsdaten/Geburtsdaten")
    if issues['potential_personal_names'] > 0:
        print("  • Prüfe manuell die betroffenen person_ids")
    
    print("\n💡 Tipp: Führe diesen Check regelmäßig nach Datenimporten durch!")


# ── Apple Health source-name scrubbing ────────────────────────────────────────

# Patterns that indicate a personal name is embedded in a HealthKit source name.
# "Apple Watch von Firstname" → "Apple Watch"
# "Firstname's Apple Watch"  → "Apple Watch"
# "iPhone von Firstname"       → "iPhone"
_VON_RE  = re.compile(r"^(.+?)\s+von\s+\S+$", re.IGNORECASE)
_APOS_RE = re.compile(r"^\S+(?:'s|s')\s+(.+)$", re.IGNORECASE)


def scrub_apple_source_name(name: str) -> str:
    """Strip personal names from HealthKit sourceName values.

    Examples:
        "Apple Watch von Firstname" → "Apple Watch"
        "Firstname's iPhone"       → "iPhone"
        "Health"                  → "Health"  (unchanged)
    """
    m = _VON_RE.match(name)
    if m:
        return m.group(1).strip()
    m = _APOS_RE.match(name)
    if m:
        return m.group(1).strip()
    return name


# ── Apple Health <Me> attribute scrubbing ────────────────────────────────────

# Maps HealthKit characteristic attributes to their "neutral" values.
_ME_NEUTRALISE = {
    "HKCharacteristicTypeIdentifierDateOfBirth":         "",
    "HKCharacteristicTypeIdentifierBiologicalSex":       "HKBiologicalSexNotSet",
    "HKCharacteristicTypeIdentifierBloodType":           "HKBloodTypeNotSet",
    "HKCharacteristicTypeIdentifierFitzpatrickSkinType": "HKFitzpatrickSkinTypeNotSet",
    "HKCharacteristicTypeIdentifierCardioFitnessMedicationsUse": "",
}


def scrub_me_attributes(attrs: dict) -> dict:
    """Return a copy of a HealthKit <Me> attribute dict with PII removed."""
    out = dict(attrs)
    for key, neutral in _ME_NEUTRALISE.items():
        if key in out:
            out[key] = neutral
    return out
