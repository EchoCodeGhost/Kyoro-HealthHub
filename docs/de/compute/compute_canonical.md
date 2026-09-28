# Canonical health data (golden record) across all sources (v2 schema).

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/compute/compute_canonical.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Wählt pro (Datum, Metrik) den besten Wert aus allen Quellen nach Confidence-Score und schreibt einen Golden Record. Reine Datenauswahl, keine klinische Aussage.

## Relevanz

Ermöglicht die Berechnung kanonischer Gesundheitsmetriken, essentiell für die Standardisierung

## Methode

CONFIDENCE (Metrik × source_app) bestimmt die Quellen-Priorität; der höchstbewertete Wert je Tag+Metrik wird kanonisch, alle übrigen Quellen landen als JSON in supplements.

## Datenfluss

- **Liest:** `measurements`, `sleep`, `blood_pressure`, `body_composition`, `blood_glucose`, `reproductive_health`
- **Schreibt:** `health_canonical (golden record per day+metric), source_confidence`

## Grenzen

Kein Messverfahren und keine Inferenz — nur Priorisierung vorhandener Werte. Qualität hängt vollständig von der Güte der Quelldaten ab.

## Aufruf

```bash
python3 compute_canonical.py
python3 compute_canonical.py --metric heart_rate
python3 compute_canonical.py --summary
```
