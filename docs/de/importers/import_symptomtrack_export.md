# Kyoro SymptomTrack JSON-Export → health.db (symptoms)

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/importers/import_symptomtrack_export.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Importiert Kyoro SymptomTrack-JSON-Exporte (GET /api/export) in die gemeinsame symptoms-Tabelle. Ermöglicht Symptom-Daten von einem zweiten Gerät (z.B. Familienmitglied) mit einer separaten --person-ID einzuspielen, ohne das Kyoro SymptomTrack-Backend zu verändern.

## Relevanz

Ermöglicht den Import von Symptomdaten, essentiell für die klinische Analyse

## Methode

Liest symptomtrack_export_*.json Dateien (Feld symptom_entries[]). Felder: id, timestamp (ISO 8601), symptom, kategorie, wert_num, wert_text, note, source. Schreibt in symptoms mit source='symptomtrack_export' (INSERT OR IGNORE auf PRIMARY KEY (date, symptom, person, source)). Migräne- und AFib-Einträge (migraine_entries, afib_entries) sind Kyoro SymptomTrack-interne Sondertabellen ohne Entsprechung in health.db und werden übersprungen.

## Datenfluss

- **Liest:** `symptomtrack_export_YYYY-MM-DD.json`, `(Kyoro`, `SymptomTrack`, `/api/export`, `output)`
- **Schreibt:** `symptoms`

## Grenzen

Kein Re-Import von Migräne/AFib-Episoden. Nur tagesweise Deduplizierung per PRIMARY KEY — mehrere Einträge desselben Symptoms am selben Tag werden übersprungen nach dem ersten INSERT.

## Aufruf

```bash
python3 import_symptomtrack_export.py symptomtrack_export_2026-07-08.json
python3 import_symptomtrack_export.py symptomtrack_export.json --person oma
```
