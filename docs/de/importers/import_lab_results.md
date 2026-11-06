# Laborbefunde PDF → Review-CSV oder medicine.db (lab_manual)

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/importers/import_lab_results.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Importiert Laborbefunde aus PDF-Dateien

## Relevanz

Ermöglicht den Import von Laborergebnissen, essentiell für die Integration klinischer Daten

## Methode

Workflow: 1. python import_lab_results.py datei.pdf to Kyoro-HealthHub/Laborbefunde/YYYY-MM-DD_lab_ocr.csv 2. CSV in LibreOffice/Excel oeffnen, OCR-Errors korrigieren, als YYYY-MM-DD_labor.csv speichern 3. python medical_query.py labor to liest alle CSVs direkt, keine DB noetig 4. python import_lab_results.py --db datei.pdf to Speichert die Daten direkt in medicine.db (Tabelle lab_manual, dieselbe Tabelle wie andere Laborwert-Importer — frueher eine eigene lab_results-Tabelle in health.db, das widersprach der DB-Aufteilungsregel und wurde korrigiert). --dry-run zeigt vor dem echten Import, welche (Datum, Parameter, Labor, Person)-Kombinationen schon existieren, ohne etwas zu schreiben.

## Datenfluss

- **Liest:** `lab_manual`, `(medicine.db)`, `—`, `nur`, `für`, `--dry-run`, `und`, `Duplikat-Check`, `via`, `INSERT`, `OR`, `IGNORE`
- **Schreibt:** `CSV-Dateien oder lab_manual in medicine.db`

## Grenzen

OCR kann ungenau sein. Manuelle Korrektur erforderlich. Der Duplikat-Schutz (UNIQUE auf Datum+Parameter+Labor+Person) greift nur bei exakt gleichem Datum — ein OCR-Lesefehler im Datum bei einem erneuten Scan desselben Befunds wird nicht erkannt. Der VLM-Fallback (bei niedriger OCR-Qualität) läuft ausschließlich mit lokalem LLM-Provider (openvino/ovms/ollama/ lmstudio/mlx) — bei konfiguriertem Cloud-Provider wird der Fallback übersprungen, nicht etwa das Bild trotzdem gesendet. Geht nicht gut mit historischen Trend-Berichten um, die mehrere Datums-Spalten pro Parameter in einer Zeile haben (ein Datum pro Seite wird angenommen) — dafür braucht es einen eigenen, noch zu planenden Importer. Der Labor-/Praxisname (--labor oder Dateiname-Fallback) wird über modules/provider_scrubbing.py pseudonymisiert, aber nur wenn er in der lokalen Provider-Registry steht — ein noch nicht registrierter Name landet unverändert in lab_manual.labor (kein Datenverlust, aber auch keine garantierte Erkennung).

## Aufruf

```bash
python import_lab_results.py datei.pdf
python import_lab_results.py *.pdf
python import_lab_results.py --datum YYYY-MM-DD alter_befund.pdf
python import_lab_results.py --db datei.pdf
python import_lab_results.py --db --dry-run datei.pdf
```
