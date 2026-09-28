# rename_ecowitt_source_tag.py — Renames weather_station.source

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/migrations/rename_ecowitt_source_tag.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

import_homeassistant.py taggte Ecowitt-Wetterstationsdaten mit dem exakten Gateway-Modellnamen ('ecowitt_gw3000a') statt nur der Marke. Anders als bei Geraeteklassen-Tags, die fuer die Kalibrierungslogik technisch gebraucht werden (z.B. polar_h10/polar_v3), ist das exakte Wetterstations-Gateway- Modell fuer nichts im Code funktional relevant — nur die Marke zaehlt. Der Importer verwendet jetzt 'ecowitt', diese Migration zieht bereits importierte Datenbanken nach.

## Relevanz

Entfernt eine unnoetig spezifische Geraeteangabe aus einem DB-Wert -- betrifft Datenschutz/Datenhygiene, nicht Funktion.

## Methode

UPDATE weather_station SET source='ecowitt' WHERE source='ecowitt_gw3000a'. Idempotent: prueft vorher, ob ueberhaupt Zeilen mit dem alten Tag existieren.

## Datenfluss

- **Liest:** `health.db`, `(weather_station.source)`
- **Schreibt:** `health.db (weather_station.source only, no other columns changed)`

## Grenzen

Betrifft nur weather_station.source — falls andere Tabellen jemals direkt auf diesen String verweisen sollten (aktuell nicht der Fall), wären die dort nicht mitkorrigiert.

## Aufruf

```bash
python3 scripts/migrations/rename_ecowitt_source_tag.py --dry-run
python3 scripts/migrations/rename_ecowitt_source_tag.py
```
