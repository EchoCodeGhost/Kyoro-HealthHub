# scrub_pdf_metadata.py — Entfernt PII-Metadaten aus PDF-Dateien

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/utils/scrub_pdf_metadata.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Entfernt Dokument- und Bild-Metadaten aus PDFs vor Ablage in originals/.

## Relevanz

Bietet Funktionen zur Datenbereinigung und Anonymisierung, essentiell für den Datenschutz

## Methode

Entfernt das /Info-Dictionary (Author, Creator, Producer, Title, Subject, Keywords, CreationDate, ModDate) und den XMP-Metadatenstream. Eingebettete JPEG-Bilder (DCTDecode) werden extrahiert, durch imaging_utils.strip_exif_pii geschickt (GPS, Geräte-Serial, Owner-Name, MakerNote werden entfernt) und ohne EXIF zurückgeschrieben.

## Datenfluss

- **Liest:** `PDF-Dateien`
- **Schreibt:** `PII-freie PDF-Dateien`

## Grenzen

Nur JPEG-kodierte eingebettete Bilder (DCTDecode) werden auf EXIF geprüft; andere Encodings (z.B. FlateDecode-Rohpixel aus normalen OCR-Scans) tragen üblicherweise kein EXIF und werden nicht angerührt. Formularfelder/Annotationen mit eigenen Metadaten werden nicht geprüft. pikepdf trägt beim Speichern seine eigene Producer-Signatur ein (Software-Info, keine PII).

## Aufruf

```bash
python scrub_pdf_metadata.py eingang.pdf ausgang.pdf
python scripts/utils/scrub_pdf_metadata.py imports/_inbox/befund.pdf data/staging/befund_scrubbed.pdf
```
