# KubiosHRV Orthostatic-Import

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/importers/import_kubios_orthostatic.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Importiert KubiosHRV Orthostatic-Exportdateien

## Relevanz

Ermöglicht den Import von Gesundheitsdaten, essentiell für die umfassende Datenanalyse

## Methode

Liest KubiosHRV-Exportdateien und importiert in v2: sessions (type='orthostatic') + session_metrics. Unterstuetzte Formate: 1. KubiosHRV Standard TXT-Bericht (Desktop-Software, Windows/Mac) 2. Manuelles CSV (Vorlage: --template) Datenquellen: kubios_polar_h10 - Kubios + Polar H10 Brustgurt (genaueste HRV-Werte) kubios_ble_hrm - Kubios + beliebiger BLE/ANT+-Brustgurt kubios_camera - Kubios Mobile App with Kamera-PPG (niedrigere Genauigkeit) Hinweis: hr_delta = hr_stand - hr_supine kann POTS unterschaetzen.

## Datenfluss

- **Liest:** `KubiosHRV`, `TXT/CSV-Dateien`
- **Schreibt:** `sessions, session_metrics`

## Grenzen

Segmentanalyse kann Peak-HR unterschaetzen.

## Aufruf

```bash
python import_kubios_orthostatic.py               # scannt imports/kubios/ (Default)
python import_kubios_orthostatic.py --file export.txt
python import_kubios_orthostatic.py --dir ~/Downloads/kubios/
python import_kubios_orthostatic.py --csv messung.csv
python import_kubios_orthostatic.py --template
python import_kubios_orthostatic.py --manual
```
