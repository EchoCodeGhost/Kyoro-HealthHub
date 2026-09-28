# create_medicine_imaging_schema.py — medicine_imaging.db initialisieren

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/utils/create_medicine_imaging_schema.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Initialisiert medicine_imaging.db für medizinische Bilddaten.

## Relevanz

Ermöglicht die Erstellung von Datenbank-Schemata, essentiell für die Datenorganisation und -struktur

## Methode

Tabellen: imaging_studies (übergeordnete Untersuchungen), imaging_files (einzelne Bilddateien), imaging_analysis (VLM-Analyse-Ergebnisse). Modularität: Fundus, Röntgen, MRT, CT, Echo folgen alle diesem Schema. body_part + modality unterscheiden den Bildtyp. Kernlogik liegt in ensure_schema(force=False) OHNE argparse — main() ist nur noch ein duenner CLI-Wrapper darum. Grund: andere Skripte (z.B. import_fundus.py) riefen vorher main() direkt auf, dessen ap.parse_args() dabei den AUFRUFER-Prozess' sys.argv einlas (z.B. import_fundus.py --person X datei.dcm) und mit "unrecognized arguments" abstuerzte, da dieses Skript nur --force kennt.

## Datenfluss

- **Liest:** `Keine`, `(erstellt`, `neues`, `Schema)`
- **Schreibt:** `medicine_imaging.db (Tabellen: imaging_studies, imaging_files, imaging_analysis)`

## Grenzen

Einmalig aufrufen. Wiederholte Ausfuehrung ist idempotent (CREATE IF NOT EXISTS). import_log hatte bis vor kurzem nicht dieselben Spalten wie health.dbs import_log (data_path/rows_skipped fehlten) — modules/base.py's log_import() erwartet diese und stuerzte deshalb bei jedem echten medicine_imaging.db-Import ab, VOR dem commit, sodass auch die eigentlich importierten Zeilen verlorengingen. _migrate() gleicht das jetzt per ALTER TABLE an.

## Aufruf

```bash
python3 scripts/utils/create_medicine_imaging_schema.py
python3 scripts/utils/create_medicine_imaging_schema.py --force
```
