# fhir_resources.py — FHIR Resource Builder für Kyoro HealthHub Export

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/exporters/fhir_resources.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Erstellt FHIR-R4-Ressourcen (Patient, Observation, Condition, MedicationStatement) aus Kyoro-Datenbankdaten für den FHIR-Export.

## Relevanz

Bietet FHIR-Schnittstellen, essentiell für die standardisierte Datenübertragung

## Methode

- build_patient_resource(): Erstellt minimale Patient-Ressource - build_observation(): Erstellt Observation-Ressource mit LOINC-Codierung - build_condition(): Erstellt Condition-Ressource aus klinischen Ereignissen - build_medication_statement(): Erstellt MedicationStatement aus Medikamentendaten

## Datenfluss

- **Liest:** `-`, `scripts/exporters/fhir_metric_codes.json`, `(LOINC-Mappings)`, `-`, `health.db`, `(Patientendaten)`, `-`, `medicine.db`, `(Medikamentendaten)`
- **Schreibt:** `- FHIR-R4 JSON Ressourcen (im Speicher, nicht direkt auf Dateisystem)`

## Grenzen

- Nur lesender Zugriff auf Datenbanken - Keine Validierung der Eingabedaten (wird von Aufrufer erwartet) - MedicationStatement nur implementiert, wenn Medikamentendaten verfügbar sind

## Aufruf

```bash
from scripts.exporters.fhir_resources import build_patient_resource, build_observation
```
