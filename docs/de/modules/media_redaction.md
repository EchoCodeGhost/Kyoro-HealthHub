# media_redaction.py — Metadaten, sichtbare Adressen und Namen aus Bildern und PDFs entfernen

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/modules/media_redaction.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Meldet (Report/Export) und entfernt Metadaten in Bildern (EXIF inkl. GPS) und PDFs (Info, XMP, eingebettete JPEGs, Anhänge, JavaScript, Formulare) und schwärzt Postadressen, Personennamen, Telefon- und Versichertennummern sowie GPS-Koordinaten und persönliche Ortsnamen im sichtbaren Inhalt. Alles läuft lokal.

## Relevanz

Verhindert, dass Wohnadressen, Namen und Metadaten aus Befunden und Fotos in die Ablage, in Exporte oder an externe Dienste gelangen

## Methode

Report: Pillow liest EXIF-Tags, pikepdf liest Info/XMP/Anhänge/Aktionen/Annotationen. Werte werden nur auf Wunsch ausgegeben, sonst nur Tag-Namen und Zähler. Schwärzen: Wörter mit Positionen kommen aus der PDF-Textebene (pdftotext -bbox-layout) oder per OCR (Tesseract, Sprache deu). Adress-, Namens-, Nummern- und Ortsbereiche (modules.address_redaction, name_redaction, identifier_redaction, location_redaction) werden auf die Wortboxen abgebildet und auf einem gerenderten Seitenbild mit schwarzen Rechtecken überdeckt. Betroffene PDF-Seiten werden durch die Bildseite ersetzt, sodass keine Textebene mit Adresse, Name, Nummer oder Ort zurückbleibt. Danach folgt eine Prüfung der Ausgabe (Textebene und OCR). Findings enthalten nur Zähler, nie den entfernten Text.

## Datenfluss

- **Liest:** `Bilddateien`, `(JPEG`, `PNG`, `HEIC`, `mit`, `pillow-heif)`, `PDF-Dateien`, `~/.config/kyoro/health_config.json`, `(privacy_check.patient_addresses`, `privacy_check.patient_names`, `optional)`, `identity.db`, `(person_name_map`, `optional)`
- **Schreibt:** `Bereinigte Bild- und PDF-Dateien (Zieldatei muss angegeben werden)`

## Grenzen

Optionale Werkzeuge: pytesseract + tesseract (OCR), pdf2image + poppler (Rendern, Wortboxen). Fehlen sie, wird nur die Metadaten-Bereinigung ausgeführt und eine Warnung gemeldet. Die Erkennung ist heuristisch (siehe address_redaction); schlechte OCR kann Adressen und Namen übersehen. Betroffene PDF-Seiten werden zu Bildern (nicht mehr durchsuchbar, größere Datei). Schwärzungen sind echte Pixelüberdeckung, kein Annotationslayer. Namen werden nur mit Anrede, Titel oder Feldbezeichner oder aus der Liste bekannter Namen erkannt (siehe name_redaction); Nummern nur in üblichen Schreibweisen (siehe identifier_redaction).

## Aufruf

```bash
from modules.media_redaction import report_image, report_pdf, scrub_image, scrub_pdf_full
report_pdf(Path("befund.pdf"))
scrub_pdf_full(Path("befund.pdf"), Path("sauber.pdf"))
scrub_image(Path("foto.jpg"), Path("sauber.jpg"))
```
