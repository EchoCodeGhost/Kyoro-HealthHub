# geo_bundesland.py — Deutsche Bundesländer: Namen, ISO-Codes, Zentroid-Koordinaten

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/modules/geo_bundesland.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Kanonische Liste der 16 deutschen Bundesländer (Name, ISO-3166-2-Code, ungefähre Zentroid-Koordinaten) plus Zuordnung von Heimatkoordinaten zum nächstgelegenen Bundesland — analog zu _nearest_region in import_pollen_dwd.py, aber für Bundesland-Ebene statt DWD-Teilregionen.

## Relevanz

Ermöglicht geographische Funktionen, essentiell für die räumliche Analyse

## Methode

Euklidische Distanz zu Landeshauptstadt-Koordinaten (ausreichend genau für eine Bundesland-Zuordnung, kein echtes Polygon-Matching).

## Datenfluss

- **Liest:** `Keine`, `Tabellen`, `(statische`, `Daten)`
- **Schreibt:** `Keine Tabellen (statische Daten)`

## Grenzen

Grenznahe Koordinaten können dem falschen Nachbar-Bundesland zugeordnet werden (Zentroid-Näherung, keine Polygongrenzen).

## Aufruf

```bash
from modules.geo_bundesland import nearest_bundesland
name, code = nearest_bundesland(48.14, 11.58)  # -> ("Bayern", "BY")
```
