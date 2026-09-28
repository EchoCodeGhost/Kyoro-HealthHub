# PTT / HRV / Blood pressure — Correlationsanalyse

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/analysis/cardiovascular/analyse_ptt_hrv.py`

**Evidenzstufe:** Heuristik (deliberate Designentscheidung aus Domänenwissen, keine formale Literatur- oder Validierungsbasis)

## Zweck

Korreliert Pulse-Transit-Time-Messungen (Polar Vantage V3 Spot-HRV) mit nächtlicher HRV und Blutdrucktrends aus dem Omron-Gerät.

## Relevanz

Ermöglicht die kardiovaskuläre Analyse, essentiell für die Herz-Kreislauf-Diagnostik

## Methode

Pearson-/Spearman-Korrelation zwischen PTT (contract/relax), HRV-Spot, nächtlicher RMSSD und Blutdruck. Keine klinische Validierung der PTT-zu-Blutdruck-Kalibrierung.

## Berechnung

```
Correlation strength: |r| <0.2 weak | 0.2-0.4 moderate | 0.4-0.7 strong | >0.7 very strong
PTT measurement type: contract | relax (Polar Vantage V3)
```

## Datenfluss

- **Liest:** `polar_hrv_spot`, `measurements`, `(hrv_rmssd/rmssd_ms`, `geräteunabhängig`, `über`, `modules/metric_loader)`, `omron_blood_pressure`
- **Schreibt:** `analyses/cardiovascular/analyse_ptt_hrv.{png,md}`

## Grenzen

Heuristische Methode: PTT als Blutdruck-Proxy nicht klinisch validiert; optische Sensor-PTT hat niedrigere Genauigkeit als cuffbasierte Methoden. Geräteabhängiger Messfehler unberücksichtigt.

## Referenzen

- Mukkamala R, Hahn JO, Inan OT, Mestha LK, Kim CS, Toreyin H, Kyal S (2015). Toward Ubiquitous Blood Pressure Monitoring via Pulse Transit Time: Theory and Practice. IEEE Transactions on Biomedical Engineering, 62(8):1879-1901. doi:10.1109/TBME.2015.2441951
- Payne RA, Symeonides CN, Webb DJ, Maxwell SRJ (2006). Pulse transit time measured from the ECG: an unreliable marker of beat-to-beat blood pressure. Journal of Applied Physiology, 100(1):136-141. doi:10.1152/japplphysiol.00657.2005

## Aufruf

```bash
python analyse_ptt_hrv.py
python analyse_ptt_hrv.py --help
python analyse_ptt_hrv.py --from 2024-01-01 --to 2024-12-31
```
