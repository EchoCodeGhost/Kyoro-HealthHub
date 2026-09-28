# manage_treatments.py — Therapie-Einträge verwalten

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/utils/manage/personal/manage_treatments.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Verwaltet Therapie-Termine (Physiotherapie, Osteopathie, Massage, etc.). Ermöglicht das Erfassen von Einzelterminen mit Uhrzeit oder laufenden Kuren über mehrere Tage/Wochen. Daten können mit HRV/Symptomen korreliert werden.

## Relevanz

Bietet Gesundheitsdatenfunktionen, essentiell für die medizinische Datenverarbeitung

## Methode

Einzeltermine (z.B. Osteopathie 15:00-16:00) und laufende Kuren werden über date_from/date_to Feld erfasst. Uhrzeit ist optional. Speichert in ~/.config/kyoro/treatment_history.json (lokal, nicht im Repo).

## Datenfluss

- **Liest:** `~/.config/kyoro/treatment_history.json`
- **Schreibt:** `~/.config/kyoro/treatment_history.json`

## Grenzen

Lokale Datei. Keine automatische Validierung.

## Aufruf

```bash
python3 scripts/utils/manage/personal/manage_treatments.py list [--active]
python3 scripts/utils/manage/personal/manage_treatments.py add
python3 scripts/utils/manage/personal/manage_treatments.py edit 3
python3 scripts/utils/manage/personal/manage_treatments.py stop 3
python3 scripts/utils/manage/personal/manage_treatments.py delete 3
python3 scripts/utils/manage/personal/manage_treatments.py export [--active]
```
