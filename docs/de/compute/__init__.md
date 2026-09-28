# Compute Module — Berechnungs-Skripte für Kyoro-HealthHub

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/compute/__init__.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Enthält alle Berechnungs- und Analyse-Skripte für Gesundheitsmetriken

## Methode

Berechnung von HRV-Metriken, Herzfrequenzanalysen, Schlafparametern, Stresslevel, Stoffwechselwerten und anderen Gesundheitsindikatoren

## Datenfluss

- **Liest:** `ppi_raw`, `ecg`, `measurements`, `sessions`
- **Schreibt:** `ppi_hrv_advanced, hrv_daily, sleep_analysis, clinical_analysis`

## Grenzen

Berechnungen basieren auf verfügbaren Sensordaten

## Aufruf

```bash
python __init__.py
python __init__.py --help
python __init__.py --from 2024-01-01 --to 2024-12-31
```
