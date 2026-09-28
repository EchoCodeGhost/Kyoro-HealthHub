# DWD Pollenflug-Gefahrenindex → health.db (pollen_dwd)

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/importers/import_pollen_dwd.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Import des täglichen Pollenflug-Gefahrenindex vom Deutschen Wetterdienst (DWD) OpenData

## Relevanz

Ermöglicht den Import von Gesundheitsdaten, essentiell für die umfassende Datenanalyse Ermöglicht den Import von Gesundheitsdaten, essentiell für die umfassende Datenanalyse

## Methode

Abruf des aktuellen Pollenflug-Status als JSON von DWD OpenData Server. Verarbeitet Daten für heute, morgen und übermorgen. Unterstützt alle DWD-Teilregionen mit Pollenflugvorhersage. Werte: 0-6 (0=kein, 1=gering, 2=gering-mittel, 3=mittel, 4=mittel-hoch, 5=hoch, 6=sehr hoch). Bereichsangaben (z.B. "2-3") werden als Mittelwert gespeichert.

## Datenfluss

- **Liest:** `DWD`, `OpenData`, `API`, `(https://opendata.dwd.de/climate_environment/health/alerts/s31fg.json)`
- **Schreibt:** `health.db:pollen_dwd, health.db:import_log`

## Grenzen

Liefert nur aktuelle und zukünftige Daten (heute + 2 Tage). Historische Daten müssen durch täglichen Import aufgebaut werden. Erfordert Internetverbindung. Keine Authentifizierung nötig.

## Referenzen

- DWD OpenData: https://www.dwd.de/DE/leistungen/opendata/opendata.html DWD Pollenflug: https://www.dwd.de/DE/wetter/wetterundklima_vorort/pollenflug/pollenflug.html

## Aufruf

```bash
python import_pollen_dwd.py
python import_pollen_dwd.py --region 122
python import_pollen_dwd.py --list-regions
```
