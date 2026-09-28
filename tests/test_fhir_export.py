#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Test FHIR Export functionality

Tests for:
- FHIR resource builders (Patient, Observation, Condition, MedicationStatement)
- FHIR mapping loader
- FHIR bundle generation
- Unmapped metrics tracking
"""

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
import sys

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from scripts.exporters.fhir_resources import (
    build_patient_resource,
    build_observation,
    build_condition,
    build_medication_statement
)
from scripts.exporters.fhir_mapping import (
    load_metric_code,
    track_unmapped,
    write_unmapped_report
)
from scripts.exporters.fhir_validate import validate_bundle


def test_build_patient_resource():
    """Test Patient resource creation"""
    patient = build_patient_resource("PAT-ABCD")
    
    assert patient["resourceType"] == "Patient"
    assert patient["id"] == "PAT-ABCD"
    assert patient["active"] is True
    assert "identifier" in patient
    print("✓ test_build_patient_resource passed")


def test_build_observation_with_mapping():
    """Test Observation creation with valid LOINC mapping"""
    metric_code = {
        "system": "http://loinc.org",
        "code": "8867-4",
        "display": "Heart rate"
    }
    
    row = {
        "id": "123",
        "timestamp": "2024-01-01T12:00:00Z",
        "metric": "heart_rate",
        "wert_num": 72
    }
    
    observation = build_observation(row, metric_code, "Patient/PAT-ABCD")
    
    assert observation is not None
    assert observation["resourceType"] == "Observation"
    assert observation["status"] == "final"
    assert observation["code"]["coding"][0]["code"] == "8867-4"
    assert observation["valueQuantity"]["value"] == 72
    assert observation["valueQuantity"]["unit"] == "/min"
    assert observation["subject"]["reference"] == "Patient/PAT-ABCD"
    print("✓ test_build_observation_with_mapping passed")


def test_build_observation_without_mapping():
    """Test Observation creation without mapping (should return None)"""
    observation = build_observation({"metric": "unknown"}, None, "Patient/PAT-ABCD")
    assert observation is None
    print("✓ test_build_observation_without_mapping passed")


def test_build_condition():
    """Test Condition resource creation"""
    event = {
        "id": "456",
        "type": "diagnosis",
        "date": "2024-01-01",
        "description": "Hypertension"
    }
    
    condition = build_condition(event, "Patient/PAT-ABCD")
    
    assert condition["resourceType"] == "Condition"
    assert condition["clinicalStatus"]["coding"][0]["code"] == "active"
    assert condition["code"]["text"] == "Hypertension"
    assert condition["subject"]["reference"] == "Patient/PAT-ABCD"
    print("✓ test_build_condition passed")


def test_build_medication_statement():
    """Test MedicationStatement resource creation"""
    medication = {
        "medication_id": "med-001",
        "drug_name": "Ibuprofen",
        "dose_value": 200,
        "dose_unit": "mg",
        "route": "oral",
        "is_chronic": 0,
        "date": "2024-01-01"
    }
    
    statement = build_medication_statement(medication, "Patient/PAT-ABCD")
    
    assert statement["resourceType"] == "MedicationStatement"
    assert statement["status"] == "completed"  # is_chronic=0
    assert statement["medicationCodeableConcept"]["text"] == "Ibuprofen"
    assert statement["subject"]["reference"] == "Patient/PAT-ABCD"
    print("✓ test_build_medication_statement passed")


def test_load_metric_code():
    """Test loading LOINC mappings"""
    # Test existing mapping
    heart_rate_code = load_metric_code("heart_rate")
    assert heart_rate_code is not None
    assert heart_rate_code["code"] == "8867-4"
    
    # Test non-existent mapping
    unknown_code = load_metric_code("unknown_metric")
    assert unknown_code is None
    
    print("✓ test_load_metric_code passed")


def test_track_unmapped():
    """Test tracking unmapped metrics"""
    unmapped = set()
    
    track_unmapped("metric1", unmapped)
    track_unmapped("metric2", unmapped)
    track_unmapped("metric1", unmapped)  # Duplicate should not be added
    
    assert len(unmapped) == 2
    assert "metric1" in unmapped
    assert "metric2" in unmapped
    print("✓ test_track_unmapped passed")


def test_write_unmapped_report():
    """Test writing unmapped metrics report"""
    with tempfile.TemporaryDirectory() as tmpdir:
        unmapped = {"metric1", "metric2", "metric3"}
        report_written = write_unmapped_report(unmapped, Path(tmpdir))
        
        assert report_written is True
        
        report_path = Path(tmpdir) / "fhir_export_unmapped_metrics.txt"
        assert report_path.exists()
        
        content = report_path.read_text()
        assert "# FHIR Export - Unmapped Metrics Report" in content
        assert "metric1" in content
        assert "metric2" in content
        assert "metric3" in content
        print("✓ test_write_unmapped_report passed")


def test_fhir_bundle_structure():
    """Test basic FHIR bundle structure"""
    # Create minimal bundle
    bundle = {
        "resourceType": "Bundle",
        "type": "collection",
        "entry": []
    }
    
    # Add patient
    patient = build_patient_resource("PAT-TEST")
    bundle["entry"].append({
        "fullUrl": "urn:uuid:PAT-TEST",
        "resource": patient
    })
    
    # Add observation
    metric_code = load_metric_code("heart_rate")
    row = {
        "id": "obs-001",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "metric": "heart_rate",
        "wert_num": 70
    }
    observation = build_observation(row, metric_code, "Patient/PAT-TEST")
    bundle["entry"].append({
        "fullUrl": "urn:uuid:obs-001",
        "resource": observation
    })
    
    # Validate bundle structure
    assert bundle["resourceType"] == "Bundle"
    assert bundle["type"] == "collection"
    assert len(bundle["entry"]) == 2
    assert bundle["entry"][0]["resource"]["resourceType"] == "Patient"
    assert bundle["entry"][1]["resource"]["resourceType"] == "Observation"
    print("✓ test_fhir_bundle_structure passed")


def test_validate_bundle_accepts_valid_bundle():
    """A well-formed bundle passes structural validation (no exception)."""
    patient = build_patient_resource("PAT-TEST")
    metric_code = load_metric_code("heart_rate")
    row = {
        "id": "obs-001",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "metric": "heart_rate",
        "wert_num": 70,
    }
    observation = build_observation(row, metric_code, "Patient/PAT-TEST")
    bundle = {
        "resourceType": "Bundle",
        "type": "collection",
        "entry": [
            {"fullUrl": "urn:uuid:PAT-TEST", "resource": patient},
            {"fullUrl": "urn:uuid:obs-001", "resource": observation},
        ],
    }
    validate_bundle(bundle)  # must not raise
    print("✓ test_validate_bundle_accepts_valid_bundle passed")


def test_validate_bundle_rejects_missing_resource_type():
    """A bundle missing the required top-level 'resourceType' must be rejected."""
    malformed_bundle = {
        # "resourceType": "Bundle" deliberately omitted
        "type": "collection",
        "entry": [],
    }
    try:
        validate_bundle(malformed_bundle)
        raise AssertionError(
            "validate_bundle() should have rejected a bundle missing 'resourceType'"
        )
    except ValueError as e:
        assert "resourceType" in str(e)
        print("✓ test_validate_bundle_rejects_missing_resource_type passed")


def test_validate_bundle_rejects_missing_required_resource_field():
    """A bundle whose nested Observation is missing a required field (status)
    must be rejected by the deeper fhir.resources structural check, not just
    the top-level resourceType check."""
    malformed_bundle = {
        "resourceType": "Bundle",
        "type": "collection",
        "entry": [
            {
                "resource": {
                    "resourceType": "Observation",
                    # "status" deliberately omitted — required in FHIR R4B
                    "code": {"text": "incomplete observation"},
                }
            }
        ],
    }
    try:
        validate_bundle(malformed_bundle)
        raise AssertionError(
            "validate_bundle() should have rejected an Observation missing 'status'"
        )
    except ValueError as e:
        assert "status" in str(e) or "validation" in str(e).lower()
        print("✓ test_validate_bundle_rejects_missing_required_resource_field passed")


def run_all_tests():
    """Run all FHIR export tests"""
    print("Running FHIR Export Tests...")
    print("=" * 60)
    
    test_build_patient_resource()
    test_build_observation_with_mapping()
    test_build_observation_without_mapping()
    test_build_condition()
    test_build_medication_statement()
    test_load_metric_code()
    test_track_unmapped()
    test_write_unmapped_report()
    test_fhir_bundle_structure()
    test_validate_bundle_accepts_valid_bundle()
    test_validate_bundle_rejects_missing_resource_type()
    test_validate_bundle_rejects_missing_required_resource_field()

    print("=" * 60)
    print("All FHIR export tests passed! ✓")


if __name__ == "__main__":
    run_all_tests()