# color_scale.py — Farbskala für Score-Werte

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/modules/color_scale.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Definiert die Farbskala für Score-Werte (0-10) mit RGB-Farben. Wird für Visualisierungen verwendet, um Scores farblich darzustellen.

## Relevanz

Bietet Farbskalen-Funktionen, essentiell für die Datenvisualisierung

## Methode

Enthält 11 Werte: 10 farbige Scores (1-10) mit Farbverlauf von Grün (niedrig) zu Rot/Orange (hoch) + Score 0 in Grau (neutral). Bietet Funktionen zum Konvertieren zwischen Score-Werten und RGB-Farben sowie zum Finden der nächstgelegenen Farbe.

## Datenfluss

- **Liest:** `Keine`, `Tabellen`, `(statische`, `Daten)`
- **Schreibt:** `Keine Tabellen (statische Daten)`

## Grenzen

Statische Farbdefinitionen. Keine Dynamik.

## Aufruf

```bash
python color_scale.py
python color_scale.py --help
python color_scale.py --from 2024-01-01 --to 2024-12-31
```
