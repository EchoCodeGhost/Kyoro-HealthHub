# geo_bundesland.py — Deutsche Bundesländer: Namen, ISO-Codes, Zuordnung von Koordinaten

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/modules/geo_bundesland.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Kanonische Liste der 16 deutschen Bundesländer (Name in der Schreibweise der RKI-Datensätze, ISO-3166-2-Code) und Zuordnung von Koordinaten zum Bundesland, für RKI- und AMELAG-Serien.

## Relevanz

Ermöglicht geographische Funktionen, essentiell für die räumliche Analyse

## Methode

Die Zuordnung nutzt die weltweite Regionssuche (modules/region_lookup.py, Natural-Earth-Grenzen). Punkte außerhalb Deutschlands ergeben None statt eines benachbarten Bundeslands.

## Datenfluss

- **Liest:** `scripts/modules/geodata/admin1.json.gz`, `(über`, `region_lookup)`
- **Schreibt:** `Keine Tabellen (statische Daten)`

## Grenzen

Grenzen auf ~2 km vereinfacht, die Quelle selbst ist an Grenzen auf etwa 1–2 km genau: Orte direkt an einer Landes- oder Staatsgrenze können der Nachbareinheit zugeordnet werden.

## Aufruf

```bash
from modules.geo_bundesland import bundesland_of
bundesland_of(48.14, 11.58)  # -> ("Bayern", "BY")
bundesland_of(47.80, 13.04)  # -> None (Österreich)
```
