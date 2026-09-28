# manage_solo_nights.py — Nächte ohne Partner (Bett geteilt ja/nein) verwalten

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/utils/manage/personal/manage_solo_nights.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Erfasst Nächte, in denen allein geschlafen wurde. Sleep-Cycle-Schnarchen und Somneo-Umgebungslärm sind nicht personenspezifisch (Mikrofon erfasst auch Partnerschnarchen/-geräusche) — dieses Verzeichnis erlaubt Analyse- Skripten, Nächte mit garantiert eindeutiger Zuordnung zu markieren.

## Relevanz

Ermöglicht personenspezifische Zuordnung von Mikrofon-/Umgebungsdaten, wichtig für Schnarch-/Lärmanalysen

## Methode

Speichert unter ~/.config/kyoro/solo_nights.json (lokal, nicht im Repo). Jeder Eintrag: date_from, date_to (gleich bei Einzelnacht), notes. is_solo_night(date) in modules/solo_nights.py prüft ein Datum gegen die Liste.

## Datenfluss

- **Liest:** `~/.config/kyoro/solo_nights.json`
- **Schreibt:** `~/.config/kyoro/solo_nights.json`

## Grenzen

Rein manuelle Erfassung, keine automatische Ableitung aus Sensordaten.

## Aufruf

```bash
python3 scripts/utils/manage/personal/manage_solo_nights.py list
python3 scripts/utils/manage/personal/manage_solo_nights.py add
python3 scripts/utils/manage/personal/manage_solo_nights.py add YYYY-MM-DD [YYYY-MM-DD]
python3 scripts/utils/manage/personal/manage_solo_nights.py delete 3
python3 scripts/utils/manage/personal/manage_solo_nights.py edit 2
```
