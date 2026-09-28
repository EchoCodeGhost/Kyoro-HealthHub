# manage_clinical_events.py — Gesundheitsereignisse verwalten

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/utils/manage/personal/manage_clinical_events.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Verwaltet Gesundheitsereignisse (z.B. Infektionen, Behandlungen, Eingriffe) in einer lokalen JSON-Datei. Ermöglicht das Hinzufügen, Bearbeiten, Löschen und Exportieren von Ereignissen für die Dokumentation.

## Relevanz

Bietet Gesundheitsdatenfunktionen, essentiell für die medizinische Datenverarbeitung

## Methode

Speichert Ereignisse unter ~/.config/kyoro/clinical_events.json (lokal, wird nicht ins Repo committed). Unterstützt verschiedene Ereignistypen mit Datum, Beschreibung und Tags. Export als Markdown-Tabelle möglich.

## Datenfluss

- **Liest:** `~/.config/kyoro/clinical_events.json`
- **Schreibt:** `~/.config/kyoro/clinical_events.json`

## Grenzen

Lokale Datei, wird nicht in die Datenbank oder Versionierung aufgenommen. Keine automatische Validierung der Eingaben.

## Aufruf

```bash
python3 scripts/utils/manage/personal/manage_clinical_events.py list
python3 scripts/utils/manage/personal/manage_clinical_events.py add
python3 scripts/utils/manage/personal/manage_clinical_events.py edit 3
python3 scripts/utils/manage/personal/manage_clinical_events.py delete 3
python3 scripts/utils/manage/personal/manage_clinical_events.py export
```
