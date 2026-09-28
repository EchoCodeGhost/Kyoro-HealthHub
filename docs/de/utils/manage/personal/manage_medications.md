# manage_medications.py — Medikamente und Ergänzungsmittel verwalten

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/utils/manage/personal/manage_medications.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Verwaltet Medikamente, Nahrungsergänzungsmittel und pflanzliche Präparate in einer lokalen JSON-Datei. Ermöglicht das Erfassen von Einnahmezeiträumen und Dosierungen für die Korrelation mit Gesundheitsdaten.

## Relevanz

Bietet Gesundheitsdatenfunktionen, essentiell für die medizinische Datenverarbeitung

## Methode

Speichert unter KYORO_CONFIG_DIR/medication_history.json (lokal, nicht im Repo). Unterstützt verschiedene Kategorien und Dosierungsangaben.

## Datenfluss

- **Liest:** `KYORO_CONFIG_DIR/medication_history.json`
- **Schreibt:** `KYORO_CONFIG_DIR/medication_history.json`

## Grenzen

Lokale Datei. Keine automatische Validierung.

## Aufruf

```bash
python3 scripts/utils/manage/personal/manage_medications.py list [--active]
python3 scripts/utils/manage/personal/manage_medications.py add
python3 scripts/utils/manage/personal/manage_medications.py edit 3
python3 scripts/utils/manage/personal/manage_medications.py stop 3
python3 scripts/utils/manage/personal/manage_medications.py delete 3
python3 scripts/utils/manage/personal/manage_medications.py export [--active]
```
