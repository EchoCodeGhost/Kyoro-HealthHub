# Changepoint-Detektion auf täglichen Marker-Zeitreihen.

> GENERIERT AUS DOCSTRING — NICHT HÄNDISCH EDITIEREN.  
> Source: `scripts/analysis/neurology/analyse_changepoint.py`

**Evidenzstufe:** Heuristik (deliberate Designentscheidung aus Domänenwissen, keine formale Literatur- oder Validierungsbasis)

## Zweck

Detektiert anhaltende Niveau-Sprünge (Step-Changes) in täglichen Marker-Zeitreihen und datiert sie; vergleicht Brüche mit konfigurierten klinischen Ereignissen.

## Relevanz

Ermöglicht die neurologische Analyse, essentiell für die Nervensystemdiagnostik

## Methode

Binary Segmentation mit Mean-Shift-Kosten (Between-Group-SS) und verteilungsfreiem Permutationstest (500 Permutationen, p < 0,01); Mindest- Effektgröße Cohen's d ≥ 0,5. Schwellen intern konfiguriert, nicht validiert.

## Berechnung

```
Changepoint detection: binary segmentation with between-group SS cost
Effect size threshold: Cohen's d >= 0.5 for sustained level shifts
Significance: p < 0.01 (permutation test with 500 permutations)
```

## Datenfluss

- **Liest:** `daily_stress`, `polar_nightly_hrv`, `ppi_hrv_advanced`, `measurements`
- **Schreibt:** `analyses/neurology/*.{md,png} (kein DB-Write)`

## Grenzen

Heuristische Methode: Rein statistisch; keine kausale Interpretation. Consumer-Sensorik mit Messartefakten. Permutationstest-Power bei kurzen Segmenten eingeschränkt. Hypothesengenerierend — keine klinischen Schlussfolgerungen.

## Referenzen

- Killick R, Eckley IA (2014). changepoint: An R Package for Changepoint Analysis. Journal of Statistical Software, 58(3). doi:10.18637/jss.v058.i03
- Truong C, Oudre L, Vayatis N (2020). Selective review of offline change point detection methods. Signal Processing, 167:107299. doi:10.1016/j.sigpro.2019.107299

## Aufruf

```bash
python analyse_changepoint.py
python analyse_changepoint.py --help
python analyse_changepoint.py --from 2024-01-01 --to 2024-12-31
```
