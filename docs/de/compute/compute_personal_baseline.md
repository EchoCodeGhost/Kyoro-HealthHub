# Berechnet personalisierte Baselines für Kernmetriken.

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/compute/compute_personal_baseline.py`

**Evidenzstufe:** Infrastruktur (keine klinische Aussage)

## Zweck

Personalisierte Baseline-Werte aus den besten/stabilsten Phasen — ersetzt ad-hoc-Berechnungen in Analysis-Scripts durch zentrale, methodisch konsistente Tabelle.

## Relevanz

Ermöglicht die Berechnung persönlicher Baseline-Werte, essentiell für die individuelle Gesundheitsanalyse

## Methode

Vier Methoden: IQR-Median aller Geräte (all_iqr), Top-N% aller Geräte (all_top), IQR-Median eines Geräts (device_iqr), Top-N% eines Geräts (device_top). Instabile Perioden (Infektionen ±7/+90 Tage) werden ausgeschlossen. Ergebnis wird in personal_baseline gespeichert (Median, SD, P25/P75, n).

## Datenfluss

- **Liest:** `measurements`, `(hrv_rmssd`, `met_min`, `spo2`, `sleep_deep_pct`, `sleep_rem_pct`, `respiratory_rate`, `skin_temperature)`
- **Schreibt:**

  ```
  personal_baseline: metric, method, device_id, median_val, sd_val,
  p25, p75, n_days, ts_computed, person
  ```

## Grenzen

Baseline-Qualität hängt von Datendichte und Geräte-Verfügbarkeit ab; Methoden- wahl (IQR vs. Top-N%) beeinflusst das Ergebnis; Minimum 30 Tage erforderlich. Kein automatisches Re-Compute bei neuen Daten — manuell ausführen.

## Aufruf

```bash
python compute_personal_baseline.py
python compute_personal_baseline.py --help
python compute_personal_baseline.py --from 2024-01-01 --to 2024-12-31
```
