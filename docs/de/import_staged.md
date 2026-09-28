# Staged Import — Importiert Rohdaten aus dem Staging-Verzeichnis in health.db.

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/import_staged.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Liest Rohdaten aus data/staging/YYYY-MM-DD/ und importiert sie in health.db. Ermöglicht Offline-Import: Daten werden einmal von fetch_daily.py geholt und können beliebig oft neu importiert werden.

## Relevanz

Bietet Gesundheitsdatenfunktionen, essentiell für die medizinische Datenverarbeitung

## Methode

Durchsucht das Staging-Verzeichnis nach JSON-Dateien mit Gesundheitsdaten. Jede Datei wird geparst und die Daten in die entsprechenden Tabellen der health.db geschrieben. Unterstützt verschiedene Datenquellen (Polar, Apple, Oura, Dyson, Ecowitt, etc.) basierend auf der manifest.json. Standortdaten werden aus dem Manifest oder der Konfiguration entnommen.

## Datenfluss

- **Liest:** `data/staging/YYYY-MM-DD/*.json`, `(Rohdaten)`
- **Schreibt:** `health.db (alle Tabellen basierend auf den importierten Daten)`

## Grenzen

Keine Datenvalidierung auf Semantik-Ebene. Abhängig von der Qualität der Rohdaten aus fetch_daily.py. Kein Abgleich mit bestehenden Daten - importiert einfach alle verfügbaren Daten. Keine medizinische Interpretation.

## Aufruf

```bash
python import_staged.py                    # heutiges Staging
python import_staged.py --date 2026-06-01  # bestimmtes Datum
python import_staged.py --list             # verfügbare Staging-Tage anzeigen
python import_staged.py --all              # alle verfügbaren Tage importieren
```
