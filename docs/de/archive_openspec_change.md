# archive_openspec_change.py — Archive completed OpenSpec change

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/archive_openspec_change.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Verschiebt ein abgeschlossenes OpenSpec-Change-Verzeichnis in den archive/ Ordner und dokumentiert den Abschluss.

## Relevanz

Bietet Gesundheitsdatenfunktionen, essentiell für die medizinische Datenverarbeitung

## Methode

1. Validiert dass alle tasks.md Checkboxen abgehakt sind 2. Verschiebt Verzeichnis von changes/ nach changes/archive/ 3. Erstellt Archiv-Metadaten mit Abschlussdatum

## Datenfluss

- **Liest:** `openspec/changes/<change_name>/`
- **Schreibt:** `openspec/changes/archive/<change_name>/`

## Grenzen

Keine automatische Validierung der Aufgabenabhaken — manuelle Prüfung erforderlich. Kein Rollback nach Archivierung.

## Aufruf

```bash
python3 scripts/archive_openspec_change.py pseudonymize-device-person-identifiers
python3 scripts/archive_openspec_change.py --list-pending
```
