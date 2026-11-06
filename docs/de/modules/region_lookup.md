# region_lookup.py — Offline ISO 3166 region for coordinates, worldwide

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/modules/region_lookup.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Ordnet Koordinaten offline der ersten Verwaltungsebene zu (ISO 3166-2, z.B. DE-BY, ES-GC, US-HI) und liefert deren Namen und Fläche. Grundlage für location_store.region_of.

## Relevanz

Liefert die Stufe "region" der Ortsdaten-Policy weltweit statt nur für Deutschland

## Methode

Lädt die mitgelieferte Datei geodata/admin1.json.gz (Natural Earth, vereinfacht, erzeugt von tools/build_region_data.py) beim ersten Aufruf und sucht über einen STRtree (shapely) die Einheit, die den Punkt enthält. Liegt der Punkt in keiner Einheit, gilt die nächste Einheit bis 5 km Entfernung (Küsten, kleine Inseln).

## Datenfluss

- **Liest:** `scripts/modules/geodata/admin1.json.gz`
- **Schreibt:** `(nichts)`

## Grenzen

Umrisse auf ~2 km vereinfacht: an Grenzen kann ein Punkt bis zu dieser Strecke der Nachbareinheit zugeordnet werden. De-facto-Grenzen nach Natural Earth; umstrittene Gebiete folgen dieser Darstellung. In manchen Ländern ist die erste Ebene klein (Basel-Stadt, Paris), dort entspricht die Region fast dem Ort.

## Aufruf

```bash
from modules.region_lookup import lookup, unit_info
code = lookup(49.79, 9.95)          # -> "DE-BY"
info = unit_info("DE-BY")           # -> {"name_de": "Bayern", ...}
```
