# manage_environmental_substances.py — Umweltsubstanzen verwalten

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/utils/manage/personal/manage_environmental_substances.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Verwaltet Umweltsubstanzen (Kosmetik, Haushaltsprodukte) für das Trigger-Tracking. Ermöglicht das Erfassen von Substanzen und deren Verwendung für die Korrelation mit Symptomen. Unterstützt automatischen INCI-Inhaltsstoff-Lookup via Open Beauty Facts.

## Relevanz

Bietet Gesundheitsdatenfunktionen, essentiell für die medizinische Datenverarbeitung

## Methode

Speichert unter ~/.config/kyoro/environmental_substances.json (lokal, nicht im Repo). Analog zu manage_medications.py, aber mit eigenen Feldern für Kosmetik und Haushaltsprodukte. Beim Hinzufügen wird automatisch nach INCI-Inhaltsstoffen gesucht (kann mit --no-lookup übersprungen werden). Bestehende Einträge können mit refresh-ingredients <nr> aktualisiert werden.

## Datenfluss

- **Liest:** `~/.config/kyoro/environmental_substances.json`, `Open`, `Beauty`, `Facts`, `API`
- **Schreibt:** `~/.config/kyoro/environmental_substances.json`

## Grenzen

Lokale Datei. Keine automatische Validierung. INCI-Lookup erfordert Netzwerkzugriff und kann fehlschlagen, wenn das Produkt nicht in Open Beauty Facts bekannt ist.

## Aufruf

```bash
python3 scripts/utils/manage/personal/manage_environmental_substances.py list [--active]
python3 scripts/utils/manage/personal/manage_environmental_substances.py add [--no-lookup]
python3 scripts/utils/manage/personal/manage_environmental_substances.py edit 3
python3 scripts/utils/manage/personal/manage_environmental_substances.py stop 3
python3 scripts/utils/manage/personal/manage_environmental_substances.py delete 3
python3 scripts/utils/manage/personal/manage_environmental_substances.py refresh-ingredients 3
python3 scripts/utils/manage/personal/manage_environmental_substances.py export [--active]
```
