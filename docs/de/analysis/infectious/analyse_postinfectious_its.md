# Interrupted Time Series (ITS) Analysis

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/analysis/infectious/analyse_postinfectious_its.py`

**Evidenzstufe:** Heuristik (deliberate Designentscheidung aus Domänenwissen, keine formale Literatur- oder Validierungsbasis)

## Zweck

Vergleicht HRV (RMSSD), Ruhepuls und Schlafqualität vor und nach einem konfigurierbaren Ereignis-Datum mittels segmentierter linearer Regression (Interrupted Time Series).

## Relevanz

Unterstützt die infektionsbezogene Datenanalyse und Entscheidungsfindung durch systematische Aufbereitung von Wearable- und Symptomdaten

## Methode

Segmentierte lineare Regression Y = β₀ + β₁·t + β₂·D + β₃·(t−t_c)·D; OLS in Pure-Python. Cohen's d für Effektgröße. Keine Konfounderkontrolle.

## Berechnung

```
Model: Y = β₀ + β₁·t + β₂·D + β₃·(t−t_c)·D where D=1 if t>=t_c (cutoff date)
Effect size: Cohen's d 0.2 small | 0.5 medium | 0.8 large
Segment trend: β₁ pre-interruption | β₃ post-interruption change
```

## Datenfluss

- **Liest:** `polar_nightly_hrv`, `measurements`, `sessions`, `session_metrics`
- **Schreibt:** `analyses/infectious/*.{md,png}`

## Grenzen

Heuristische Methode: Kein Kausalitätsnachweis; Konfoundfaktoren (Saisonalität, Geräteänderungen) nicht kontrolliert. Mindestdatenbedarf: ≥30 Tage je Segment empfohlen.

## Referenzen

- Penfold RB, Zhang F (2013). Use of Interrupted Time Series Analysis in Evaluating Health Care Quality Improvements. Academic Pediatrics, 13(6 Suppl):S38-S44. doi:10.1016/j.acap.2013.08.002 (ITS-Methode)
- Cohen J (1988). Statistical Power Analysis for the Behavioral Sciences (2nd ed.). Lawrence Erlbaum Associates. (Cohen's d: 0.2 small, 0.5 medium, 0.8 large)

## Aufruf

```bash
python analyse_postinfectious_its.py
python analyse_postinfectious_its.py --help
python analyse_postinfectious_its.py --from 2024-01-01 --to 2024-12-31
```
