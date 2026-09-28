# AFib Level-1 Schwellenwert-Kalibrierung

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/calibration/calibrate_afib_thresholds.py`

**Evidenzstufe:** kalibriert (Literaturbasis + Parameter auf persönliche Baselines angepasst, keine externe Validierung)

## Zweck

Kalibriert Schwellenwerte für AFib-Erkennung mit MIT-BIH AFDB-Datenbank

## Relevanz

Ermöglicht die Kalibrierung von Algorithmen und Schwellenwerten, essentiell für die Datenqualität

## Methode

Kalibriert AFib Level-1 Schwellenwerte unter Verwendung der MIT-BIH Atrial Fibrillation Database. 25 Aufnahmen à ~10h, 250 Hz, mit Rhythmus-Annotationen. Berechnet optimale Schwellenwerte für 5 HRV-Metriken.

## Datenfluss

- **Liest:** `MIT-BIH`, `AFDB-Datenbank`, `aus`, `data/calibration/afdb/`
- **Schreibt:** `data/calibration/afdb_thresholds.json, data/calibration/afdb_calibration.csv, data/calibration/afdb_roc.png`

## Grenzen

Kalibrierung basiert auf AFDB-Daten. Validität für andere Datensätze nicht garantiert.

## Referenzen

- Moody GB, Mark RG (2001). The impact of the MIT-BIH Arrhythmia Database. IEEE Engineering in Medicine and Biology Magazine, 20(3):45-50. doi:10.1109/51.932724
- Goldberger AL, Amaral LAN, Glass L et al. (2000). PhysioBank, PhysioToolkit, and PhysioNet. Circulation, 101(23). doi:10.1161/01.CIR.101.23.e215

## Aufruf

```bash
cd ~/Kyoro-HealthHub/scripts
python3 calibration/calibrate_afib_thresholds.py
```
