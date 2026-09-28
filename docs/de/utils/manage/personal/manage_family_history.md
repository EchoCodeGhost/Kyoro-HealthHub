# manage_family_history.py — Familienanamnese und genetische Vorbelastungen erfassen

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/utils/manage/personal/manage_family_history.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Dokumentiert Erkrankungen und Auffälligkeiten bei Blutsverwandten, um genetische Prädispositionen und Vererbungsmuster sichtbar zu machen. Unterstützt zwei Ansichten: nach Verwandtem oder nach Erkrankung (Cluster).

## Relevanz

Bietet Gesundheitsdatenfunktionen, essentiell für die medizinische Datenverarbeitung

## Methode

Speichert unter ~/.config/kyoro/family_history.json (lokal, nicht im Repo). Jeder Eintrag: Verwandter, Erkrankung, Status (bestätigt/vermutet), Seite (mütterlich/väterlich), Alter bei Beginn, Notizen. Strg+C bricht jederzeit ohne Datenverlust ab.

## Datenfluss

- **Liest:** `~/.config/kyoro/family_history.json`
- **Schreibt:** `~/.config/kyoro/family_history.json`

## Grenzen

Keine genetische Datenbank — rein anamnestische Dokumentation. Nicht committed; nie als bestätigte Diagnose bei Dritten behandeln.

## Aufruf

```bash
python3 scripts/utils/manage/personal/manage_family_history.py list
python3 scripts/utils/manage/personal/manage_family_history.py list --by-condition
python3 scripts/utils/manage/personal/manage_family_history.py add
python3 scripts/utils/manage/personal/manage_family_history.py delete 3
python3 scripts/utils/manage/personal/manage_family_history.py edit 3
python3 scripts/utils/manage/personal/manage_family_history.py export
```
