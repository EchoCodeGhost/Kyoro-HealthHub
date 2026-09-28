# Anwendungs-Verlaufs-Analyse

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/analysis/internal_medicine/analyse_treatment_response.py`

**Evidence tier:** heuristic (deliberate design from domain knowledge, no formal literature or validation basis)

## Purpose

Analyzes the effect of applications on events and HRV by comparing baseline periods before application with periods during or after application. Correlates entries from treatment_history.json with event and HRV data from the database.

## Relevance

Enables health data analysis, essential for medical diagnostics

## Method

1. Loads all entries from treatment_history.json and groups by category. 2. For single applications (short duration): compare event intensity/HRV the day before vs. day(s) after the application. 3. For ongoing applications (longer duration): compare event trend during the application vs. baseline before. 4. Aggregation by practitioner/category: which application type shows the most consistent improvements?

## Scoring

```
Event-Change: (Application - Baseline), negativ = Verbesserung
HRV-Change: (Application - Baseline), positiv = Verbesserung
Aggregation: Durchschnitt pro Kategorie
```

## Data flow

- **Reads:** `treatment_history.json`, `symptoms`, `measurements`, `(hrv_rmssd/rmssd_ms)`, `ppi_hrv_advanced`
- **Writes:** `analyses/internal_medicine/treatment_response_*.{md,png}`

## Limitations

Placebo/expectation effect not controllable, small sample size per category, self-report bias in events. Heuristic method: No control group design, correlative, n=1. Causal attribution not possible.

## References

- Rossettini, Carlino & Testa 2018, BMC Musculoskelet Disord (Kontextfaktoren als Trigger von Placebo-/Nocebo-Effekten bei
- Rossettini G, Carlino E, Testa M (2018). Clinical relevance of contextual factors as triggers of placebo and nocebo effects in musculoskeletal pain. BMC Musculoskeletal Disorders, 19(1). doi:10.1186/s12891-018-1943-8
- Choi SW, Wong GTC (2018). Quality improvement studies - pitfalls of the before and after study design. Anaesthesia, 73(11):1432-1435. doi:10.1111/anae.14451 (Limitationen unkontrollierter Vorher/Nachher-Vergleiche)

## Usage

```bash
python analyse_treatment_response.py
python analyse_treatment_response.py --help
python analyse_treatment_response.py --from 2024-01-01 --to 2024-12-31
```
