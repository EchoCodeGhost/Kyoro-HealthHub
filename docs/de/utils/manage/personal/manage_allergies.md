# manage_allergies.py — Allergien und Unverträglichkeiten verwalten

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/utils/manage/personal/manage_allergies.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Dokumentiert bekannte Allergien und Unverträglichkeiten (Arzneimittel, Insektengift, Inhalation, Kontakt, Nahrungsmittel, Autoimmun) für Arztbriefe und die KI-Anamnese.

## Relevanz

Bietet Gesundheitsdatenfunktionen, essentiell für die medizinische Datenverarbeitung

## Methode

Speichert unter ~/.config/kyoro/allergies.json (lokal, nicht im Repo). Jeder Eintrag: allergen, type, reaction, severity, diagnosed, notes. Strg+C bricht jederzeit ohne Datenverlust ab.

## Datenfluss

- **Liest:** `~/.config/kyoro/allergies.json`
- **Schreibt:** `~/.config/kyoro/allergies.json`

## Grenzen

Keine klinische Validierung — reine Dokumentation. Arzneimittelallergien immer mit Kreuzreaktivität und Alternativen im notes-Feld dokumentieren.

## Aufruf

```bash
python3 scripts/utils/manage/personal/manage_allergies.py list
python3 scripts/utils/manage/personal/manage_allergies.py add
python3 scripts/utils/manage/personal/manage_allergies.py edit 3
python3 scripts/utils/manage/personal/manage_allergies.py delete 3
python3 scripts/utils/manage/personal/manage_allergies.py export
```
