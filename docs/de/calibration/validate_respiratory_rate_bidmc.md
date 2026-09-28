# Atemfrequenz-Schätzer-Validierung gegen BIDMC-Ground-Truth

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/calibration/validate_respiratory_rate_bidmc.py`

**Evidenzstufe:** kalibriert (Literaturbasis + Parameter auf persönliche Baselines angepasst, keine externe Validierung)

## Zweck

Validiert die RSA-basierte Atemfrequenz-Schätzlogik aus mobile/KyoroPolarApp/.../RespiratoryRateEstimator.kt (Python-Nachbau hier) gegen echte Atemfrequenz-Ground-Truth aus dem BIDMC-Datensatz (BACK-26, lokaler Feature-Backlog).

## Relevanz

Ermöglicht die Validierung von Algorithmen, essentiell für die Qualitätssicherung

## Methode

Lädt bidmc_XX_Signals.csv (PLETH-Wellenform, 125 Hz) und bidmc_XX_Numerics.csv (RESP-Ground-Truth in Atemzügen/Min., 1 Hz) im CSV-Format (nicht das binäre WFDB-.breath-Annotationsformat — deutlich einfacher zu parsen, README empfiehlt CSV explizit für direkten Gebrauch). Peak-Detection auf PLETH liefert Puls-zu-Puls- Intervalle (Ersatz für einen echten PPI-Stream). Dieselbe Detrend+ Glättung+Peak-Zählung-Logik wie in RespiratoryRateEstimator.kt wird hier in Python nachgebaut und über 30-Sek.-Fenster gegen die echte RESP-Spalte verglichen (MAE).

## Datenfluss

- **Liest:** `PhysioNet`, `bidmc_csv/`, `files`, `(online`, `cached`, `in`, `data/calibration/bidmc_csv/`, `after`, `first`, `run)`
- **Schreibt:** `data/calibration/bidmc_csv/ (raw CSVs), stdout summary`

## Grenzen

Puls-zu-Puls-Intervalle kommen hier aus PPG-Peak-Detection auf einer sauberen ICU-Monitor-Aufnahme (125 Hz, wenig Rauschen) — auf einem realen Handgelenk-PPG (Polar Loop Gen 2/Polar 360, ~22-100 Hz, Bewegungsartefakte) dürfte die Genauigkeit schlechter ausfallen als hier gemessen. Diese Validierung zeigt also eine Obergrenze, keine Garantie für die Kotlin-Implementierung im Alltag.

## Referenzen

- Pimentel MAF, Johnson AEW, Charlton PH et al. (2017). Toward a Robust Estimation of Respiratory Rate From Pulse Oximeters. IEEE Transactions on Biomedical Engineering, 64(8):1914-1923. doi:10.1109/TBME.2016.2613124

## Aufruf

```bash
python3 scripts/calibration/validate_respiratory_rate_bidmc.py
python3 scripts/calibration/validate_respiratory_rate_bidmc.py --records bidmc01,bidmc02
python3 scripts/calibration/validate_respiratory_rate_bidmc.py --limit 10
```
