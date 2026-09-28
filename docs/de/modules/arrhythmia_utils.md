# arrhythmia_utils.py — Hilfsfunktionen für Arrhythmie-Analyse

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/modules/arrhythmia_utils.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Gemeinsame Hilfsfunktionen für Arrhythmie-Analyse-Skripte.

## Relevanz

Bietet Hilfsfunktionen für die Arrhythmie-Erkennung, essentiell für die kardiologische Analyse

## Methode

Abdeckt: CV-Klassifizierung, Burst-Gruppierung, Pre-Episode-Kontext-Loading, Trainings-Überlappungs-Erkennung und Hilfsdaten-Lader (Blutdruck, etc.). Definiert Schwellwerte für AFib-Klassifizierung basierend auf CV-Werten.

## Datenfluss

- **Liest:** `arrhythmie_episoden`, `blood_pressure`, `Tabellen`
- **Schreibt:** `Keine Tabellen (Hilfsfunktionen)`

## Grenzen

Internes Hilfsmodul — nicht direkt aufrufen. Aenderungen koennen Analyse-Skripte brechen.

## Aufruf

```bash
python arrhythmia_utils.py
python arrhythmia_utils.py --help
python arrhythmia_utils.py --from 2024-01-01 --to 2024-12-31
```
