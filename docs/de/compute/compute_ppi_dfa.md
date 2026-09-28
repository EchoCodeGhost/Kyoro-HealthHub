# Detrended Fluctuation Analysis (DFA) on ppi_raw (Polar H10 / ECG Logger).

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/compute/compute_ppi_dfa.py`

**Evidenzstufe:** Forschung (peer-reviewte Literaturbasis, aber keine formale klinische Validierungsstudie mit Endpunkten)

## Zweck

Berechnet DFA alpha1/alpha2 je 5-Minuten-Fenster als Marker für Vorhofflimmern und autonome Regulation aus Beat-to-beat-Intervallen.

## Relevanz

Ermöglicht die Analyse von Puls-Puls-Intervall-Daten, essentiell für die HRV-Analyse

## Methode

alpha1 über Skalen 4-16 (Kubios-Standard), alpha2 über 16-64. alpha2 bleibt NULL bei < 256 Schlägen im Fenster.

## Schwellenwerte

| Wert | Bedeutung |
|---|---|
| `Ruhe (is_training=0):` |  |
| `alpha1 < 0.75` | [research] AFib-Indikator / Verlust fraktalen Gedächtnisses — mechanistisch begründet (Ho 1997); kein prospektiver Diagnostiktest mit Sensitivität/Spezifität; im AFES-Kontext mit weiteren Signalen kombinieren |
| `alpha1 < 0.85` | [research] Mortalitätsprädiktor; validiert für post-AMI mit EF<35% (Mäkikallio 1999); für andere Nutzerprofile als Orientierungswert verwenden, klinische Einordnung nutzerabhängig |
| `alpha1 ~ 1.0` | normaler Sinusrhythmus (1/f-Rauschen) |
| `alpha1 > 1.2` | pathologische Starrheit (z. B. schwere Herzinsuffizienz) |
| `Training (is_training=1):` |  |
| `alpha1 < 0.75` | [validated] HRVT1 – aerobe Schwelle überschritten; validiert gegen Laktat-Referenz in Gesunden, Sportlern und kardialen Populationen (Rogers & Gronwald 2022); bei autonomer Dysregulation oder Erkrankungen mit veränderter HRV-Dynamik als Näherung verwenden |
| `alpha1 < 0.50` | [validated] HRVT2 – anaerobe Schwelle überschritten; validiert gegen VT2/MLSS in Sportstudien (Sempere-Ruiz 2024); Übertragbarkeit auf klinische Populationen nutzerabhängig prüfen |

## Datenfluss

- **Liest:** `ppi_raw`
- **Schreibt:**

  ```
  ppi_dfa: window_start TEXT, person TEXT, device TEXT, n_beats INT,
  alpha1 REAL, alpha2 REAL, is_training INT, mean_hr_bpm REAL, computed_at TEXT
  measurements: dfa_alpha1_rest_{avg,min,pct_low,pct_risk},
  dfa_alpha1_train_{avg,min,pct_at,pct_hrvt2}, dfa_hrvt1, dfa_hrvt2
  ```

## Grenzen

DFA mit Skalen 4-16 zeigt bei unkorrelierten Zeitreihen systematisch alpha1 ≈ 0.58 statt theoretisch 0.50 (bekannter Finite-Scale-Bias; gilt auch für Kubios). Da die publizierten Schwellenwerte mit denselben Skalen ermittelt wurden, ist der Bias in den Thresholds absorbiert — Absolutwerte nur intra-individuell vergleichen. Nur echte Beat-to-beat-Daten (ppi_raw); optische HR-Sensoren ungeeignet. Bekanntes leeres Ergebnis: Ein 5-Min-Fenster braucht _MIN_BEATS (100) kontiguierliche Schläge (Lücke <= _GAP_S). In dieser DB stammt ppi_raw überwiegend aus kurzen, EKG-Session-gekoppelten Erfassungen (Sekunden bis wenige zehn Sekunden je Aufnahme), nicht aus kontinuierlichem Brustgurt-Streaming — die längste zusammenhängende Schlagfolge bleibt unter _MIN_BEATS. Für solche Zeiträume bleibt ppi_dfa korrekterweise leer; das ist kein Bug im Skript, sondern fehlende Eingangsdatengrundlage (siehe pipeline-architecture: "Silent empty results as known behavior" — dieses Skript meldet die Fensteranzahl explizit im Log, statt stillschweigend durchzulaufen). Abhilfe nur durch tatsächliches kontinuierliches Brustgurt-/EKG-Logger-Tragen, nicht durch künstliches Befüllen der Tabelle. Trainings-Fenster werden markiert (is_training=1) und von AFES ignoriert. HRVT1/HRVT2 (alpha1=0.75/0.50) prospektiv validiert gegen Laktat/VT2 in Gesunden, Sportlern und kardialen Populationen (Rogers 2022, Sempere-Ruiz 2024). Bei autonomer Dysregulation ist alpha1 in Ruhe bereits erniedrigt, was HRVT in Ruhe-HR-Nähe zieht — kein valider AT-Wert in diesem Fall (Dysautonomie-Margin-Check in compute_pem.py). alpha1 < 0.85 (Mäkikallio 1999): prospektive Validierung für post-AMI mit EF<35%; für andere Nutzerprofile als Orientierungswert nutzbar, klinische Einordnung erfordert individuellen Kontext. alpha1 < 0.75 in Ruhe als AFib-Indikator: mechanistisch begründet, kein prospektiver Diagnostiktest mit publizierter Sensitivität/Spezifität — im AFES-Kontext mit weiteren Signalen kombinieren.

## Referenzen

- Peng CK, Havlin S, Stanley HE, Goldberger AL (1995). Quantification of scaling exponents and crossover phenomena in nonstationary heartbeat time series. Chaos: An Interdisciplinary Journal of Nonlinear Science, 5(1):82-87. doi:10.1063/1.166141
- Ho KKL, Moody GB, Peng CK et al. (1997). Predicting Survival in Heart Failure Case and Control Subjects by Use of Fully Automated Methods for Deriving Nonlinear and Conventional Indices of Heart Rate Dynamics. Circulation, 96(3):842-848. doi:10.1161/01.CIR.96.3.842
- Mäkikallio TH, Høiber S, Køber L et al. (1999). Fractal analysis of heart rate dynamics as a predictor of mortality in patients with depressed left ventricular function after acute myocardial infarction. The American Journal of Cardiology, 83(6):836-839. doi:10.1016/s0002-9149(98)01076-5
- Gronwald T, Hoos O (2019). Correlation properties of heart rate variability during endurance exercise: A systematic review. Annals of Noninvasive Electrocardiology, 25(1). doi:10.1111/anec.12697
- Rogers B, Gronwald T (2022). Fractal Correlation Properties of Heart Rate Variability as a Biomarker for Intensity Distribution and Training Prescription in Endurance Exercise: An Update. Frontiers in Physiology, 13. doi:10.3389/fphys.2022.879071
- Sempere-Ruiz N, Sarabia JM, Baladzhaeva S, Moya-Ramón M (2024). Reliability and validity of a non-linear index of heart rate variability to determine intensity thresholds. Frontiers in Physiology, 15. doi:10.3389/fphys.2024.1329360

## Aufruf

```bash
python compute_ppi_dfa.py                            # recompute all
python compute_ppi_dfa.py --update                   # from last entry
python compute_ppi_dfa.py --recompute                # overwrite existing
python compute_ppi_dfa.py --from 2026-05-01 --to 2026-06-03
```
