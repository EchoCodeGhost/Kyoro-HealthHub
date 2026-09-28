# Syndrom-Konfiguration Generator

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/analysis/syndromes/_generate.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Generiert Syndrom-Konfigurationsdateien aus der Quelldatei

## Relevanz

Ermöglicht die Gesundheitsdatenanalyse, essentiell für die medizinische Diagnostik

## Methode

Einmaliges Migrationsskript: Liest SYNDROME_CONFIG, SYNDROME_CODES, SYNDROME_SERO und _AFES_CONTEXT aus dem Elternskript (ohne Import, um Nebenwirkungen zu vermeiden), und schreibt eine JSON-Datei pro Syndrom plus _afes_context.txt.

## Datenfluss

- **Liest:** `analyse_postinfectious_diagnose.py`, `(Quelldatei)`
- **Schreibt:** `JSON-Dateien pro Syndrom in scripts/analysis/syndromes/`

## Grenzen

Einmalige Ausfuehrung. Keine automatische Aktualisierung. Bereits durchgeführt — die JSON-Dateien in diesem Ordner sind seither die Quelle der Wahrheit, `analyse_postinfectious_diagnose.py` liest sie zur Laufzeit ein (`_load_syndromes()`) statt sie hartzucodieren. Erneutes Ausführen würde versuchen, aus der (nicht mehr vorhandenen) literalen Dict-Zuweisung zu lesen und bricht deshalb absichtlich mit einer klaren Fehlermeldung ab, statt die JSON-Dateien stillschweigend zu überschreiben oder zu beschädigen.

## Aufruf

```bash
python3 scripts/analysis/syndromes/_generate.py
python3 _generate.py  # from scripts/analysis/syndromes/ directory
```
