#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
identity_resolver.py — Zentrales Identifier-Pseudonym-Resolver-Modul

@tier        infrastructure
@purpose.de  Zentralisierte Pseudonym-Auflösung für Geräte-, Personen-,
             Leistungserbringer- und Quelldatei-Identifikatoren. Erweitert
             das bestehende Seriennummern-Pseudonymisierungsmuster auf
             device_id, person, provider und sourcefile. Einziger
             Zugriffspunkt für alle Identitätsauflösungen.
@purpose.en  Centralized pseudonym resolution for device, person,
             treating-provider, and source-file identifiers. Extends the
             existing serial-number pseudonymization pattern to cover
             device_id, person, provider, and sourcefile. Single access
             point for all identity resolution.
@method.de   Deterministische SHA-256-basierte Pseudonym-Generierung mit Präfixen:
             - DEV-XXXXXXXX für Geräte-IDs
             - PER-XXXXXXXX für Personen-IDs
             - PRV-XXXXXXXX für Anbieter-IDs (kanonischer Registry-Schlüssel
               aus provider_scrubbing.py, nicht der Rohtext)
             - SRC-XXXXXXXX für rohe Quelldatei-Namen (z.B. ein Scanner-
               generierter Stapel-Dateiname, der eine Geräte-/Stapel-ID
               trägt -- selbst nicht direkt personenbezogen, aber ein
               vermeidbarer Rückverfolgungs-Hinweis, sobald ohnehin andere
               Identifikatoren pseudonymisiert werden)
             Der Hash wird mit einem zufälligen, einmalig erzeugten, lokal in
             identity.db gespeicherten Salt kombiniert (salt:typ:real_value,
             wobei "typ" device/person/provider/sourcefile ist). Ohne Salt
             wären device_id/person Wörterbuch-Angriffen ausgesetzt:
             beide Spalten haben extrem geringe Kardinalität (ein paar Dutzend
             bekannte Gerätemodell-Strings, 'self'/'partner'), sodass ein
             unsalted Hash von jedem mit Zugriff auf health.db (explizit auch
             ein extern angebundenes KI-Tool, siehe proposal.md) durch simples
             Durchprobieren aller bekannten Kandidatenwerte gebrochen werden
             könnte — genau die Bedrohung, die dieser Change verhindern soll.
             Speichert Zuordnungen in ~/.config/kyoro/identity.db und bietet
             Vorwärts- (real→pseudo) und Rückwärtsauflösung (pseudo→real) sowie
             menschenlesbare Anzeigenamen für Reports.
@method.en   Deterministic SHA-256-based pseudonym generation with prefixes:
             - DEV-XXXXXXXX for device IDs
             - PER-XXXXXXXX for person IDs
             - PRV-XXXXXXXX for provider IDs (the canonical registry key
               from provider_scrubbing.py, never the raw matched text)
             - SRC-XXXXXXXX for raw source-file names (e.g. a scanner-
               generated batch filename carrying a device/batch ID -- not
               directly identifying on its own, but an avoidable trace once
               other identifiers are pseudonymized anyway)
             The hash is combined with a random, once-generated salt stored
             locally in identity.db (salt:type:real_value, where "type" is
             device/person/provider/sourcefile). Without a salt, device_id/
             person would be vulnerable to a dictionary attack:
             both columns have extremely low cardinality (a few dozen known
             device model strings, 'self'/'partner'), so an unsalted hash
             could be broken by anyone with access to health.db (explicitly
             including a remote-connected AI tool, see proposal.md) simply by
             trying every known candidate value — exactly the threat this
             change is meant to prevent.
             Stores mappings in ~/.config/kyoro/identity.db and provides
             forward (real→pseudo) and reverse (pseudo→real) resolution plus
             human-readable display names for reports.
@reads       <KYORO_ACTIVE_PATIENT_DIR or ~>/.config/kyoro/identity.db (device_id_map, person_map, provider_map, sourcefile_map, device_serial_map)
             ~/.config/kyoro/registry.json (für sensor_type Lookup in resolve_display_name)
@writes      ~/.config/kyoro/identity.db (neue Einträge in device_id_map, person_map, provider_map, sourcefile_map)
@limits.de   Nur lokale Auflösung; keine Netzwerkzugriffe. Pseudonyme sind
             deterministisch aber nicht kryptografisch sicher — für Datenschutz,
             nicht für Sicherheit ausgelegt.

@relevance.de  Bietet Identitätsauflösungsfunktionen, essentiell für die Datenintegration
@relevance.en  Provides identity resolution functions, essential for data integration
@limits.en   Local-only resolution; no network access. Pseudonyms are deterministic
             but not cryptographically secure — designed for privacy, not security.
@usage
    from modules.identity_resolver import resolve_device, resolve_person, resolve_provider, resolve_sourcefile, reverse_resolve, resolve_display_name
    dev_pseudo = resolve_device("polar_v3")  # -> "DEV-8abb425f"
    person_pseudo = resolve_person("self")   # -> "PER-6173fec1"
    provider_pseudo = resolve_provider("dr_mueller_ingolstadt")  # -> "PRV-3fa21c90" (canonical registry key, not raw name)
    sourcefile_pseudo = resolve_sourcefile("BRW5CF370DEF29E_..._ocr.pdf")  # -> "SRC-9c21ab04"
    real_value = reverse_resolve(dev_pseudo) # -> "polar_v3"
    display_name = resolve_display_name(dev_pseudo) # -> "polar_v3 (optical_wrist_gps)"
"""

import sqlite3
import hashlib
import secrets
from pathlib import Path
from typing import Optional, Dict, Any
import json
import os

# Constants
# Same rule as health_config.KYORO_CONFIG_DIR (not imported here to keep this
# module free of the config import chain): a patient instance started with
# KYORO_ACTIVE_PATIENT_DIR must use its own identity.db, never the operator's.
_ACTIVE_PATIENT_DIR = os.environ.get("KYORO_ACTIVE_PATIENT_DIR")
_CONFIG_DIR = (Path(_ACTIVE_PATIENT_DIR) if _ACTIVE_PATIENT_DIR else Path.home()) / ".config" / "kyoro"
IDENTITY_DB_PATH = _CONFIG_DIR / "identity.db"
REGISTRY_PATH = _CONFIG_DIR / "registry.json"

# Pseudonym prefixes
PREFIX_DEVICE = "DEV-"
PREFIX_PERSON = "PER-"
PREFIX_PROVIDER = "PRV-"
PREFIX_SOURCEFILE = "SRC-"

class IdentityResolver:
    """Main identity resolver class."""
    
    def __init__(self):
        """Initialize the identity resolver."""
        self._ensure_identity_db()
        self._ensure_registry()
        self._cache: Dict[str, Dict[str, str]] = {}
        self._salt: str = self._load_or_create_salt()

    def _ensure_identity_db(self) -> None:
        """Ensure identity.db exists with required tables."""
        os.makedirs(IDENTITY_DB_PATH.parent, exist_ok=True)

        with sqlite3.connect(IDENTITY_DB_PATH) as conn:
            cursor = conn.cursor()

            # device_serial_map — Spaltennamen MUESSEN zu utils/anonymize.py,
            # utils/create_identity_schema.py und migrations/
            # pseudonymize_polar_device_serials.py passen. Diese Datei legte die
            # Tabelle frueher als (pseudo_id, device_serial_real) an und gewann das
            # Rennen, weil sie bei jedem DB-Oeffnen laeuft. Danach war
            # CREATE TABLE IF NOT EXISTS dort ein stiller Nulleffekt, und die drei
            # anderen brachen mit "no such column: device_id" bzw. "serial_real" --
            # inklusive des im README dokumentierten Onboardings.
            #
            # Kanonisch ist die reichere Form: sie haelt fest, zu WELCHEM Geraet
            # eine Seriennummer gehoert. Bestehende Tabellen der alten Form werden
            # ersetzt, sofern leer; enthalten sie Daten, bleibt die Migration dem
            # Betreiber ueberlassen statt sie stillschweigend zu verwerfen.
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS device_serial_map (
                    pseudo_id   TEXT PRIMARY KEY,
                    device_id   TEXT NOT NULL,
                    serial_real TEXT NOT NULL,
                    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cols = {r[1] for r in cursor.execute("PRAGMA table_info(device_serial_map)")}
            if "serial_real" not in cols:
                n = cursor.execute("SELECT COUNT(*) FROM device_serial_map").fetchone()[0]
                if n == 0:
                    cursor.execute("DROP TABLE device_serial_map")
                    cursor.execute("""
                        CREATE TABLE device_serial_map (
                            pseudo_id   TEXT PRIMARY KEY,
                            device_id   TEXT NOT NULL,
                            serial_real TEXT NOT NULL,
                            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    """)
                else:
                    import sys as _s
                    print(f"WARNUNG: device_serial_map hat das alte Schema und {n} Zeilen "
                          f"— bitte manuell migrieren (utils/create_identity_schema.py).",
                          file=_s.stderr)

            # Create device_id_map for device_id pseudonyms
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS device_id_map (
                    pseudo_id TEXT PRIMARY KEY,
                    device_id_real TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create person_map for person pseudonyms
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS person_map (
                    pseudo_id TEXT PRIMARY KEY,
                    person_real TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create provider_map for provider (doctor/practice) pseudonyms.
            # provider_real is the CANONICAL provider_registry.json key
            # (see provider_scrubbing.py), never the raw matched text.
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS provider_map (
                    pseudo_id TEXT PRIMARY KEY,
                    provider_real TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create sourcefile_map for raw source-filename pseudonyms (e.g.
            # scanner-generated batch filenames that embed a scan date/time/
            # batch-ID -- not identifying on their own, but an unnecessary
            # breadcrumb once scrubbing other identifiers is the point).
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sourcefile_map (
                    pseudo_id TEXT PRIMARY KEY,
                    sourcefile_real TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create account_pseudo_map if not exists -- Schema MUSS mit
            # utils/create_identity_schema.py uebereinstimmen, der
            # eigentlichen Quelle dieser Tabelle (service-skopierter
            # Composite-Key, Spalte account_pseudo statt pseudo_id). Die
            # vorherige Definition hier (pseudo_id PRIMARY KEY, kein
            # service/person_id) war ein eigenstaendiger, nie synchronisierter
            # Zweit-Entwurf -- griff real nie, weil die Tabelle in jeder
            # echten Installation laengst mit dem anderen Schema existiert
            # (CREATE TABLE IF NOT EXISTS ist dann ein No-op), fiel aber bei
            # einer frischen Test-DB auf und brach reverse()/get_all_mappings().
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS account_pseudo_map (
                    service TEXT NOT NULL,
                    account_pseudo TEXT NOT NULL,
                    account_real TEXT NOT NULL,
                    person_id TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (service, account_pseudo)
                )
            """)

            # Single-row table holding the local secret salt mixed into every
            # pseudonym hash. Without it, low-cardinality values like
            # device_id/person would be dictionary-attackable (see module
            # docstring). Never written to health.db/registry.json.
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS pseudonym_salt (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    salt_hex TEXT NOT NULL
                )
            """)

            conn.commit()

    def _load_or_create_salt(self) -> str:
        """Load the local pseudonym salt, generating one on first use.

        Deterministic pseudonyms must stay stable across processes/reruns
        (INSERT OR IGNORE dedup relies on it), so the salt is generated once
        and persisted — never derived from guessable input.
        """
        with sqlite3.connect(IDENTITY_DB_PATH) as conn:
            cursor = conn.cursor()
            row = cursor.execute("SELECT salt_hex FROM pseudonym_salt WHERE id = 1").fetchone()
            if row:
                return row[0]
            salt_hex = secrets.token_hex(32)
            cursor.execute(
                "INSERT INTO pseudonym_salt (id, salt_hex) VALUES (1, ?)", (salt_hex,)
            )
            conn.commit()
            return salt_hex
    
    def _ensure_registry(self) -> None:
        """Ensure registry.json exists."""
        if not REGISTRY_PATH.exists():
            os.makedirs(REGISTRY_PATH.parent, exist_ok=True)
            with open(REGISTRY_PATH, 'w') as f:
                json.dump({"device_registry": []}, f, indent=2)
    
    def _generate_pseudonym(self, kind: str, real_value: str) -> str:
        """Generate deterministic pseudonym for a given real value."""
        if kind == "device":
            prefix = PREFIX_DEVICE
        elif kind == "person":
            prefix = PREFIX_PERSON
        elif kind == "provider":
            prefix = PREFIX_PROVIDER
        elif kind == "sourcefile":
            prefix = PREFIX_SOURCEFILE
        else:
            raise ValueError(f"Unknown identifier kind: {kind}")
        
        # Create deterministic hash, salted so low-cardinality real_values
        # (device model strings, 'self'/'partner') can't be dictionary-attacked
        # by anyone who only has the pseudonym (e.g. from health.db).
        hash_input = f"{self._salt}:{kind}:{real_value}"
        hash_obj = hashlib.sha256(hash_input.encode('utf-8'))
        hash_hex = hash_obj.hexdigest()[:8]  # Use first 8 chars for readability
        
        return f"{prefix}{hash_hex}"
    
    def _canonicalize_device(self, real_value: str) -> str:
        """Normalize a raw device identifier to its canonical semantic device_id.

        Callers may pass the same physical device under different spellings:
        the SN- serial pseudonym, the raw hex serial, or the semantic name
        (e.g. 'polar_ignite2'). Without this normalization each spelling
        gets hashed into its own DEV-XXXXXXXX pseudonym, silently splitting
        one device's data across multiple IDs (see device_serial_map).
        """
        with sqlite3.connect(IDENTITY_DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT device_id FROM device_serial_map WHERE pseudo_id = ? OR serial_real = ?",
                (real_value, real_value),
            )
            row = cursor.fetchone()
            return row[0] if row else real_value

    def resolve(self, kind: str, real_value: str) -> str:
        """
        Resolve a real identifier to its pseudonym.

        Args:
            kind: Type of identifier ('device', 'person', or 'provider')
            real_value: The real identifier value

        Returns:
            The pseudonym for the given real value
        """
        if kind == "device":
            real_value = self._canonicalize_device(real_value)

        # Check cache first
        cache_key = f"{kind}:{real_value}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        # Generate pseudonym
        pseudo_id = self._generate_pseudonym(kind, real_value)
        
        # Check if already in database
        with sqlite3.connect(IDENTITY_DB_PATH) as conn:
            cursor = conn.cursor()
            
            if kind == "device":
                cursor.execute(
                    "SELECT pseudo_id FROM device_id_map WHERE device_id_real = ?",
                    (real_value,)
                )
            elif kind == "person":
                cursor.execute(
                    "SELECT pseudo_id FROM person_map WHERE person_real = ?",
                    (real_value,)
                )
            elif kind == "provider":
                cursor.execute(
                    "SELECT pseudo_id FROM provider_map WHERE provider_real = ?",
                    (real_value,)
                )
            elif kind == "sourcefile":
                cursor.execute(
                    "SELECT pseudo_id FROM sourcefile_map WHERE sourcefile_real = ?",
                    (real_value,)
                )
            else:
                raise ValueError(f"Unknown identifier kind: {kind}")
            
            result = cursor.fetchone()
            
            if result:
                # Already exists, use existing pseudonym
                existing_pseudo = result[0]
                self._cache[cache_key] = existing_pseudo
                return existing_pseudo
            else:
                # Insert new mapping
                if kind == "device":
                    cursor.execute(
                        "INSERT INTO device_id_map (pseudo_id, device_id_real) VALUES (?, ?)",
                        (pseudo_id, real_value)
                    )
                elif kind == "person":
                    cursor.execute(
                        "INSERT INTO person_map (pseudo_id, person_real) VALUES (?, ?)",
                        (pseudo_id, real_value)
                    )
                elif kind == "provider":
                    cursor.execute(
                        "INSERT INTO provider_map (pseudo_id, provider_real) VALUES (?, ?)",
                        (pseudo_id, real_value)
                    )
                elif kind == "sourcefile":
                    cursor.execute(
                        "INSERT INTO sourcefile_map (pseudo_id, sourcefile_real) VALUES (?, ?)",
                        (pseudo_id, real_value)
                    )

                conn.commit()
                self._cache[cache_key] = pseudo_id
                return pseudo_id
    
    def reverse(self, pseudo_id: str) -> Optional[str]:
        """
        Reverse resolve a pseudonym to its real value.
        
        Args:
            pseudo_id: The pseudonym to resolve
            
        Returns:
            The real identifier value, or None if not found
        """
        # Check cache first (reverse cache)
        reverse_cache_key = f"reverse:{pseudo_id}"
        if reverse_cache_key in self._cache:
            return self._cache.get(reverse_cache_key)
        
        with sqlite3.connect(IDENTITY_DB_PATH) as conn:
            cursor = conn.cursor()
            
            # Determine kind from prefix
            if pseudo_id.startswith(PREFIX_DEVICE):
                cursor.execute(
                    "SELECT device_id_real FROM device_id_map WHERE pseudo_id = ?",
                    (pseudo_id,)
                )
                kind = "device"
            elif pseudo_id.startswith(PREFIX_PERSON):
                cursor.execute(
                    "SELECT person_real FROM person_map WHERE pseudo_id = ?",
                    (pseudo_id,)
                )
                kind = "person"
            elif pseudo_id.startswith(PREFIX_PROVIDER):
                cursor.execute(
                    "SELECT provider_real FROM provider_map WHERE pseudo_id = ?",
                    (pseudo_id,)
                )
                kind = "provider"
            elif pseudo_id.startswith(PREFIX_SOURCEFILE):
                cursor.execute(
                    "SELECT sourcefile_real FROM sourcefile_map WHERE pseudo_id = ?",
                    (pseudo_id,)
                )
                kind = "sourcefile"
            else:
                # Could be a serial pseudonym or other type
                # Check device_serial_map
                cursor.execute(
                    "SELECT serial_real FROM device_serial_map WHERE pseudo_id = ?",
                    (pseudo_id,)
                )
                result = cursor.fetchone()
                if result:
                    self._cache[reverse_cache_key] = result[0]
                    return result[0]
                
                # Check account_pseudo_map -- Spalte heisst account_pseudo,
                # nicht pseudo_id wie bei den anderen *_map-Tabellen (eigenes
                # Schema, siehe CREATE TABLE weiter oben); ohne diese
                # Korrektur lieferte die Abfrage immer 0 Zeilen.
                cursor.execute(
                    "SELECT account_real FROM account_pseudo_map WHERE account_pseudo = ?",
                    (pseudo_id,)
                )
                result = cursor.fetchone()
                if result:
                    self._cache[reverse_cache_key] = result[0]
                    return result[0]
                
                return None
            
            result = cursor.fetchone()
            if result:
                real_value = result[0]
                self._cache[reverse_cache_key] = real_value
                return real_value
            else:
                return None
    
    def resolve_display_name(self, pseudo_id: str) -> str:
        """
        Resolve a pseudonym to a human-readable display name for reports.
        
        Args:
            pseudo_id: The pseudonym to resolve
            
        Returns:
            Human-readable display name
        """
        real_value = self.reverse(pseudo_id)
        if real_value:
            if pseudo_id.startswith(PREFIX_DEVICE):
                # For devices, try to get sensor_type from registry
                sensor_type = self._get_sensor_type_for_device(real_value)
                if sensor_type:
                    return f"{real_value} ({sensor_type})"
                return real_value
            elif pseudo_id.startswith(PREFIX_PERSON):
                # For persons, use the real value as display name
                return real_value
            else:
                # For other types (serials, accounts), return the real value
                return real_value
        else:
            return f"Unknown {pseudo_id}"
    
    def _get_sensor_type_for_device(self, device_id: str) -> Optional[str]:
        """Get sensor_type for a device from registry.json."""
        try:
            with open(REGISTRY_PATH, 'r') as f:
                registry = json.load(f)
                
            for device in registry.get('device_registry', []):
                if device.get('device_id') == device_id:
                    return device.get('sensor_type')
            
            return None
        except (FileNotFoundError, json.JSONDecodeError, KeyError):
            return None
    
    def get_all_mappings(self, kind: Optional[str] = None) -> Dict[str, Dict[str, str]]:
        """
        Get all mappings for debugging/inspection.
        
        Args:
            kind: Optional filter for specific kind ('device', 'person', 'provider', 'serial', 'account')
            
        Returns:
            Dictionary of all mappings
        """
        mappings = {}
        
        with sqlite3.connect(IDENTITY_DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            if kind is None or kind == "device":
                cursor.execute("SELECT pseudo_id, device_id_real FROM device_id_map")
                mappings['device'] = {row['device_id_real']: row['pseudo_id'] for row in cursor.fetchall()}
            
            if kind is None or kind == "person":
                cursor.execute("SELECT pseudo_id, person_real FROM person_map")
                mappings['person'] = {row['person_real']: row['pseudo_id'] for row in cursor.fetchall()}

            if kind is None or kind == "provider":
                cursor.execute("SELECT pseudo_id, provider_real FROM provider_map")
                mappings['provider'] = {row['provider_real']: row['pseudo_id'] for row in cursor.fetchall()}

            if kind is None or kind == "sourcefile":
                cursor.execute("SELECT pseudo_id, sourcefile_real FROM sourcefile_map")
                mappings['sourcefile'] = {row['sourcefile_real']: row['pseudo_id'] for row in cursor.fetchall()}

            if kind is None or kind == "serial":
                cursor.execute("SELECT pseudo_id, serial_real FROM device_serial_map")
                mappings['serial'] = {row['serial_real']: row['pseudo_id'] for row in cursor.fetchall()}
            
            if kind is None or kind == "account":
                # account_pseudo_map hat die Spalte account_pseudo, nicht
                # pseudo_id wie die anderen *_map-Tabellen -- siehe reverse().
                cursor.execute("SELECT account_pseudo, account_real FROM account_pseudo_map")
                mappings['account'] = {row['account_real']: row['account_pseudo'] for row in cursor.fetchall()}
        
        return mappings

# Global instance
default_resolver = IdentityResolver()

# Convenience functions
def resolve_device(device_id: str) -> str:
    """Resolve a device identifier to pseudonym."""
    return default_resolver.resolve("device", device_id)

def resolve_person(person: str) -> str:
    """Resolve a person identifier to pseudonym."""
    return default_resolver.resolve("person", person)

def resolve_provider(canonical_registry_key: str) -> str:
    """Resolve a canonical provider-registry key to pseudonym.

    Takes the canonical key from provider_scrubbing.py's registry match,
    never the raw matched text.
    """
    return default_resolver.resolve("provider", canonical_registry_key)

def resolve_sourcefile(raw_filename: str) -> str:
    """Resolve a raw source filename (e.g. a scanner-generated batch
    filename embedding a device/batch identifier) to a pseudonym."""
    return default_resolver.resolve("sourcefile", raw_filename)

def reverse_resolve(pseudo_id: str) -> Optional[str]:
    """Reverse resolve a pseudonym to real value."""
    return default_resolver.reverse(pseudo_id)

def resolve_display_name(pseudo_id: str) -> str:
    """Resolve pseudonym to human-readable display name."""
    return default_resolver.resolve_display_name(pseudo_id)

if __name__ == "__main__":
    # Test the module
    print("Testing identity resolver...")
    
    # Test device resolution
    dev_pseudo = resolve_device("polar_v3")
    print(f"Device 'polar_v3' -> {dev_pseudo}")
    
    # Test person resolution
    person_pseudo = resolve_person("self")
    print(f"Person 'self' -> {person_pseudo}")
    
    # Test reverse resolution
    real_dev = reverse_resolve(dev_pseudo)
    print(f"Reverse: {dev_pseudo} -> {real_dev}")
    
    # Test display name
    display_name = resolve_display_name(dev_pseudo)
    print(f"Display name for {dev_pseudo}: {display_name}")
    
    print("Identity resolver test completed.")