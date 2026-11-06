# sort_scan_batch.py — Triage/Splitter für gemischte, gescannte Dokumentstapel

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/utils/sort_scan_batch.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Nimmt große, OCR'te Sammel-PDFs (z.B. aus einem Dokumentenscanner mit mehreren unterschiedlichen Dokumenttypen hintereinander) und zerlegt sie in einzelne, nach Kategorie sortierte PDF-Dateien. Erkennt dabei auch Fast-Duplikate (mehrfach gescannte Seiten).

## Relevanz

Ermöglicht die lokale Vorsortierung gemischter Scan-Stapel ohne KI-Beteiligung, essentiell für den Datenschutz beim Einsortieren großer Dokumentenmengen

## Methode

Rein regelbasiert, KEIN LLM (lokal oder Cloud) beteiligt — läuft komplett ohne dass Dokumentinhalte irgendeine KI durchlaufen. Extrahiert Seitentext via pdftotext (poppler-utils, muss bereits vorhanden sein), klassifiziert jede Seite per Schlüsselwort-/ Regex-Heuristik (Laborbefund/Laboranforderung/Arztbrief/Genetik/ Abrechnung/Überweisungsträger/Trennblatt-oder-OCR-Müll/Unklar), erkennt Fast-Duplikate per Jaccard-Ähnlichkeit auf Wort-Shingles (Schwelle konfigurierbar, lose per Default wegen OCR-Rauschen), gruppiert zusammenhängende Seiten derselben Kategorie innerhalb einer Quelldatei zu einem logischen Dokument und schneidet jedes mit pikepdf in eine eigene Ausgabedatei. Erwartet bereits OCR'te PDFs (siehe @limits) — führt selbst kein OCR aus.

## Datenfluss

- **Liest:** `keine`, `Tabellen`, `(reine`, `Datei-Operation)`
- **Schreibt:**

  ```
  keine Tabellen — nur Dateien: <out-dir>/<kategorie>/*.pdf
  + sortierung_bericht.txt (Status/Pfade, keine Inhalts-Snippets)
  ```

## Grenzen

Erwartet bereits OCR'te PDFs (durchsuchbarer Text) — vorher `ocrmypdf` laufen lassen (siehe requirements.txt/onboard.py für Installationshinweis). Gruppierung läuft nur INNERHALB einer Eingabedatei — ein logisches Dokument, das genau an einer Dateigrenze zwischen zwei Eingabe-PDFs geteilt ist, wird nicht automatisch zusammengeführt (wird im Bericht als Randfall an Seite 1/letzter Seite markiert). Klassifizierung ist heuristisch, kein Ersatz für eine inhaltliche Prüfung — Ergebnis immer selbst durchsehen, bevor weiterverarbeitet wird. Keine Datei wird gelöscht, auch "uninteressante" Kategorien (Überweisungsträger, Trennblätter) landen nur in einem eigenen Unterordner, nicht im Papierkorb.

## Aufruf

```bash
python3 sort_scan_batch.py --file scan1_ocr.pdf scan2_ocr.pdf
python3 sort_scan_batch.py --file scan_ocr.pdf --out-dir /pfad/sortiert
python3 sort_scan_batch.py --file scan_ocr.pdf --similarity-threshold 0.6
python3 sort_scan_batch.py --lang en --file scan_ocr.pdf
```
