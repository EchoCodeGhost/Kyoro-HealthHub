# fhir_resources.py — FHIR Resource Builder für Kyoro HealthHub Export

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/exporters/fhir_resources.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Builds FHIR R4 resources (Patient, Observation, Condition, MedicationStatement) from Kyoro database data for FHIR export.

## Relevance

Provides FHIR interfaces, essential for standardized data exchange

## Method

- build_patient_resource(): Creates minimal Patient resource - build_observation(): Creates Observation resource with LOINC coding - build_condition(): Creates Condition resource from clinical events - build_medication_statement(): Creates MedicationStatement from medication data

## Data flow

- **Reads:** `-`, `scripts/exporters/fhir_metric_codes.json`, `(LOINC-Mappings)`, `-`, `health.db`, `(Patientendaten)`, `-`, `medicine.db`, `(Medikamentendaten)`
- **Writes:** `- FHIR-R4 JSON Ressourcen (im Speicher, nicht direkt auf Dateisystem)`

## Limitations

- Read-only access to databases - No validation of input data (expected from caller) - MedicationStatement only implemented if medication data is available

## Usage

```bash
from scripts.exporters.fhir_resources import build_patient_resource, build_observation
```
