# Post-COVID Schlaf-Wearable-Muster — Abgleich gegen RECOVER-Kohorte

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/analysis/infectious/analyse_postcovid_sleep_wearable.py`

**Evidence tier:** heuristic (deliberate design from domain knowledge, no formal literature or validation basis)

## Purpose

Compares seven sleep-wearable patterns (sleep HRV, resting heart rate, sleep-duration variability, breathing rate, sleep efficiency, REM latency, bedtime regularity) between a configurable pre- and post-window against the Long-COVID patterns reported in the RECOVER cohort.

## Relevance

Provides a concrete, literature-grounded comparison point for the post-infectious deterioration in one's own wearable data, instead of only a general "it got worse" statement.

## Method

Simple pre/post mean and dispersion comparison (arithmetic mean, standard deviation) restricted to Polar-sourced data only (device consistency), no significance test, no matching, no control group — single-subject self-comparison (n=1), not a cohort study.

## Scoring

```
Kein numerischer Score/keine Schwellenwert-Klassifikation — bewusster Verzicht,
da ein n=1-Vorher/Nachher-Vergleich gegen ein einzelnes Preprint keine
belastbare Grundlage für Schwellenwerte bietet. Die sieben Muster werden als
rohe Vorher/Nachher-Mittelwerte (+ Streuung bei Dauer/Bettzeit) tabellarisch
gegenübergestellt; die Richtungsinterpretation (passt/passt nicht zum
RECOVER-Muster) bleibt der LLM-Kommentierung bzw. der lesenden Person
überlassen, nicht einer im Skript festgelegten Regel.
```

## Data flow

- **Reads:** `polar_nightly_hrv`, `polar_sleep_hypnogram`, `sessions`, `session_metrics`
- **Writes:** `analyses/postinfectious/*.md`

## Limitations

Heuristic method: single-subject pre/post comparison (n=1), no cohort comparison, no control group, no significance test. REM latency = first REM epoch in the hypnogram from sleep onset (minutes) — a functional approximation of the clinical REM-latency definition, not a PSG-validated measurement. Bedtime regularity from `sessions.ts_start` (Polar), mapped onto a 24h window anchored before noon — an approximation, not circular statistics. Breathing rate is a nightly average, not REM-specific as in the reference study. Source study is a preprint (Research Square), not yet peer-reviewed. Data quality depends on Polar device coverage in the respective period; other device sources (Oura, Garmin, Whoop) deliberately excluded to avoid mistaking device artifacts for infection effects.

## References

- Parthasarathy S, Brosnahan S, Sieberts S, et al. (2025). Wearable-derived Sleep Measurements are Associated with Long-COVID in the RECOVER Adult Cohort. Research Square [Preprint]. doi:10.21203/rs.3.rs-7422764/v1 — Preprint, noch nicht peer-reviewed; Ergebnisse können sich bei Publikation noch ändern; die 7 Muster in diesem Skript stammen ausschließlich hieraus.
- Recherche zu eigenständiger Literatur speziell zur Bettzeit-/Zirkadianrhythmus-Verschiebung bei Long COVID (2026-08-24, NCBI eSearch/eFetch): **kein belastbares Zitat gefunden.** Goldstein CA et al. (2022, Brain Behav Immun Health, doi:10.1016/j.bbih.2022.100476) hat kein auffindbares strukturiertes Abstract, vermutlich Kommentar/Perspektivartikel ohne eigene Daten. Merikanto I et al. (2022, J Sleep Res, doi:10.1111/jsr.13542) ist ein **Protokoll-Paper** (beschreibt nur das geplante Studiendesign der ICOSS-Studie), keine Ergebnispublikation. Gezielte Suche nach "long covid delayed sleep phase chronotype" ergab 0 Treffer. **Der Bettzeit-Verspätungsbefund in diesem Skript ist damit eigene Beobachtung ohne externe Literaturstütze — nicht als literaturbestätigt darstellen.**

## Usage

```bash
python analyse_postcovid_sleep_wearable.py
python analyse_postcovid_sleep_wearable.py --help
```
