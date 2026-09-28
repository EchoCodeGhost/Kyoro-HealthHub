# import_pollen_google.py — Google Pollen API → health.db

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/importers/import_pollen_google.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Importiert Pollenflugdaten von der Google Maps Platform Pollen API in die health.db

## Relevanz

Ermöglicht den Import von Gesundheitsdaten, essentiell für die umfassende Datenanalyse

## Methode

Verwendet die Google Pollen API (Universal Pollen Index UPI 0-5) für 13 Pollenarten. Unterstützte Arten: ALDER, ASH, BIRCH, COTTONWOOD, ELM, GRASS, MAPLE, MUGWORT, OAK, OLIVE, PINE, RAGWEED, WEED. Daten werden in die Tabelle pollen_google geschrieben mit Spalten: date, plant_code, upi, category, person. Tägliche Ausführung liefert Daten für heute + bis zu 4 Folgetage. Historische Daten werden durch regelmäßigen Import aufgebaut.

## Datenfluss

- **Liest:** `health_config.json`, `(google_pollen_key)`
- **Schreibt:** `pollen_google, import_log`

## Grenzen

Abhaengig von Google API-Verfuegbarkeit und Key-Konfiguration. Keine medizinische Validierung.

## Aufruf

```bash
python import_pollen_google.py
python import_pollen_google.py --days 5
python import_pollen_google.py --lat 48.1 --lon 11.6 --days 3
```
