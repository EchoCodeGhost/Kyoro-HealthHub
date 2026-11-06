# dump_scan_to_ods.py — Bestmögliche Tabellen-Extraktion aus OCR'ten Scans nach LibreOffice Calc

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/utils/dump_scan_to_ods.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Für Dokumente, deren Layout zu unregelmäßig für eine automatische Parser-Logik ist (z.B. alte Trend-Berichte mit verschachtelten Mehrdaten-Vergleichsblöcken): extrahiert pdfplumbers bestmögliche Tabellenerkennung pro Seite und dumpt sie als eigenes Tabellenblatt in eine .ods-Datei — zur manuellen Durchsicht/ Korrektur in LibreOffice Calc, statt eine perfekte, aber aufwändige Spezial-Parser-Logik für ein einzelnes altes Dokumentformat zu bauen.

## Relevanz

Ermöglicht die manuelle Aufbereitung schwer parsebarer Scans, essentiell für Altdaten mit unregelmäßigem Layout

## Methode

Nutzt pdfplumber.Page.find_tables(table_settings={vertical_ strategy: text, horizontal_strategy: text}) — textbasierte Spalten-/Zeilenerkennung über Whitespace-Lücken, kein OCR- Neulauf (nutzt die von ocrmypdf bereits eingebettete Text- ebene). Findet find_tables() nichts, fällt die Seite auf reinen Fließtext (eine Spalte) zurück, damit nichts verloren geht. Kein LLM beteiligt.

## Datenfluss

- **Liest:** `keine`, `Tabellen`, `(reine`, `Datei-Operation)`
- **Schreibt:** `keine Tabellen — nur eine .ods-Datei (ein Tabellenblatt pro Seite)`

## Grenzen

Keine inhaltliche Validierung — reiner Best-Effort-Dump der erkannten Tabellenstruktur. Bei sehr unregelmäßigem Layout (mehrere verschachtelte Mini-Tabellen pro Seite, wie bei den alten Trend-Berichten) wird die Spalten-/Zeilenzuordnung nicht zwingend korrekt sein — das ist der Punkt: Mensch korrigiert in Calc, statt dass ein fragiler Parser rät.

## Aufruf

```bash
python3 dump_scan_to_ods.py --file scan.pdf
python3 dump_scan_to_ods.py --file scan1.pdf scan2.pdf --out /pfad/ausgabe.ods
```
