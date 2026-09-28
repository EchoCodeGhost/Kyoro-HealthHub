# import_fundus.py — Fundusfotos (DCM/JPEG) importieren, anonymisieren, VLM-Analyse

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/importers/import_fundus.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Importiert Fundusfotos und fuehrt VLM-Analyse durch

## Relevanz

Ermöglicht den Import von Gesundheitsdaten, essentiell für die umfassende Datenanalyse

## Methode

Pipeline: 1. DCM to JPEG konvertieren (PII vollständig entfernt, via dicom_utils) 2. JPEG in data/fundus/ speichern (Dateiname ohne personenspezifische Daten) 3. Metadaten in medicine_imaging.db speichern 4. Optional: VLM-Analyse via OpenRouter (--analyse)

## Datenfluss

- **Liest:** `DCM/JPEG-Dateien`
- **Schreibt:** `data/fundus/, medicine_imaging.db`

## Grenzen

VLM-Analyse kann ungenau sein. Abhaengig von Bildqualitaet. --person war bisher fest auf OWN_PERSON_ID verdrahtet (kein Override moeglich) — wichtig bei einem geteilten Geraet (z.B. Funduskamera in einer Augenarztpraxis), wo die Geraete-/Dateiherkunft allein nichts ueber die abgebildete Person aussagt. Jetzt per --person setzbar.

## Aufruf

```bash
python3 scripts/importers/import_fundus.py <datei_oder_verzeichnis> [--analyse] [--lang de|en]
python3 scripts/importers/import_fundus.py /path/to/fundus/ --analyse
python3 scripts/importers/import_fundus.py rechts.dcm links.dcm --analyse
python3 scripts/importers/import_fundus.py scan.dcm --person PER-xxxxxxxx
```
