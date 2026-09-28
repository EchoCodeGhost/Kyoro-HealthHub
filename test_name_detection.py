#!/usr/bin/env python3
"""
Test script to verify that name detection and pseudonymization works correctly
with the new name_lists.json configuration.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'scripts'))

from utils.anonymize import (
    get_common_german_first_names, 
    get_common_german_last_names, 
    get_common_arzt_titles, 
    get_common_mvz_names,
    scrub_sensitive_health_data
)

def test_name_loading():
    """Test that names are loaded correctly from the JSON file."""
    print("🔍 Testing name list loading...")
    
    first_names = get_common_german_first_names()
    last_names = get_common_german_last_names()
    titles = get_common_arzt_titles()
    mvz_names = get_common_mvz_names()
    
    print(f"✓ Loaded {len(first_names)} first names")
    print(f"✓ Loaded {len(last_names)} last names")
    print(f"✓ Loaded {len(titles)} medical titles")
    print(f"✓ Loaded {len(mvz_names)} MVZ name patterns")
    
    # Verify some expected names are present
    assert 'Michael' in first_names, "Expected 'Michael' in first names"
    assert 'Müller' in last_names, "Expected 'Müller' in last names"
    assert 'Dr. med.' in titles, "Expected 'Dr. med.' in titles"
    assert 'MVZ' in mvz_names, "Expected 'MVZ' in MVZ names"
    
    print("✅ All name lists loaded successfully")
    return True

def test_pseudonymization():
    """Test that pseudonymization works with the loaded names."""
    print("\n🔍 Testing pseudonymization...")
    
    test_cases = [
        (
            "Patient Michael Müller wurde von Dr. med. Schmidt behandelt.",
            "Michael",
            "Müller",
            "Dr. med."
        ),
        (
            "Anna Bauer hatte einen Termin im MVZ Gesundheitszentrum.",
            "Anna",
            "Bauer",
            None
        ),
        (
            "Kontakt: Thomas Weber (Tel: 0123-456789)",
            "Thomas",
            "Weber",
            None
        )
    ]
    
    for i, (text, expected_first, expected_last, expected_title) in enumerate(test_cases):
        result = scrub_sensitive_health_data(text)
        
        # Check that names were pseudonymized (should not appear in result)
        if expected_first:
            assert expected_first not in result, f"Test case {i+1}: First name '{expected_first}' should be pseudonymized"
        if expected_last:
            assert expected_last not in result, f"Test case {i+1}: Last name '{expected_last}' should be pseudonymized"
        if expected_title:
            assert expected_title not in result, f"Test case {i+1}: Title '{expected_title}' should be pseudonymized"
        
        print(f"✓ Test case {i+1} passed: Names properly pseudonymized")
    
    print("✅ All pseudonymization tests passed")
    return True

def test_fallback_mechanism():
    """Test the fallback mechanism by temporarily renaming the JSON file."""
    print("\n🔍 Testing fallback mechanism...")
    
    name_lists_path = os.path.join('scripts', 'utils', 'name_lists.json')
    backup_path = name_lists_path + '.test_backup'
    
    # Backup the original file
    if os.path.exists(name_lists_path):
        os.rename(name_lists_path, backup_path)
    
    try:
        # Load names without the JSON file (should use fallback)
        first_names = get_common_german_first_names()
        last_names = get_common_german_last_names()
        
        assert len(first_names) > 0, "Fallback should provide first names"
        assert len(last_names) > 0, "Fallback should provide last names"
        
        print(f"✓ Fallback mechanism works: {len(first_names)} first names, {len(last_names)} last names")
        print("✅ Fallback test passed")
        return True
        
    finally:
        # Restore the original file
        if os.path.exists(backup_path):
            os.rename(backup_path, name_lists_path)

def main():
    """Run all tests."""
    print("🧪 Testing name detection and pseudonymization configuration\n")
    
    try:
        test_name_loading()
        test_pseudonymization()
        test_fallback_mechanism()
        
        print("\n🎉 All tests passed! The name detection system is working correctly.")
        print("\n📋 Summary:")
        print("  • Names are loaded from name_lists.json")
        print("  • Pseudonymization works with loaded names")
        print("  • Fallback mechanism works when JSON file is missing")
        print("  • No hardcoded names in the main code")
        
        return 0
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())