# imaging_utils.py — Bildformat-Normalisierung mit PII-Stripping

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/modules/imaging_utils.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Normalisiert Smartphone-Bildformate und entfernt PII aus EXIF-Metadaten.

## Relevanz

Bietet Bildverarbeitungsfunktionen, essentiell für die medizinische Bildanalyse

## Methode

Eingabe: HEIC/HEIF, JPEG, PNG, MOV/MP4. Ausgabe: JPEG ohne EXIF-PII. Entfernt GPS, Geräte-Serial, Owner-Name, MakerNote. Geräte-Serial wird vor dem Entfernen pseudonymisiert (→ identity.db). DateTimeOriginal wird extrahiert und als Rückgabewert übergeben.

## Datenfluss

- **Liest:** `Bilddateien`, `(HEIC/HEIF`, `JPEG`, `PNG`, `MOV/MP4)`
- **Schreibt:** `Normalisierte JPEG-Dateien`

## Grenzen

Benötigt Pillow (Pflicht), pillow-heif (empfohlen für HEIC), ImageMagick (Fallback für HEIC), opencv-python (für MOV/MP4).

## Aufruf

```bash
python imaging_utils.py
python imaging_utils.py --help
python imaging_utils.py --from 2024-01-01 --to 2024-12-31
```
