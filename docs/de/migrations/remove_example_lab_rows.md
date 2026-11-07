# remove_example_lab_rows.py — Entfernt Zeilen aus der Beispieldatei aus lab_manual.

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/migrations/remove_example_lab_rows.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Findet und löscht Laborzeilen, die aus templates/labor.example.csv stammen. Diese synthetischen Werte dürfen nie in Auswertungen oder Arztbriefe gelangen.

## Relevanz

Verhindert, dass erfundene Laborwerte als echte Befunde gelten

## Methode

Vergleicht Datum, Parameter und Wert mit der Beispieldatei statt mit dem Laborname, weil dieser pseudonymisiert wird. Prüft health.db und medicine.db. Ohne --yes wird nur gezählt. Die Audit-Trigger aus open_db halten jede gelöschte Zeile fest.

## Datenfluss

- **Liest:** `templates/labor.example.csv`, `lab_manual`, `in`, `health.db`, `und`, `medicine.db`
- **Schreibt:** `lab_manual (DELETE), audit_log, import_log`

## Grenzen

Ein echter Befund mit identischem Datum, Parameter und Wert würde mitgelöscht; die Ausgabe nennt daher die Zahl pro Datum, und bei Abweichung von der Beispieldatei bricht das Skript nicht ab, sondern zählt nur exakte Treffer.

## Aufruf

```bash
python3 scripts/migrations/remove_example_lab_rows.py        # nur zählen
python3 scripts/migrations/remove_example_lab_rows.py --yes  # löschen
```
