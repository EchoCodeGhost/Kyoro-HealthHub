# Kubios HRV Screenshot-Import

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/importers/import_kubios_screenshot.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Importiert Kubios HRV Mobile Screenshots per OCR

## Relevanz

Ermöglicht den Import von Gesundheitsdaten, essentiell für die umfassende Datenanalyse

## Methode

Liest Kubios HRV Mobile Screenshots (PNG) per OCR und importiert die Werte in kubios_hrv_resting. Unterstuetzt: - Kubios HRV Mobile "RESTING HRV" Resultscreen - macOS-Screenshots - Beliebige PNG-Screenshots (Datum aus File-Metadaten) Alle Werte werden extrahiert, inkl. PNS/SNS-Index.

## Datenfluss

- **Liest:** `PNG-Screenshots`
- **Schreibt:** `kubios_hrv_resting`

## Grenzen

OCR kann ungenau sein. Abhaengig von Screenshot-Qualitaet.

## Aufruf

```bash
python import_kubios_screenshot.py               # scannt imports/kubios/ (Default)
python import_kubios_screenshot.py --file screenshot.png
python import_kubios_screenshot.py --dir ~/Downloads/kubios/
python import_kubios_screenshot.py --file screenshot.png --dry-run
```
