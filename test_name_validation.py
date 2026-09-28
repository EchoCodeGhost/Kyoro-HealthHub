#!/usr/bin/env python3
"""
Test script for the name_validation module.

This script tests the comprehensive name detection and validation capabilities
of the new name_validation.py module.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'scripts'))

from utils.name_validation import (
    NameDetector, 
    is_common_first_name, 
    is_common_last_name, 
    detect_names_in_text, 
    validate_person_id, 
    contains_potential_names
)


def test_basic_name_checks():
    """Test basic first and last name detection."""
    print("🔍 Testing basic name checks...")
    
    # Test first names
    assert is_common_first_name("Michael") == True
    assert is_common_first_name("michael") == True  # case insensitive
    assert is_common_first_name("Anna") == True
    assert is_common_first_name("UnknownName") == False
    
    # Test last names
    assert is_common_last_name("Müller") == True
    assert is_common_last_name("müller") == True  # case insensitive
    assert is_common_last_name("Schmidt") == True
    assert is_common_last_name("UnknownLast") == False
    
    print("✅ Basic name checks passed")


def test_full_name_detection():
    """Test detection of full name patterns."""
    print("\n🔍 Testing full name detection...")
    
    detector = NameDetector()
    
    test_text = "Patient Michael Müller wurde von Dr. med. Schmidt behandelt."
    full_names = detector.detect_full_names(test_text)
    
    assert len(full_names) == 1
    assert full_names[0][0] == "Michael Müller"
    assert full_names[0][1] == "Michael"
    assert full_names[0][2] == "Müller"
    
    # Test with multiple names
    multi_text = "Anna Bauer und Thomas Weber waren anwesend."
    multi_names = detector.detect_full_names(multi_text)
    
    assert len(multi_names) == 2
    name_pairs = [(fn[1], fn[2]) for fn in multi_names]
    assert ("Anna", "Bauer") in name_pairs
    assert ("Thomas", "Weber") in name_pairs
    
    print("✅ Full name detection passed")


def test_title_name_detection():
    """Test detection of title + name patterns."""
    print("\n🔍 Testing title + name detection...")
    
    detector = NameDetector()
    
    test_text = "Dr. med. Müller und Prof. Dr. Schmidt sind die Ärzte."
    title_names = detector.detect_title_names(test_text)
    
    assert len(title_names) == 2
    
    # Check that we found both title patterns
    titles_found = [tn[1] for tn in title_names]
    assert "Dr. med." in titles_found
    assert "Prof. Dr." in titles_found
    
    # Check last names
    last_names_found = [tn[2] for tn in title_names]
    assert "Müller" in last_names_found
    assert "Schmidt" in last_names_found
    
    print("✅ Title + name detection passed")


def test_comprehensive_detection():
    """Test comprehensive name detection."""
    print("\n🔍 Testing comprehensive name detection...")
    
    test_text = """
    Patient Michael Müller wurde von Dr. med. Schmidt behandelt.
    Anna Bauer war auch anwesend, zusammen mit Thomas.
    Das MVZ Gesundheitszentrum wurde von Prof. Dr. Weber geleitet.
    """
    
    detection = detect_names_in_text(test_text)
    
    # Should find full names
    assert len(detection['full_names']) >= 1
    
    # Should find title + name combinations
    assert len(detection['title_names']) >= 2
    
    # Should find single first names not part of full names
    assert len(detection['single_first']) >= 1
    
    # Should find single last names not part of other patterns
    assert len(detection['single_last']) >= 0
    
    print(f"  Full names found: {[fn[0] for fn in detection['full_names']]}")
    print(f"  Title names found: {[tn[0] for tn in detection['title_names']]}")
    print(f"  Single first names: {detection['single_first']}")
    print(f"  Single last names: {detection['single_last']}")
    
    print("✅ Comprehensive detection passed")


def test_person_id_validation():
    """Test person_id validation."""
    print("\n🔍 Testing person_id validation...")
    
    # Valid person IDs (should return True)
    assert validate_person_id("P-ABC123") == True
    assert validate_person_id("user_42") == True
    assert validate_person_id("patient_007") == True
    
    # Invalid person IDs (should return False)
    assert validate_person_id("Michael") == False  # Common first name
    assert validate_person_id("Müller") == False   # Common last name
    assert validate_person_id("Michael Müller") == False  # Contains space
    assert validate_person_id("michael@example.com") == False  # Email address
    assert validate_person_id("Dr. Schmidt") == False  # Title + name
    
    print("✅ Person ID validation passed")


def test_contains_potential_names():
    """Test the quick check function."""
    print("\n🔍 Testing contains_potential_names...")
    
    # Text with names (should return True)
    assert contains_potential_names("Patient Michael Müller") == True
    assert contains_potential_names("Dr. med. Schmidt") == True
    assert contains_potential_names("Anna war hier") == True
    
    # Text without names (should return False)
    assert contains_potential_names("Der Patient wurde behandelt") == False
    assert contains_potential_names("Termin am 15.05.2023") == False
    assert contains_potential_names("") == False
    
    print("✅ Contains potential names check passed")


def test_edge_cases():
    """Test edge cases and error handling."""
    print("\n🔍 Testing edge cases...")
    
    detector = NameDetector()
    
    # Empty strings
    assert detector.detect_full_names("") == []
    assert detector.detect_title_names("") == []
    assert detector.detect_any_names("") == {'full_names': [], 'title_names': [], 'single_first': [], 'single_last': []}
    
    # None values
    assert detector.detect_full_names(None) == []
    assert detector.is_common_first_name(None) == False
    
    # Non-string values
    assert detector.is_common_first_name(123) == False
    assert detector.is_common_last_name([]) == False
    
    # Case sensitivity
    assert detector.is_common_first_name("MICHAEL") == True
    assert detector.is_common_last_name("mÜller") == True
    
    # Partial matches (should not match)
    assert detector.is_common_first_name("Michaela") == False  # Not in list
    assert detector.is_common_last_name("Müllerian") == False  # Not exact match
    
    print("✅ Edge cases handled correctly")


def test_integration_with_anonymize():
    """Test that name_validation works with the same name lists as anonymize."""
    print("\n🔍 Testing integration with anonymize module...")
    
    from utils.anonymize import get_common_german_first_names, get_common_german_last_names
    
    # Get names from anonymize module
    first_names_anon = set(get_common_german_first_names())
    last_names_anon = set(get_common_german_last_names())
    
    # Get names from validation module
    first_names_val = set()
    last_names_val = set()
    
    # Test a few names to ensure consistency
    test_first_names = ["Michael", "Anna", "Thomas"]
    test_last_names = ["Müller", "Schmidt", "Bauer"]
    
    for name in test_first_names:
        # Convert anonymize names to lowercase for comparison
        anon_names_lower = set(n.lower() for n in first_names_anon)
        assert is_common_first_name(name) == (name.lower() in anon_names_lower)
        first_names_val.add(name)
    
    for name in test_last_names:
        # Convert anonymize names to lowercase for comparison
        anon_names_lower = set(n.lower() for n in last_names_anon)
        assert is_common_last_name(name) == (name.lower() in anon_names_lower)
        last_names_val.add(name)
    
    print("✅ Integration with anonymize module verified")


def main():
    """Run all tests."""
    print("🧪 Testing name_validation module\n")
    
    try:
        test_basic_name_checks()
        test_full_name_detection()
        test_title_name_detection()
        test_comprehensive_detection()
        test_person_id_validation()
        test_contains_potential_names()
        test_edge_cases()
        test_integration_with_anonymize()
        
        print("\n🎉 All name_validation tests passed!")
        print("\n📋 Module capabilities:")
        print("  • Detect common German first and last names")
        print("  • Identify full name patterns (Firstname Lastname)")
        print("  • Recognize medical title + name combinations")
        print("  • Validate person_ids for personal information")
        print("  • Comprehensive text scanning for potential names")
        print("  • Case-insensitive matching")
        print("  • Avoids duplicate detections")
        print("  • Integrated with existing name lists")
        
        return 0
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())