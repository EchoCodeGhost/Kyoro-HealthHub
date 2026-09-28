# Kyoro SymptomTrack CSV-Export → health.db (symptoms)

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/importers/import_kyoro_symptoms.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Importiert Kyoro SymptomTrack CSV-Exporte

## Relevanz

Ermöglicht den Import von Symptomdaten, essentiell für die klinische Analyse

## Methode

Liest symptom-history*.csv Exporte aus der Kyoro SymptomTrack App und schreibt in die gemeinsame symptoms-Tabelle (source='kyoro_st'). Gegenueber dem Symptomtagebuch-Importer hat Kyoro ST: - volle ISO-Timestamps (ts-Spalte) - Koerperregion (body_region-Spalte) - Notizen (notes-Spalte) PRIMARY KEY (date, symptom, person, source): bei mehrfachem Eintrag desselben Symptoms am selben Tag gewinnt der Eintrag mit dem hoechsten Wert. CSV-Format (multi-sektionell) mit Metadaten, Eintraegen pro Tag, etc.

## Datenfluss

- **Liest:** `CSV-Dateien`, `aus`, `imports/kyoro-ST/`
- **Schreibt:** `symptoms`

## Grenzen

Multi-sektionelles Format. Abhaengig von App-Export. run()/import_file() reichten person schon vorher korrekt durch; main() hatte aber kein --person-Flag, war also faktisch trotzdem fest auf die eigene Person verdrahtet. Jetzt ergaenzt; --rebuild loescht dadurch auch nur noch die Eintraege der gewaehlten Person.

## Aufruf

```bash
python3 import_kyoro_symptoms.py            # alle CSVs in imports/kyoro-ST/
python3 import_kyoro_symptoms.py --update   # nur neue Eintraege
python3 import_kyoro_symptoms.py --file /pfad/symptom-history.csv
python3 import_kyoro_symptoms.py --rebuild  # kyoro_st-Eintraege loeschen + neu
python3 import_kyoro_symptoms.py --person PER-xxxxxxxx
```
