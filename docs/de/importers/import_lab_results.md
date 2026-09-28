# Laborbefunde PDF → Review-CSV oder health.db

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/importers/import_lab_results.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Importiert Laborbefunde aus PDF-Dateien

## Relevanz

Ermöglicht den Import von Laborergebnissen, essentiell für die Integration klinischer Daten

## Methode

Workflow: 1. python import_lab_results.py datei.pdf to Kyoro-HealthHub/Laborbefunde/YYYY-MM-DD_lab_ocr.csv 2. CSV in LibreOffice/Excel oeffnen, OCR-Errors korrigieren, als YYYY-MM-DD_labor.csv speichern 3. python medical_query.py labor to liest alle CSVs direkt, keine DB noetig 4. python import_lab_results.py --db datei.pdf to Speichert die Daten direkt in der DB

## Datenfluss

- **Liest:** `PDF-Dateien`, `(Laborbefunde)`
- **Schreibt:** `CSV-Dateien oder lab_results in health.db`

## Grenzen

OCR kann ungenau sein. Manuelle Korrektur erforderlich.

## Aufruf

```bash
python import_lab_results.py datei.pdf
python import_lab_results.py *.pdf
python import_lab_results.py --datum YYYY-MM-DD alter_befund.pdf
python import_lab_results.py --db datei.pdf
```
