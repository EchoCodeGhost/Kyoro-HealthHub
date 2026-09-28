# endemic_matching — Geteilte Geo-/Zeit-Logik für strukturelle Endemie-Treffer

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/modules/endemic_matching.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Buendelt die Distanz-, Radius- und "zeitlose Quelle"-Logik, die bis vor kurzem fast identisch in analyse_outbreak_exposure.py, analyse_pathogen_exposure.py und analyse_postinfectious_diagnose.py dupliziert war -- jeder Bugfix musste dort bislang dreimal einzeln nachgezogen werden.

## Relevanz

Ohne dieses Modul muss jeder zukuenftige Fix an der Endemie-/FSME-Matching-Logik erneut in bis zu drei Dateien synchron nachgezogen werden -- genau das Muster, das die heutige Session mehrfach durchlaufen musste.

## Methode

geo_dist_km(): Standard-Haversine-Formel. resolve_radius_km(): nutzt einen pro-Eintrag gesetzten radius_km-Override, sonst einen Default abhaengig davon, ob die Quelle in TIMELESS_SOURCES steht (200 km) oder nicht (100 km). since_floor_ok(): vergleicht ein optionales since_date gegen ein Referenzdatum (i.d.R. Aufenthalts- ende) -- endet der Aufenthalt vor since_date, gilt das (juengere, aktiv expandierende) Risiko als nicht anwendbar.

## Datenfluss

- **Liest:** `Keine`, `(reine`, `Funktionsbibliothek`, `keine`, `DB-/Dateizugriffe)`
- **Schreibt:** `Keine`

## Grenzen

Deckt bewusst NUR die Distanz-/Radius-/Zeitlos-Logik ab, nicht den komplexeren regionsbasierten Text-Abgleich (Insel-Gruppen, "Gesamt*"-Sonderfaelle etc.) -- der bleibt je Skript eigenstaendig, da er an die jeweilige lokale Datenform (dict vs. Stay-Dataclass) gekoppelt ist und sich in den drei Skripten bereits leicht unterschiedlich verhaelt (z.B. hat der Diagnose-Motor keine Inselgruppen-Sonderregel noetig).

## Aufruf

```bash
from modules.endemic_matching import geo_dist_km, resolve_radius_km, since_floor_ok, TIMELESS_SOURCES
radius = resolve_radius_km(outbreak_dict)
if geo_dist_km(lat1, lon1, lat2, lon2) <= radius: ...
```
