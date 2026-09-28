# fhir_mapping.py — FHIR Mapping Utilities

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/exporters/fhir_mapping.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Lädt LOINC/SNOMED-Mappings und verwaltet unmapped Metriken für FHIR-Export.

## Relevanz

Bietet FHIR-Schnittstellen, essentiell für die standardisierte Datenübertragung

## Methode

- load_metric_code(): Lädt LOINC-Mapping für eine Metrik - track_unmapped(): Verfolgt nicht gemappte Metriken für den Report - write_unmapped_report(): Schreibt Report-Datei

## Datenfluss

- **Liest:** `-`, `scripts/exporters/fhir_metric_codes.json`
- **Schreibt:** `- fhir_export_unmapped_metrics.txt (Report-Datei)`

## Grenzen

- Keine Validierung der Eingabedaten - Report wird nur geschrieben, wenn unmapped Metriken vorhanden sind

## Aufruf

```bash
from scripts.exporters.fhir_mapping import load_metric_code, track_unmapped
```
