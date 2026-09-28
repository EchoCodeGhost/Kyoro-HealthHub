# fhir_validate.py — Strukturelle FHIR-R4(B)-Validierung für den Export-Bundle

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/exporters/fhir_validate.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Validiert das gebaute FHIR-Bundle strukturell (Pflichtfelder, Kardinalitäten, Typen) bevor es auf die Platte geschrieben wird, und bricht mit einer klaren Fehlermeldung ab, wenn die Struktur nicht dem FHIR-Schema entspricht.

## Relevanz

Bietet FHIR-Schnittstellen, essentiell für die standardisierte Datenübertragung

## Methode

- validate_bundle(bundle: dict) -> None: wirft ValueError bei Strukturverstößen, RuntimeError wenn die Validierungs-Bibliothek fehlt. Kein Rückgabewert bei Erfolg.

## Datenfluss

- **Liest:** `nichts`, `von`, `der`, `Platte`, `/`, `nothing`, `from`, `disk`, `—`, `arbeitet`, `nur`, `mit`, `dem`, `übergebenen`, `dict`, `im`, `Speicher`
- **Schreibt:** `nichts / nothing`

## Grenzen

- Validiert nur die Basis-FHIR-R4B-Ressourcenform (Pflichtfelder, Datentypen, Kardinalität) — KEINE Terminologie-Prüfung (ob ein LOINC-Code real existiert), KEINE US-Core- oder andere Profile. - "R4B" statt reinem "R4": siehe Provenienz-Kommentar unten — das verwendete Paket bietet in der installierten Version kein reines R4-Modellpaket an, nur R4B (HL7-Fehlerkorrekturversion von R4, für Bundle/Observation/Condition/Patient/MedicationStatement ohne Strukturbruch gegenüber R4).

## Aufruf

```bash
from fhir_validate import validate_bundle
validate_bundle(bundle_dict)  # raises on failure, returns None on success
```
