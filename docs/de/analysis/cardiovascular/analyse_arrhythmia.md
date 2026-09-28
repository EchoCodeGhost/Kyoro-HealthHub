# Arrhythmia-Muster & Trigger-Analyse

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/analysis/cardiovascular/analyse_arrhythmia.py`

**Evidenzstufe:** kalibriert (Literaturbasis + Parameter auf persönliche Baselines angepasst, keine externe Validierung)

## Zweck

Analysiert Muster, Häufigkeit, Tageszeitverteilung und Trigger-Zusammenhänge detektierter Arrhythmie-Episoden aus dem Polar-PPI-Datenstrom.

## Relevanz

Ermöglicht die kardiovaskuläre Analyse, essentiell für die Herz-Kreislauf-Diagnostik

## Methode

Liest aus compute_arrhythmia-generierten arrhythmie_episoden; korreliert Episodentage mit HRV (RMSSD), Stress-Score, Schlafeffizienz und SpO2 via Gruppenvergleich (Episodentag vs. episodenfreier Tag).

## Datenfluss

- **Liest:** `arrhythmie_episoden`, `daily_stress`, `symptoms`, `sessions`, `session_metrics`, `polar_nightly_hrv`
- **Schreibt:**

  ```
  analyses/cardiovascular/*.{md,png}, analyses/cardiovascular/episodes/*.png
  (--plot-episodes: Tachogramm+Lorenz-Plot pro Episode, Quelle via
  identity_resolver menschenlesbar beschriftet) (kein DB-Write)
  ```

## Grenzen

CV-basierte Episodenerkennung ist kein klinisches EKG; Polar-Daten können Bewegungsartefakte enthalten. Alle Korrelationen sind explorativ (n=1).

## Referenzen

- Perez MV, Mahaffey KW, Hedlin H et al. (2019). Large-Scale Assessment of a Smartwatch to Identify Atrial Fibrillation. New England Journal of Medicine, 381(20):1909-1917. doi:10.1056/NEJMoa1901183
- Tateno & Glass 2001, Med Biol Eng Comput (Erkennungsmethode hinter den hier analysierten arrhythmie_episoden, s. compute_arrhythmia.py),
- Tateno K, Glass L (2001). Automatic detection of atrial fibrillation using the coefficient of variation and density histograms of RR and ΔRR intervals. Medical and Biological Engineering and Computing, 39(6):664-671. doi:10.1007/BF02345439
- Malmivuo J, Plonsey R (1995). Bioelectromagnetism: Principles and Applications of Bioelectric and Biomagnetic Fields. Oxford University Press, New York. ISBN 978-0-19-505823-9 (kein DOI verfügbar)

## Aufruf

```bash
python analyse_arrhythmia.py
python analyse_arrhythmia.py --help
python analyse_arrhythmia.py --from 2024-01-01 --to 2024-12-31
python analyse_arrhythmia.py --plot-episodes --detection-method bigeminy_rr_alternation --from 2026-09-01
python analyse_arrhythmia.py --plot-episodes --max-episode-plots 50
```
