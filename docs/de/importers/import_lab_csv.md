# Manuelle Laborbefund-CSVs → health.db (lab_manual)

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/importers/import_lab_csv.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Import von manuell erfassten Laborbefunden aus CSV-Dateien für Longitudinal-Analysen

## Relevanz

Ermöglicht den Import von Laborergebnissen, essentiell für die Integration klinischer Daten

## Methode

Parsen von CSV-Dateien mit festem Format (Kopfzeile Pflicht). Kommentarzeilen (beginnend mit #) werden übersprungen. Numerische Werte werden als Float geparst, textuelle Werte als String. Speicherung in lab_manual-Tabelle mit PRIMARY KEY (date, parameter, labor, person).

## Datenfluss

- **Liest:** `medicine/laborbefunde/*_labor.csv`, `imports/manual/labor*.csv`
- **Schreibt:** `health.db:lab_manual, health.db:import_log`

## Grenzen

Verarbeitet nur Dateien mit allen Pflichtfeldern (datum, parameter, wert). Doppelte Einträge (gleiches Datum, Parameter, Labor, Person) werden ignoriert. OCR-korrigierte Dateien müssen Validierungsregeln einhalten.

## Aufruf

```bash
python3 import_lab_csv.py                    # alle CSVs in Standardverzeichnissen
python3 import_lab_csv.py --update           # nur neue (ignoriert via PRIMARY KEY)
python3 import_lab_csv.py --file /pfad.csv   # einzelne Datei
python3 import_lab_csv.py --dry-run          # Vorschau ohne DB-Schreibzugriff
```
