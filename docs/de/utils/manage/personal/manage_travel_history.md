# manage_travel_history.py — Reiseverlauf verwalten

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/utils/manage/personal/manage_travel_history.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Erfasst besuchte Regionen und Zeiträume für die spätere Analyse. Ermöglicht die Korrelation von Reisen mit Gesundheitsdaten.

## Relevanz

Bietet Gesundheitsdatenfunktionen, essentiell für die medizinische Datenverarbeitung

## Methode

Speichert unter ~/.config/kyoro/travel_history.json (lokal, nicht im Repo). Unterstützt das Erfassen von Region, Land, Beginn, Ende und Kontext.

## Datenfluss

- **Liest:** `~/.config/kyoro/travel_history.json`
- **Schreibt:** `~/.config/kyoro/travel_history.json`

## Grenzen

Keine Validierung der Regionscodes. Datei liegt ausserhalb des Repos.

## Aufruf

```bash
python3 scripts/utils/manage/personal/manage_travel_history.py list
python3 scripts/utils/manage/personal/manage_travel_history.py add
python3 scripts/utils/manage/personal/manage_travel_history.py add "Region Name" YYYY-MM YYYY-MM-DD
python3 scripts/utils/manage/personal/manage_travel_history.py delete 3
python3 scripts/utils/manage/personal/manage_travel_history.py edit 3
```
