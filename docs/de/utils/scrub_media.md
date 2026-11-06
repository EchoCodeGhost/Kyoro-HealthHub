# scrub_media.py — Metadaten, Adressen, Namen, Nummern und Orte aus Bildern und PDFs melden oder entfernen

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/utils/scrub_media.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Kommandozeile für modules.media_redaction: zeigt, welche Metadaten (EXIF, GPS, PDF-Info, XMP, Anhänge, JavaScript) und welche Adressen, Namen, Telefon- und Versichertennummern, Koordinaten und persönlichen Ortsnamen in Dateien stecken, und schreibt bereinigte Kopien. Alles lokal, Originale bleiben unverändert.

## Relevanz

Macht Bild- und PDF-Bereinigung ohne Import nutzbar, etwa vor dem Teilen von Dateien

## Methode

Unterbefehle: report (Metadaten anzeigen, optional als JSON exportieren), scrub (eine Datei bereinigen), scrub-dir (Ordner rekursiv in einen Zielordner), check (Exit-Code 1, wenn Metadaten, Adressen oder Namen gefunden werden). Werte werden nur mit --show-values ausgegeben. Adressen, Namen, Nummern und Orte werden nie im Klartext gemeldet, nur als Anzahl.

## Datenfluss

- **Liest:** `Bild-`, `und`, `PDF-Dateien`, `~/.config/kyoro/health_config.json`, `(optional)`
- **Schreibt:** `Bereinigte Kopien am Zielort, optional JSON-Report (--json-out)`

## Grenzen

Überschreibt nie das Original (Ziel muss ein anderer Pfad sein). Ohne OCR/poppler wird nur die Metadaten-Bereinigung ausgeführt und eine Warnung ausgegeben. Exit-Codes: 0 sauber, 1 Funde, 2 Werkzeuge fehlen oder Fehler (mit --strict).

## Aufruf

```bash
python -m utils.scrub_media report befund.pdf foto.jpg
python -m utils.scrub_media report ordner/ --json-out report.json
python -m utils.scrub_media scrub befund.pdf sauber/befund.pdf
python -m utils.scrub_media scrub-dir eingang/ ausgang/ --strict
python -m utils.scrub_media check ordner/
python -m utils.scrub_media scrub foto.jpg out.jpg --address "Musterstraße 12, 12345 Musterstadt" --name "Erika Mustermann"
```
