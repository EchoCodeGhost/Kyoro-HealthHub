# DFA Alpha1 & Autonome Komplexität

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/analysis/cardiovascular/analyse_dfa_alpha1.py`

**Evidenzstufe:** kalibriert (Literaturbasis + Parameter auf persönliche Baselines angepasst, keine externe Validierung)

## Zweck

Analysiert erweiterte HRV-Metriken aus dem PPI-Datenstrom: DFA Alpha1/Alpha2, Sample Entropy, LF/HF-Ratio und SD1/SD2 als Langzeit-Marker autonomer Regulation und Systemkomplexität.

## Relevanz

Ermöglicht die kardiovaskuläre Analyse, essentiell für die Herz-Kreislauf-Diagnostik

## Methode

Liest aus compute_ppi_dfa-generierten ppi_dfa (alpha1/alpha2) und ppi_hrv_advanced (SampEn, LF/HF, SD1/SD2). Schwellen (α1 < 0,75; 0,85; 1,0; 0,50) aus publizierten Studien (Mäkikallio, Gronwald, Sempere-Ruiz).

## Datenfluss

- **Liest:** `ppi_dfa`, `ppi_hrv_advanced`
- **Schreibt:** `analyses/cardiovascular/*.{md,png} (kein DB-Write)`

## Grenzen

Ursprüngliche Schwellen aus klinischen Populationen (post-AMI, Leistungssport); Ruijgt et al. 2026 stützt die Übertragbarkeit speziell für Long-COVID/PEM-Kontext (n=121), ersetzt aber keine individuelle Kalibrierung. Polar H10 Beat-to-beat Daten können Ektopie-Artefakte enthalten. n=1.

## Referenzen

- Peng CK, Havlin S, Stanley HE, Goldberger AL (1995). Quantification of scaling exponents and crossover phenomena in nonstationary heartbeat time series. Chaos: An Interdisciplinary Journal of Nonlinear Science, 5(1):82-87. doi:10.1063/1.166141
- Ho KKL, Moody GB, Peng CK et al. (1997). Predicting Survival in Heart Failure Case and Control Subjects by Use of Fully Automated Methods for Deriving Nonlinear and Conventional Indices of Heart Rate Dynamics. Circulation, 96(3):842-848. doi:10.1161/01.CIR.96.3.842
- Mäkikallio TH, Høiber S, Køber L et al. (1999). Fractal analysis of heart rate dynamics as a predictor of mortality in patients with depressed left ventricular function after acute myocardial infarction. The American Journal of Cardiology, 83(6):836-839. doi:10.1016/s0002-9149(98)01076-5
- Gronwald T, Hoos O (2019). Correlation properties of heart rate variability during endurance exercise: A systematic review. Annals of Noninvasive Electrocardiology, 25(1). doi:10.1111/anec.12697
- Sempere-Ruiz N, Sarabia JM, Baladzhaeva S, Moya-Ramón M (2024). Reliability and validity of a non-linear index of heart rate variability to determine intensity thresholds. Frontiers in Physiology, 15. doi:10.3389/fphys.2024.1329360
- Ruijgt TM, Slaghekke A, Ellens A, Janssen KW, Wüst RCI (2026). Wearable Heart Rate Variability Monitoring, Autonomic Dysfunction and Post-exertional Malaise in Long COVID: An Observational Study. Sports Medicine, online ahead of print. doi:10.1007/s40279-026-02487-4 (peer-reviewed; n=121 Long-COVID + 21 Kontrollen; HRV bleibt nach Belastung nahe/über der ersten ventilatorischen Schwelle einen vollen Tag supprimiert — stützt DFA-α1-Schwelle 0.75 speziell für Long-COVID/PEM-Kontext, nicht nur post-AMI/Leistungssport)

## Aufruf

```bash
python analyse_dfa_alpha1.py
python analyse_dfa_alpha1.py --help
python analyse_dfa_alpha1.py --from 2024-01-01 --to 2024-12-31
```
