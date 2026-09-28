# SQL-Spalten-Check gegen das reale Schema

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/check_sql_columns.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Findet SELECT-Statements, die Spalten abfragen, die es in der Zieltabelle nicht gibt. Das ist die Fehlerklasse, wegen der die CLAUDE.md-Regel "Code der parst ist nicht Code der läuft" existiert: Solche Statements kompilieren, bestehen jedes Docstring- und Compliance-Gate und scheitern erst zur Laufzeit — oder, schlimmer, gar nicht sichtbar, wenn sie in einem except-Block verschwinden.

## Relevanz

Schließt die Lücke zwischen "kompiliert" und "läuft". analyse_all erwischt von dieser Fehlerklasse nur, was tatsächlich abstürzt; die in try/except verschluckte Hälfte liefert stillschweigend unvollständige Auswertungen — bei Gesundheitsdaten also falsche Ergebnisse ohne jeden Hinweis darauf.

## Methode

Liest das reale Schema aus sqlite_master (Tabellen UND Views) der konfigurierten Datenbank. Durchsucht dann alle .py unter scripts/ nach einfachen "SELECT spalte, spalte FROM tabelle"-Mustern und vergleicht die Spaltenliste mit PRAGMA table_info. Bewusst konservativ: Statements mit JOIN, Alias-Präfix, Ausdrücken, Aggregatfunktionen oder f-String-Interpolation werden übersprungen, weil sie sich ohne echten SQL-Parser nicht zuverlässig zerlegen lassen. Lieber wenige sichere Treffer als eine Liste mit Fehlalarmen, die niemand mehr liest.

## Datenfluss

- **Liest:** `scripts/**/*.py`, `health.db`, `(nur`, `sqlite_master`, `+`, `PRAGMA`, `table_info)`
- **Schreibt:** `STDOUT/STDERR (Fehlermeldungen)`

## Grenzen

Nur SELECT, kein INSERT/UPDATE. Kein SQL-Parser, sondern eine bewusst enge Heuristik — Statements mit JOIN, Aliasen, Ausdrücken oder dynamisch zusammengesetztem SQL werden nicht geprüft, es gibt also keine Vollständigkeitsgarantie. Geprüft wird gegen EINE konkrete Datenbank: Tabellen, die erst ein noch nie gelaufener Importer anlegt, fehlen dort und werden übersprungen statt gemeldet.

## Aufruf

```bash
python3 scripts/check_sql_columns.py
python3 scripts/check_sql_columns.py --db /pfad/zu/health.db
python3 scripts/check_sql_columns.py --path scripts/analysis --quiet
```
