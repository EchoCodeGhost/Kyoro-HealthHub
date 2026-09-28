# Multi-Source HRV-Vergleich — Polar vs. Oura vs. Apple Watch vs. Kubios

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/analysis/cardiovascular/analyse_hrv_multisource.py`

**Evidenzstufe:** Heuristik (deliberate Designentscheidung aus Domänenwissen, keine formale Literatur- oder Validierungsbasis)

## Zweck

Vergleicht HRV-RMSSD-Werte aus Polar, Oura, Apple Watch und Kubios auf überlappenden Tagen und prüft Konsistenz, systematische Abweichungen und Trends.

## Relevanz

Ermöglicht die kardiovaskuläre Analyse, essentiell für die Herz-Kreislauf-Diagnostik

## Methode

Pearson-Korrelation und mittlere absolute Abweichung zwischen Quellen-Paaren; deskriptive Statistik (n, mean, std, min, max) je Quelle; kein gemeinsamer Kalibrierungsstandard.

## Berechnung

```
Correlation strength: |r| <0.7 poor | 0.7-0.85 moderate | 0.85-0.95 good | >0.95 excellent
Mean absolute difference: lower = better consistency
```

## Datenfluss

- **Liest:** `polar_nightly_hrv`, `oura_sleep_model`, `measurements`, `kubios_hrv_resting`
- **Schreibt:** `analyses/cardiovascular/hrv_multisource_*.{md,png}`

## Grenzen

Heuristische Methode: Consumer-Geräte messen HRV in unterschiedlichen Kontexten (Schlaf vs. Spot-Messung) und mit unterschiedlichen Algorithmen; kein Goldstandard-Vergleich; DFA/LF-HF-Metriken nur aus Kubios-Import verfügbar. Herstellerübergreifend zeigt die Validierungsliteratur, dass PPG-basierte HRV (Watch, Ring) gegen EKG systematisch abweicht, besonders unter Bewegung (Hernando et al. 2018; Kinnunen et al. 2020; Gilgen-Ammann et al. 2019) — Quellen sind daher vergleichbar, aber nicht ohne Weiteres austauschbar. KRITISCH: LF/HF-Ratio ist kein valides Stressmaß auf Einzelpersonenebene — die LF-Power spiegelt nicht ausschließlich sympathische Aktivität wider (Billman 2013, doi:10.3389/fphys.2013.00026); LF/HF-Werte nur explorativ interpretieren.

## Referenzen

- Task Force of the ESC/NASPE (1996). Heart rate variability: standards of measurement, physiological interpretation, and clinical use. European Heart Journal, 17(3), 354-381. doi:10.1093/oxfordjournals.eurheartj.a014868
- Billman GE (2013). The LF/HF ratio does not accurately measure cardiac sympatho-vagal balance. Frontiers in Physiology, 4:26. doi:10.3389/fphys.2013.00026 (LF/HF-Ratio: methodische Einschränkungen für Einzelpersonen)
- Hernando D, Roca S, Sancho J, Alesanco Á, Bailón R (2018). Validation of the Apple Watch for heart rate variability measurements during relax and mental stress in healthy subjects. Sensors, 18(8), 2619. doi:10.3390/s18082619 (PPG-Watch vs. EKG)
- Kinnunen H, Rantanen A, Kenttä T, Koskimäki H (2020). Feasible assessment of recovery and cardiovascular health: accuracy of nocturnal HR and HRV assessed via ring PPG in comparison to medical grade ECG. Physiological Measurement, 41(4), 04NT01. doi:10.1088/1361-6579/ab840a (PPG-Ring vs. EKG, Nachtmessung)
- Gilgen-Ammann R, Schweizer T, Wyss T (2019). RR interval signal quality of a heart rate monitor and an ECG Holter at rest and during exercise. European Journal of Applied Physiology, 119(7), 1525-1532. doi:10.1007/s00421-019-04142-5 (Brustgurt-RR-Signalqualität in Ruhe und unter Belastung)

## Aufruf

```bash
python analyse_hrv_multisource.py
python analyse_hrv_multisource.py --help
python analyse_hrv_multisource.py --from 2024-01-01 --to 2024-12-31
```
