#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
fhir_resources.py — FHIR Resource Builder für Kyoro HealthHub Export

@tier        infrastructure
@purpose.de  Erstellt FHIR-R4-Ressourcen (Patient, Observation, Condition, MedicationStatement)
             aus Kyoro-Datenbankdaten für den FHIR-Export.
@purpose.en  Builds FHIR R4 resources (Patient, Observation, Condition, MedicationStatement)
             from Kyoro database data for FHIR export.
@method.de  
  - build_patient_resource(): Erstellt minimale Patient-Ressource
  - build_observation(): Erstellt Observation-Ressource mit LOINC-Codierung
  - build_condition(): Erstellt Condition-Ressource aus klinischen Ereignissen
  - build_medication_statement(): Erstellt MedicationStatement aus Medikamentendaten
  
  Alle Ressourcen folgen FHIR R4 Spezifikation.
@method.en  
  - build_patient_resource(): Creates minimal Patient resource
  - build_observation(): Creates Observation resource with LOINC coding
  - build_condition(): Creates Condition resource from clinical events
  - build_medication_statement(): Creates MedicationStatement from medication data
  
  All resources follow FHIR R4 specification.
@reads      
  - scripts/exporters/fhir_metric_codes.json (LOINC-Mappings)
  - health.db (Patientendaten)
  - medicine.db (Medikamentendaten)
@writes     
  - FHIR-R4 JSON Ressourcen (im Speicher, nicht direkt auf Dateisystem)
@limits.de  
  - Nur lesender Zugriff auf Datenbanken
  - Keine Validierung der Eingabedaten (wird von Aufrufer erwartet)
  - MedicationStatement nur implementiert, wenn Medikamentendaten verfügbar sind

@relevance.de  Bietet FHIR-Schnittstellen, essentiell für die standardisierte Datenübertragung
@relevance.en  Provides FHIR interfaces, essential for standardized data exchange
@limits.en  
  - Read-only access to databases
  - No validation of input data (expected from caller)
  - MedicationStatement only implemented if medication data is available
@usage
    from scripts.exporters.fhir_resources import build_patient_resource, build_observation
    
    patient = build_patient_resource("PAT-ABCD")
    observation = build_observation(row, metric_code, "Patient/PAT-ABCD")
"""

from datetime import datetime, timezone
from typing import Dict, Optional
import json
import re
from pathlib import Path
import sys

# Projektkonvention: Import-Pfad für lokale Module
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from health_config import KYORO_MASTER_DIR

# UCUM Einheiten für häufige Metriken
UCUM_UNITS = {
    "heart_rate": {"value": "/min", "system": "http://unitsofmeasure.org", "code": "/min"},
    "hrv_rmssd": {"value": "ms", "system": "http://unitsofmeasure.org", "code": "ms"},
    "hrv_sdnn": {"value": "ms", "system": "http://unitsofmeasure.org", "code": "ms"},
    "oxygen_saturation": {"value": "%", "system": "http://unitsofmeasure.org", "code": "%"},
    "total_sleep_min": {"value": "min", "system": "http://unitsofmeasure.org", "code": "min"},
}


def build_patient_resource(patient_pseudo: str) -> Dict:
    """
    Erstellt eine minimale FHIR Patient-Ressource.
    
    Args:
        patient_pseudo: Patienten-Pseudonym (z.B. "PAT-ABCD")
        
    Returns:
        FHIR Patient-Ressource als Dict
    """
    return {
        "resourceType": "Patient",
        "id": patient_pseudo,
        "identifier": [{
            "system": "https://kyoro.healthhub/patient",
            "value": patient_pseudo
        }],
        "active": True
    }


def build_observation(row: Dict, metric_code: Optional[Dict], patient_ref: str) -> Optional[Dict]:
    """
    Erstellt eine FHIR Observation-Ressource aus einer Datenbankzeile.
    
    Args:
        row: Datenbankzeile mit mindestens 'timestamp' und 'wert_num'
        metric_code: LOINC-Mapping aus fhir_metric_codes.json (oder None)
        patient_ref: FHIR-Referenz auf Patient (z.B. "Patient/PAT-ABCD")
        
    Returns:
        FHIR Observation-Ressource als Dict, oder None wenn metric_code fehlt
    """
    if metric_code is None:
        return None
        
    # Einheit bestimmen
    metric_name = row.get('metric', '')
    unit_info = UCUM_UNITS.get(metric_name, {"value": "1", "system": "http://unitsofmeasure.org", "code": "1"})
    
    return {
        "resourceType": "Observation",
        "id": f"obs-{row.get('id', 'unknown')}",
        "status": "final",
        "code": {
            "coding": [{
                "system": metric_code["system"],
                "code": metric_code["code"],
                "display": metric_code["display"]
            }]
        },
        "subject": {
            "reference": patient_ref
        },
        "effectiveDateTime": row.get('timestamp', datetime.now(timezone.utc).isoformat()),
        "valueQuantity": {
            "value": row.get('wert_num'),
            "unit": unit_info["value"],
            "system": unit_info["system"],
            "code": unit_info["code"]
        }
    }


def build_condition(event: Dict, patient_ref: str) -> Dict:
    """
    Erstellt eine FHIR Condition-Ressource aus einem klinischen Ereignis.
    
    Args:
        event: Klinisches Ereignis mit 'type', 'date', 'description'
        patient_ref: FHIR-Referenz auf Patient (z.B. "Patient/PAT-ABCD")
        
    Returns:
        FHIR Condition-Ressource als Dict
    """
    return {
        "resourceType": "Condition",
        "id": f"cond-{event.get('id', 'unknown')}",
        "clinicalStatus": {
            "coding": [{
                "system": "http://terminology.hl7.org/CodeSystem/condition-clinical",
                "code": "active",
                "display": "Active"
            }]
        },
        "verificationStatus": {
            "coding": [{
                "system": "http://terminology.hl7.org/CodeSystem/condition-ver-status",
                "code": "confirmed",
                "display": "Confirmed"
            }]
        },
        "code": {
            "text": event.get('description', event.get('type', 'Unknown condition'))
        },
        "subject": {
            "reference": patient_ref
        },
        "onsetDateTime": event.get('date', datetime.now(timezone.utc).isoformat())
    }


def build_medication_statement(medication: Dict, patient_ref: str) -> Dict:
    """
    Erstellt eine FHIR MedicationStatement-Ressource aus Medikamentendaten.
    
    Args:
        medication: Medikamenteneintrag mit 'drug_name', 'dose_value', 'dose_unit', etc.
        patient_ref: FHIR-Referenz auf Patient (z.B. "Patient/PAT-ABCD")
        
    Returns:
        FHIR MedicationStatement-Ressource als Dict
    """
    # FHIR id must match ^[A-Za-z0-9\-.]+$. medication_id is normally an
    # integer PK and safe as-is; the ts fallback is a raw UTC ISO timestamp
    # (always contains ":") and would otherwise fail validation the same way
    # the Bundle id did before that fix — sanitize defensively either way.
    med_id = str(medication.get('medication_id', medication.get('ts', 'unknown')))
    med_id = re.sub(r"[^A-Za-z0-9\-.]", "-", med_id)
    return {
        "resourceType": "MedicationStatement",
        "id": f"med-{med_id}",
        "status": "active" if medication.get('is_chronic', 1) else "completed",
        "medicationCodeableConcept": {
            "text": medication.get('drug_name', 'Unknown medication')
        },
        "subject": {
            "reference": patient_ref
        },
        "effectiveDateTime": medication.get('date', medication.get('ts')),
        "dosage": [{
            "text": f"{medication.get('dose_value', '')} {medication.get('dose_unit', '')} {medication.get('route', '')}".strip(),
            "timing": {
                "repeat": {
                    "frequency": 1,
                    "period": 1,
                    "periodUnit": "d"
                }
            },
            "route": {
                "text": medication.get('route', 'Unknown route')
            } if medication.get('route') else None,
            "doseAndRate": [{
                "doseQuantity": {
                    "value": medication.get('dose_value'),
                    "unit": medication.get('dose_unit'),
                    "system": "http://unitsofmeasure.org",
                    "code": medication.get('dose_unit')
                }
            }] if medication.get('dose_value') and medication.get('dose_unit') else None
        }]
    }


if __name__ == "__main__":
    # Beispielnutzung
    patient = build_patient_resource("PAT-ABCD")
    print("Patient Resource:")
    print(json.dumps(patient, indent=2))
    
    # Beispiel Observation
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
    print("\nObservation Resource:")
    print(json.dumps(observation, indent=2))
    
    # Beispiel Condition
    event = {
        "id": "456",
        "type": "diagnosis",
        "date": "2024-01-01",
        "description": "Hypertension"
    }
    condition = build_condition(event, "Patient/PAT-ABCD")
    print("\nCondition Resource:")
    print(json.dumps(condition, indent=2))