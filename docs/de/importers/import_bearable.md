# Bearable CSV-Export → health.db

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/importers/import_bearable.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Importiert umfassende Gesundheits- und Lebensstildaten aus Bearable CSV-Exporten in die health.db. Unterstützt Schlaf, Gesundheitsmessungen, Symptome, Stimmung, Energie, Müdigkeit, Schmerz, Ängste, Stress, Fokus, Übelkeit, Lebensstilfaktoren, Medikamente und Notizen.

## Relevanz

Ermöglicht den Import von Gesundheitsdaten, essentiell für die umfassende Datenanalyse

## Methode

Liest CSV-Dateien aus imports/bearable/ oder einem expliziten Pfad. CSV-Format: 8 Spalten (Datum, formatiertes Datum, Wochentag, Tageszeit, Kategorie, Bewertung/Menge, Detail, Notizen). Mapping: Sleep → sessions + session_metrics, Health measurements → measurements, Symptoms → symptoms, Mood/Energy/etc. → measurements (<name>_score), Factors → bearable_factors, Medications → medications, Notes → bearable_notes.

## Datenfluss

- **Liest:** `{imports/bearable/}*.csv`, `(Bearable`, `Export)`
- **Schreibt:**

  ```
  health.db (sessions, session_metrics, measurements, symptoms,
  bearable_factors, medications, bearable_notes, bearable_custom)
  ```

## Grenzen

Keine Validierung der Bearable-Datenqualität. Keine medizinische Bewertung aus den Daten. Graceful Fallback für unbekannte Kategorien. run()/import_file() reichten person schon vorher korrekt durch; main() hatte aber kein --person-Flag (fest auf OWN_PERSON_ID) — jetzt ergaenzt.

## Aufruf

```bash
python3 import_bearable.py                  # alle CSVs in imports/bearable/
python3 import_bearable.py --file path.csv  # einzelne Datei
python3 import_bearable.py --rebuild        # bearable-Einträge löschen + neu
python3 import_bearable.py --dry-run
python3 import_bearable.py --update         # nur neue Einträge
python3 import_bearable.py --person PER-xxxxxxxx
```
