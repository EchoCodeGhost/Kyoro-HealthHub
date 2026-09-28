# Dash 2009 Selbst-Kalibrierung aus Geräte-Überlappungsfenstern

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/calibration/calibrate_dash2009_overlap.py`

**Evidenzstufe:** kalibriert (Literaturbasis + Parameter auf persönliche Baselines angepasst, keine externe Validierung)

## Zweck

Kalibriert die Dash-2009-Schwellenwerte (Shannon-Entropie, CV_RR) aus Zeitfenstern, in denen eine validierte Quelle (Polar H10/H7 Brustgurt, tateno_glass-Algorithmus) UND eine optische Handgelenks-Quelle (Vantage V3/Loop Gen 2/Ignite 2) gleichzeitig Daten geliefert haben — personenspezifische Alternative/Ergänzung zur öffentlichen Datensatz-Kalibrierung (calibrate_dash2009_public.py).

## Relevanz

Ermöglicht die Kalibrierung von Algorithmen und Schwellenwerten, essentiell für die Datenqualität

## Methode

Findet 5-Min-Fenster mit ppi_raw-Daten von beiden Gerätegruppen gleichzeitig (echtes paralleles Tragen). Geräte werden über modules/device_registry.sensor_type(device_id) klassifiziert (chest_strap vs. optical_wrist_gps) — NICHT über einen Vergleich der rohen device-Spalte gegen eine feste Menge semantischer Namen wie "polar_vantage" (ppi_raw.device enthält die pseudonymisierte device_id, z.B. "DEV-394bbcad", nie einen semantischen String; ein früherer Set-Vergleich griff deshalb NIE, unabhängig von tatsächlich vorhandenem Parallel-Tragen — 0 Fenster war ein Bug, nicht fehlende Daten, s. @limits). Nutzt den tateno_glass-Flag der validierten Quelle als Pseudo-Ground-Truth (KEINE ärztliche Diagnose!) und sucht per ROC/Youden-J die Dash-2009-Schwelle, die am besten mit dieser Referenz übereinstimmt.

## Datenfluss

- **Liest:** `ppi_raw`
- **Schreibt:** `data/calibration/dash2009_self_thresholds.json`

## Grenzen

Pseudo-Ground-Truth, keine echte Diagnose — tateno_glass selbst ist nur AFDB-kalibriert, nicht perfekt. n=1 (eine Person), Stichprobengröße hängt von tatsächlicher Parallel-Tragezeit ab und kann klein/null sein. Ohne echte AFib-Episoden in den Überlappungsfenstern kalibriert dieses Skript im Wesentlichen nur die Falsch-Positiv-Rate auf Normalrhythmus, nicht die Sensitivität für echtes Vorhofflimmern. Geräte-Klassifikation über sensor_type stammt aus der Registry-Konfiguration — ein Gerät ohne (korrekten) sensor_type-Eintrag fließt stillschweigend in kein Fenster ein (weder validated noch optical), statt einen Fehler zu werfen.

## Referenzen

- Tateno K, Glass L (2001). Automatic detection of atrial fibrillation using the coefficient of variation and density histograms of RR and ΔRR intervals. Medical and Biological Engineering and Computing, 39(6):664-671. doi:10.1007/BF02345439
- Dash S, Chon KH, Lu S, Raeder EA (2009). Automatic Real Time Detection of Atrial Fibrillation. Annals of Biomedical Engineering, 37(9):1701-1709. doi:10.1007/s10439-009-9740-z

## Aufruf

```bash
python3 scripts/calibration/calibrate_dash2009_overlap.py
python3 scripts/calibration/calibrate_dash2009_overlap.py --person max
```
