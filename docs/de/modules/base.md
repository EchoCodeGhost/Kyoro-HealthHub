# base.py — Gemeinsame Hilfsfunktionen für Importer

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/modules/base.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Stellt gemeinsame Hilfsfunktionen und Primitiven für Importer bereit. Dokumentiert in CLAUDE.md.

## Relevanz

Bietet Grundfunktionen für die Modulstruktur, essentiell für die Systemarchitektur

## Methode

Enthält: ImportResult (standardisierter Rückgabewert), resolve_person() (Person-ID aus Argument oder Standard), resolve_timezone() (IANA-Zeitzone), local_date() (UTC → lokales Datum), log_import() (forensisch sicherer Log).

## Datenfluss

- **Liest:** `persons`, `Tabelle`, `(für`, `resolve_timezone)`
- **Schreibt:** `import_log Tabelle (über log_import)`

## Grenzen

Internes Hilfsmodul. Aenderungen der Signaturen brechen alle Importer.

## Aufruf

```bash
python base.py
python base.py --help
python base.py --from 2024-01-01 --to 2024-12-31
```
