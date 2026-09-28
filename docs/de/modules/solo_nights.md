# solo_nights.py — Lookup-Hilfsfunktion für Nächte ohne Partner

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/modules/solo_nights.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Bietet is_solo_night(date) für Analyse-Skripte, um Nächte mit garantiert eindeutiger Mikrofon-/Umgebungsdaten-Zuordnung zu erkennen (Sleep-Cycle-Schnarchen, Somneo-Umgebungslärm sind sonst nicht personenspezifisch).

## Relevanz

Ermöglicht personenspezifische Zuordnung von Mikrofon-/Umgebungsdaten, wichtig für Schnarch-/Lärmanalysen

## Methode

Liest ~/.config/kyoro/solo_nights.json (Liste von date_from/date_to/ notes), Datei wird über manage_solo_nights.py gepflegt.

## Datenfluss

- **Liest:** `~/.config/kyoro/solo_nights.json`
- **Schreibt:** `Keine Tabellen (statischer Lookup)`

## Grenzen

Nur so vollständig wie die manuelle Pflege der Config-Datei.

## Aufruf

```bash
from modules.solo_nights import is_solo_night
if is_solo_night("2026-06-15"):
    ...
```
