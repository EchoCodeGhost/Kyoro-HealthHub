# HRV × Erschöpfung — Lag-Correlationsanalyse

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/analysis/cardiovascular/analyse_hrv_fatigue.py`

**Evidenzstufe:** Heuristik (deliberate Designentscheidung aus Domänenwissen, keine formale Literatur- oder Validierungsbasis)

## Zweck

Untersucht den zeitverzögerten Zusammenhang zwischen nächtlicher HRV (RMSSD) und subjektiver Erschöpfung mittels Lag-Korrelation (±7 Tage).

## Relevanz

Ermöglicht die kardiovaskuläre Analyse, essentiell für die Herz-Kreislauf-Diagnostik

## Methode

Pearson-Korrelation (Pure-Python) für HRV(t) × Erschöpfung(t+lag) über alle überlappenden Tage; Lag-Scan von −7 bis +7.

## Berechnung

```
Fatigue scale: 0-10 (subjective, from symptom diary)
Correlation strength: |r| <0.2 weak | 0.2-0.4 moderate | 0.4-0.7 strong | >0.7 very strong
Lag direction: negative (HRV leads fatigue) | positive (fatigue leads HRV)
```

## Datenfluss

- **Liest:** `measurements`, `symptoms`
- **Schreibt:** `analyses/cardiovascular/hrv_fatigue_*.{md,png}`

## Grenzen

Heuristische Methode: Explorative Analyse ohne Signifikanzschwelle; Symptomtagebuch-Datenmenge aktuell sehr gering (kein konsistentes Logging); Kausalrichtung nicht bestimmbar; keine Adjustierung für Confounding.

## Referenzen

- Shaffer F, Ginsberg JP (2017). An overview of heart rate variability metrics and norms. Frontiers in Public Health, 5:258. doi:10.3389/fpubh.2017.00258
- Davenport TE, Stevens SR, VanNess MJ, Snell CR, Little T (2010). Conceptual model for physical therapist management of chronic fatigue syndrome/myalgic encephalomyelitis. Physical Therapy, 90(4):602-614. doi:10.2522/ptj.20090047

## Aufruf

```bash
python analyse_hrv_fatigue.py
python analyse_hrv_fatigue.py --help
python analyse_hrv_fatigue.py --from 2024-01-01 --to 2024-12-31
```
