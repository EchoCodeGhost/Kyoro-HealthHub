#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Unit tests for identity_resolver module.
"""

import pytest
import sqlite3
import hashlib
from pathlib import Path
import tempfile
import shutil
import os

# Import the module
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts" / "modules"))
from identity_resolver import IdentityResolver, resolve_device, resolve_person, reverse_resolve, resolve_display_name


class TestIdentityResolver:
    """Test suite for IdentityResolver."""
    
    def setup_method(self):
        """Setup test environment."""
        # Use temporary directory for testing
        self.test_dir = Path(tempfile.mkdtemp())
        self.identity_db = self.test_dir / "identity.db"
        self.registry_json = self.test_dir / "registry.json"
        
        # Mock the paths
        import identity_resolver
        identity_resolver.IDENTITY_DB_PATH = self.identity_db
        identity_resolver.REGISTRY_PATH = self.registry_json
        
        # Create fresh resolver
        self.resolver = IdentityResolver()
        
    def teardown_method(self):
        """Cleanup test environment."""
        shutil.rmtree(self.test_dir)
    
    def test_deterministic_pseudonym_generation(self):
        """Test that same real value always maps to same pseudonym."""
        # Test device
        pseudo1 = resolve_device("polar_v3")
        pseudo2 = resolve_device("polar_v3")
        assert pseudo1 == pseudo2
        assert pseudo1.startswith("DEV-")
        
        # Test person
        pseudo1 = resolve_person("self")
        pseudo2 = resolve_person("self")
        assert pseudo1 == pseudo2
        assert pseudo1.startswith("PER-")
    
    def test_different_values_different_pseudonyms(self):
        """Test that different real values get different pseudonyms."""
        pseudo1 = resolve_device("polar_v3")
        pseudo2 = resolve_device("polar_h10")
        assert pseudo1 != pseudo2
        
        pseudo1 = resolve_person("self")
        pseudo2 = resolve_person("partner")
        assert pseudo1 != pseudo2
    
    def test_reverse_resolution(self):
        """Test reverse resolution from pseudonym to real value."""
        # Device
        real_device = "polar_v3"
        pseudo = self.resolver.resolve("device", real_device)
        reversed_real = self.resolver.reverse(pseudo)
        assert reversed_real == real_device
        
        # Person
        real_person = "self"
        pseudo = self.resolver.resolve("person", real_person)
        reversed_real = self.resolver.reverse(pseudo)
        assert reversed_real == real_person
    
    def test_reverse_resolution_unknown_pseudonym(self):
        """Test reverse resolution of unknown pseudonym."""
        result = reverse_resolve("UNKNOWN-PSEUDO")
        assert result is None
    
    def test_pseudonym_format(self):
        """Test pseudonym format."""
        dev_pseudo = resolve_device("test_device")
        assert dev_pseudo.startswith("DEV-")
        assert len(dev_pseudo) == 12  # DEV- + 8 hex chars
        
        person_pseudo = resolve_person("test_person")
        assert person_pseudo.startswith("PER-")
        assert len(person_pseudo) == 12  # PER- + 8 hex chars
    
    def test_database_persistence(self):
        """Test that mappings are persisted to database."""
        # Create a mapping
        real_device = "test_device"
        pseudo = self.resolver.resolve("device", real_device)
        
        # Verify it's in the database
        conn = sqlite3.connect(self.identity_db)
        cursor = conn.cursor()
        cursor.execute("SELECT device_id_real FROM device_id_map WHERE pseudo_id = ?", (pseudo,))
        result = cursor.fetchone()
        conn.close()
        
        assert result is not None
        assert result[0] == real_device
    
    def test_caching(self):
        """Test that resolver uses caching."""
        # First call should create mapping
        pseudo1 = resolve_device("cached_device")
        
        # Second call should use cache
        pseudo2 = resolve_device("cached_device")
        
        assert pseudo1 == pseudo2
        
        # Verify only one entry in database
        conn = sqlite3.connect(self.identity_db)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM device_id_map WHERE device_id_real = ?", ("cached_device",))
        count = cursor.fetchone()[0]
        conn.close()
        
        assert count == 1
    
    def test_display_name_resolution(self):
        """Test display name resolution."""
        # Create a device mapping
        real_device = "polar_v3"
        pseudo = self.resolver.resolve("device", real_device)
        
        # Test display name without registry entry
        display_name = self.resolver.resolve_display_name(pseudo)
        assert display_name == real_device
        
        # Create registry with sensor_type
        registry_data = {
            "device_registry": [
                {
                    "device_id": real_device,
                    "sensor_type": "chest_strap"
                }
            ]
        }
        
        with open(self.registry_json, 'w') as f:
            import json
            json.dump(registry_data, f)
        
        # Test display name with registry entry
        display_name = self.resolver.resolve_display_name(pseudo)
        assert display_name == f"{real_device} (chest_strap)"
    
    def test_display_name_person(self):
        """Test display name for person pseudonyms."""
        real_person = "self"
        pseudo = self.resolver.resolve("person", real_person)
        
        display_name = self.resolver.resolve_display_name(pseudo)
        assert display_name == real_person
    
    def test_get_all_mappings(self):
        """Test getting all mappings."""
        # Create some mappings
        resolve_device("device1")
        resolve_device("device2")
        resolve_person("person1")
        
        mappings = self.resolver.get_all_mappings()
        
        assert "device" in mappings
        assert "person" in mappings
        assert len(mappings["device"]) == 2
        assert len(mappings["person"]) == 1
    
    def test_unknown_pseudonym_display_name(self):
        """Test display name for unknown pseudonym."""
        display_name = resolve_display_name("UNKNOWN-PSEUDO")
        assert display_name == "Unknown UNKNOWN-PSEUDO"


def test_hash_determinism():
    """Test that hash generation is deterministic."""
    # Test the hash function directly
    hash_input = "device:polar_v3"
    hash_obj = hashlib.sha256(hash_input.encode('utf-8'))
    hash_hex1 = hash_obj.hexdigest()[:8]
    
    hash_obj2 = hashlib.sha256(hash_input.encode('utf-8'))
    hash_hex2 = hash_obj2.hexdigest()[:8]
    
    assert hash_hex1 == hash_hex2


def test_different_kinds_different_prefixes():
    """Test that different identifier kinds get different prefixes."""
    # This tests the internal _generate_pseudonym method
    resolver = IdentityResolver()
    
    # Access the method through a test
    dev_pseudo = resolver._generate_pseudonym("device", "test")
    person_pseudo = resolver._generate_pseudonym("person", "test")
    
    assert dev_pseudo.startswith("DEV-")
    assert person_pseudo.startswith("PER-")
    assert dev_pseudo != person_pseudo


if __name__ == "__main__":
    pytest.main([__file__, "-v"])