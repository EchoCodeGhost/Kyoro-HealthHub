# Beurer Health Manager Pro → health.db

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/importers/import_beurer.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Importiert CSV-Exporte des Beurer Health Manager Pro in die health.db. Unterstützt Körperzusammensetzung (BF 990), Blutzucker (GL 60), Körpertemperatur (FT 95) und Pulsoximetrie (PO60).

## Relevanz

Ermöglicht den Import von Gesundheitsdaten, essentiell für die umfassende Datenanalyse

## Methode

Liest CSV-Dateien aus ~/Kyoro-HealthHub/imports/beurer/ oder einem expliziten Pfad. Jede CSV-Datei wird geparst und die Daten in die entsprechenden Tabellen geschrieben: body_composition, blood_glucose, measurements (body_temperature, spo2, heart_rate).

## Datenfluss

- **Liest:** `{imports/beurer/}*.csv`, `(Beurer`, `Health`, `Manager`, `Pro`, `Export)`
- **Schreibt:** `health.db (body_composition, blood_glucose, measurements)`

## Grenzen

Keine Validierung der Beurer-Datenqualität. Abhängig von der Korrektheit des CSV-Exports. Keine medizinische Interpretation. Das FT 95 hat drei Messmodi (Körper 34,0-42,2°C, Objekt/Oberfläche 0-80°C, Raum), der CSV-Export (Datum;Uhrzeit;°C;Kommentar; Medikation) enthält aber KEINE Modus-Spalte — eine Objekt-/ Raummodus-Messung ist aus den Exportdaten heraus nicht von einer Körpertemperaturmessung unterscheidbar. Plausibilitätsprüfung: Werte außerhalb des Körpermodus-Bereichs (34,0-42,2°C, s. BODY_TEMP_MIN_C/MAX_C) werden verworfen und gezählt ausgegeben — das deckt aber keine im Objekt-Modus gemessenen Werte ab, die zufällig im plausiblen Körpertemperatur-Bereich liegen (z. B. eine warme Flasche bei ~37°C). Das bleibt ein Restrisiko, nur durch disziplinierte Nutzung im Alltag zu vermeiden (Objekt-Modus- Messungen nicht mit demselben Gerät im selben Zeitraum wie die eigene Fiebermessung loggen), nicht durch den Importer selbst.

## Aufruf

```bash
python3 import_beurer.py                     # all CSVs im Folder
python3 import_beurer.py --file export.csv
python3 import_beurer.py --update            # only neue Daten
python3 import_beurer.py --user Hauptnutzer
```
