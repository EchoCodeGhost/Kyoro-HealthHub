# Long-term wrist-PPG AFib dataset download (Zenodo record 5815074)

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/calibration/download_ppg_afib_zenodo.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Lädt den offen zugänglichen Zenodo-Datensatz "Long-term electrocardiogram and wrist-based photoplethysmogram recordings with annotated atrial fibrillation episodes" (8 Patienten, 5-8 Tage, ~1306 Stunden ECG+PPG+ACC, beat-to-beat AFib-Annotation) für die Dash-2009-Kalibrierung herunter.

## Relevanz

Ermöglicht den Download von Referenzdaten, essentiell für die Kalibrierung und Validierung

## Methode

Einzelner Download von Data.zip (~7 GB) von Zenodo, Entpacken nach data/calibration/zenodo_afib_ppg/. Kein Login/Credentialing nötig (im Gegensatz zu vielen PhysioNet-Datensätzen).

## Datenfluss

- **Liest:** `https://zenodo.org/records/5815074`, `(online)`
- **Schreibt:** `data/calibration/zenodo_afib_ppg/ (MAT-Dateien + subject_info.xlsx + LICENSE.txt)`

## Grenzen

LIZENZ: "Other (Non-Commercial)" — Datensatz nur für nicht-kommerzielle Forschung/Kalibrierung nutzbar, siehe heruntergeladene LICENSE.txt. Rohdaten bleiben deshalb in .gitignore (data/calibration/zenodo_afib_ppg/), nur die daraus destillierten Schwellenwerte (dash2009_thresholds.json) werden committet. ~7 GB Download, benötigt Internetverbindung.

## Referenzen

- Bacevičius J, Abramikas Ž, Badaras I et al. (2022). Long-term electrocardiogram and wrist-based photoplethysmogram recordings with annotated atrial fibrillation episodes [Data set]. Zenodo. doi:10.5281/zenodo.5815074

## Aufruf

```bash
python3 scripts/calibration/download_ppg_afib_zenodo.py
python3 calibration/download_ppg_afib_zenodo.py  # from inside scripts/
```
