# dicom_utils — DICOM-Dateien lesen, anonymisieren und konvertieren

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/modules/dicom_utils.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Bietet Funktionen zum Lesen, Anonymisieren und Konvertieren von DICOM-Dateien. Wiederverwendbar für alle DICOM-Quellen (Fundus, EKG-Waveforms, etc.).

## Relevanz

Bietet DICOM-Funktionen, essentiell für die medizinische Bildverarbeitung

## Methode

PII-Stripping entfernt alle personenspezifischen und Institutionsdaten sowie sensitive Informationen aus DICOM-Metadaten. Basiert auf DICOM PS3.15 Annex E (Basic Application Level Confidentiality).

## Datenfluss

- **Liest:** `DICOM-Dateien`, `(z.B.`, `medicine/imaging/*.dcm)`
- **Schreibt:** `Anonymisierte DICOM-Dateien, konvertierte Bilder`

## Grenzen

Anonymisierung entfernt keine eingebetteten Pixel-Daten. Nur JPEG-Ausgabe unterstuetzt.

## Referenzen

- DICOM PS3.15 Annex E (Basic Application Level Confidentiality)

## Aufruf

```bash
python dicom_utils.py
python dicom_utils.py --help
python dicom_utils.py --from 2024-01-01 --to 2024-12-31
```
