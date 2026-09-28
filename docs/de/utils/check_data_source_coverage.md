# check_data_source_coverage — Findet Tabellen mit Daten, die kein Analyseskript abfragt

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/utils/check_data_source_coverage.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Gleicht alle Tabellen aus den Schema-Definitionen (health.db, medicine.db, medicine_imaging.db) gegen die tatsächlichen SQL-Queries aller Analyse-/ Modul-Skripte ab und meldet Tabellen, die Daten enthalten, aber von keinem Skript per FROM/JOIN referenziert werden — genau das Muster, das am 21.08.2026 (siehe git log) zufaellig bei pollen/user_context (Oura-Tags)/ acute_events (Migraene-Detailmetriken) gefunden wurde, hier systematisch statt zufaellig.

## Relevanz

Verhindert, dass Datenquellen unbemerkt unverbunden bleiben — genau die Klasse Bug, die heute Abend viermal per Zufall gefunden wurde.

## Methode

1. Extrahiert Tabellennamen per Regex aus allen CREATE TABLE IF NOT EXISTS- Anweisungen in den drei create_*_schema.py-Dateien. 2. Durchsucht scripts/analysis/**/*.py, scripts/modules/*.py, scripts/compute/*.py, scripts/query/*.py, scripts/utils/*.py und scripts/exporters/*.py nach FROM <table>/JOIN <table>-Vorkommen (case-insensitiv, Wortgrenze) — eine Tabelle gilt als "referenziert", sobald sie in irgendeinem dieser Skripte auch nur einmal vorkommt. Compute-/Query-/ Utils-Skripte sind bewusst mit drin: ecg_rpeaks etwa wird nie in einem analysis/-Skript erwaehnt, sondern nur von compute_orthostatic_detection.py gelesen — ohne diese Verzeichnisse waere das ein Fehlalarm gewesen (so beim ersten Lauf tatsaechlich passiert, s. Git-Historie). 3. Fuer jede nie referenzierte Tabelle: Zeilenanzahl in der jeweiligen DB abfragen. Tabellen mit 0 Zeilen sind kein Befund (nichts zu verpassen); Tabellen mit Daten werden als Kandidaten gemeldet, sortiert nach Zeilenzahl.

## Datenfluss

- **Liest:** `scripts/utils/create_schema.py`, `create_medicine_schema.py`, `create_medicine_imaging_schema.py`, `(table`, `definitions);`, `scripts/analysis/**/*.py`, `scripts/modules/*.py`, `scripts/compute/*.py`, `scripts/query/*.py`, `scripts/utils/*.py`, `scripts/exporters/*.py`, `(query`, `text);`, `health.db`, `medicine.db`, `medicine_imaging.db`, `(row`, `counts)`
- **Schreibt:** `Keine Tabellen (reiner Report auf stdout)`

## Grenzen

Grep-basiert, kein echtes SQL-Parsing: erkennt keine dynamisch (per f-string mit Variablennamen) zusammengesetzten Tabellennamen und keine Zugriffe ueber Compatibility-Views (s. utils/create_schema.py). Export-Profile (exporters/profiles/*.json) sind KEIN Python und werden nicht durchsucht — eine Tabelle, die nur dort (fuer Arztexporte) auftaucht, aber in keinem Python-Skript, gilt bewusst weiterhin als "nicht analysiert" (Export an einen Arztexport ersetzt keine eigene Auswertung). Ein Treffer heisst nur "irgendein Skript erwaehnt die Tabelle im Query-Text", nicht "die Daten fliessen sinnvoll in eine Analyse ein" — false negatives (Tabelle wird zwar erwaehnt, aber nur in einem toten Codepfad) sind moeglich, ebenso wie bei analyse_undocumented_events.py/analyse_pathogen_exposure.py gesehen (Tabelle referenziert, aber Feature nie fertig verdrahtet) — dieses Skript prueft nur die Referenz, nicht die Vollstaendigkeit der Verdrahtung.

## Aufruf

```bash
python3 scripts/utils/check_data_source_coverage.py
python3 scripts/utils/check_data_source_coverage.py --min-rows 10
```
