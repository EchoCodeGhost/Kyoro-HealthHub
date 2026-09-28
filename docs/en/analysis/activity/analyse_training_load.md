# Workout load & Recoverys-Analyse

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/analysis/activity/analyse_training_load.py`

**Evidence tier:** heuristic (deliberate design from domain knowledge, no formal literature or validation basis)

## Purpose

Analyses Polar training load (load, sport type, duration) with focus on PEM risk, load tolerance and safe activity budget; correlates with next-day HRV and step count.

## Relevance

Enables activity data analysis, essential for movement and fitness analysis

## Method

Aggregates training sessions from sessions/session_metrics; correlates training load with next-day RMSSD; PEM risk model (load groups × HRV drop) is proprietary without formal validation.

## Scoring

```
Load classification: low <300 | moderate 300-600 | high 600-900 | very high >900 (Polar Load units)
PEM risk: low | moderate | high | critical (based on ACWR + HRV drop)
```

## Data flow

- **Reads:** `sessions`, `session_metrics`, `measurements`, `polar_nightly_hrv`
- **Writes:** `analyses/activity/*.{md,png}`

## Limitations

Heuristic method: ACWR concept (Gabbett 2016) provides orientation; specific thresholds and PEM risk classes are not clinically validated. Data limited to Polar-recorded sessions.

## References

- Gabbett TJ (2016). The training—injury prevention paradox: should athletes be training smarter and harder?. British Journal of Sports Medicine, 50(5):273-280. doi:10.1136/bjsports-2015-095788
- Ruijgt TM, Slaghekke A, Ellens A, Janssen KW, Wüst RCI (2026). Wearable Heart Rate Variability Monitoring, Autonomic Dysfunction and Post-exertional Malaise in Long COVID: An Observational Study. Sports Medicine, online ahead of print. doi:10.1007/s40279-026-02487-4 (peer-reviewed; n=121 Long-COVID + 21 Kontrollen; HRV bleibt nach Belastung nahe/über der ersten ventilatorischen Schwelle einen vollen Tag supprimiert, stärkere Belastung korreliert mit stärker reduzierter nächtlicher HRV — stützt Wearable-HRV als PEM-Risikomarker speziell im Long-COVID-Kontext)

## Usage

```bash
python analyse_training_load.py
python analyse_training_load.py --help
python analyse_training_load.py --from 2024-01-01 --to 2024-12-31
```
