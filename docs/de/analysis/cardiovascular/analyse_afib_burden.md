# AFib-Burden-Analyse — Häufigkeit, Dauer und Trends von Arrhythmie-Episoden

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/analysis/cardiovascular/analyse_afib_burden.py`

**Evidenzstufe:** kalibriert (Literaturbasis + Parameter auf persönliche Baselines angepasst, keine externe Validierung)

## Zweck

Analysiert Häufigkeit, Dauer und zeitliche Verteilung von Arrhythmie-Episoden aus Polar-PPI-Daten und Apple Watch EKG sowie Zusammenhänge mit Luftdruck, Blutdruck, HRV, Schlaf und Stress.

## Relevanz

Ermöglicht die kardiovaskuläre Analyse, essentiell für die Herz-Kreislauf-Diagnostik

## Methode

Liest direkt aus compute-generierten arrhythmie_episoden und ecg_sessions; verwendet CV-Klassifikation (CV ≥ 10 % = AFib-verdächtig, < 10 % = Ektopie) aus arrhythmia_utils. Keine eigene Episodendetektion im Script.

## Datenfluss

- **Liest:** `arrhythmie_episoden`, `ecg_sessions`, `biometeo`, `weather_station`, `blood_pressure`, `measurements`, `sessions`, `session_metrics`, `symptoms`
- **Schreibt:** `analyses/cardiovascular/*.{md,png} (kein DB-Write)`

## Grenzen

Polar-CV-Erkennung ist kein klinisches EKG. Die CV-Schwellen sind empirisch, nicht formal validiert. n=1, keine Kontrollgruppe, Consumer-Sensorik.

## Referenzen

- Perez MV, Mahaffey KW, Hedlin H et al. (2019). Large-Scale Assessment of a Smartwatch to Identify Atrial Fibrillation. New England Journal of Medicine, 381(20):1909-1917. doi:10.1056/NEJMoa1901183
- Tateno K, Glass L (2001). Automatic detection of atrial fibrillation using the coefficient of variation and density histograms of RR and ΔRR intervals. Medical and Biological Engineering and Computing, 39(6):664-671. doi:10.1007/BF02345439

## Aufruf

```bash
python analyse_afib_burden.py
python analyse_afib_burden.py --help
python analyse_afib_burden.py --from 2024-01-01 --to 2024-12-31
```
