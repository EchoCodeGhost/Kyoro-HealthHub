# plot_hilo_bp.py — Hilo/Aktiia Blutdruckdaten Visualisierung

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/analysis/cardiovascular/plot_hilo_bp.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Erstellt Visualisierungen fuer Hilo/Aktiia Handgelenks-Blutdruckmessungen aus der blood_pressure Tabelle

## Relevanz

Ermöglicht die kardiovaskuläre Analyse, essentiell für die Herz-Kreislauf-Diagnostik

## Methode

Liest Blutdruckdaten (systolisch, diastolisch, Puls) aus der blood_pressure Tabelle mit source='hilo_pdf' oder source='hilo_screenshots'. Erstellt folgende Plots: - Zeitreihe: Systolisch, Diastolisch, Puls über die Zeit - Histogramme: Verteilung der Messwerte - Tageszeit-Profil: Durchschnittswerte nach Uhrzeit - Monatsuebersicht: Monatliche Durchschnittswerte Unterstuetzt Filterung nach Datum (--from, --to) und Person.

## Datenfluss

- **Liest:** `blood_pressure`, `Tabelle`, `(systolic`, `diastolic`, `pulse`, `ts`, `source)`
- **Schreibt:** `analyses/cardiovascular/hilo_bp_*.png Plot-Dateien`

## Grenzen

Abhaengig von verfuegbaren Hilo-Daten in blood_pressure Tabelle. Keine medizinische Interpretation, nur Visualisierung.

## Aufruf

```bash
python plot_hilo_bp.py
python plot_hilo_bp.py --from 2026-01-01
python plot_hilo_bp.py --to 2026-07-01
python plot_hilo_bp.py --from 2026-01-01 --to 2026-07-01
python plot_hilo_bp.py --format png
python plot_hilo_bp.py --format pdf
```
