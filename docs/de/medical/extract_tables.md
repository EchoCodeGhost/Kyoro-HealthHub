# extract_tables.py — Tabellenextraktion aus PDF-Dokumenten

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/medical/extract_tables.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Extrahiere Tabellen aus gescannten PDF-Dokumenten (z.B. Krankenakten) mittels OCR-Technologie für die weitere Verarbeitung.

## Relevanz

Bietet Gesundheitsdatenfunktionen, essentiell für die medizinische Datenverarbeitung

## Methode

Nutzt PaddleOCR (PPStructureV3) zur Tabellenerkennung und -extraktion. Konvertiert PDF-Seiten zu Bildern, analysiert die Struktur und extrahiert Tabellendaten. Speichert Ergebnisse als CSV-Dateien.

## Datenfluss

- **Liest:** `medicine/krankenakte/*.pdf`
- **Schreibt:** `exports/tables/ Verzeichnis (CSV-Dateien)`

## Grenzen

Abhängig von der OCR-Genauigkeit. Komplexe Tabellenlayouts können Fehler verursachen. Manuelle Nachbearbeitung empfohlen.

## Aufruf

```bash
python medical/extract_tables.py
python medical/extract_tables.py --file path/to/document.pdf
```
