# ME/CFS Score — IOM 2015 / ICC 2011 Kriterien

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/analysis/neurology/analyse_mecfs.py`

**Evidence tier:** heuristic (deliberate design from domain knowledge, no formal literature or validation basis)

## Purpose

Scores wearable biomarkers against the core symptom domains of IOM 2015 and ICC 2011 criteria (PEM, unrefreshing sleep, fatigue, cognition, orthostasis) — objective biomarkers only, no clinical assessment.

## Relevance

Enables neurological analysis, essential for nervous system diagnostics

## Method

Rule-based scoring with cited thresholds (POTS ≥30 bpm, DFA α1=0.75, RMSSD <25 ms, deep sleep <15%, MET-minutes); traffic-light status (met/partial/not met/no data).

## Scoring

```
IOM 2015 criteria: PEM + unrefreshing sleep + fatigue + (cognition OR orthostatic intolerance)
ICC 2011 criteria: PENE + sleep + pain + neurology/autonomy/immunology
Traffic light status: green met | yellow partial | red not met | gray no data
```

## Data flow

- **Reads:** `measurements`, `sessions`, `session_metrics`, `symptoms`, `clinical_findings`
- **Writes:** `analyses/postinfectious/mecfs_*.{md,png}`

## Limitations

Heuristic method: Biomarker-to-criterion mapping is heuristic and not formally validated; long-term patterns require medical assessment; resting DFA α1 norms differ from exercise norms; severity classification is indicative only.

## References

- Institute of Medicine (2015). Beyond Myalgic Encephalomyelitis/Chronic Fatigue Syndrome: Redefining an Illness. National Academies Press, Washington, DC. doi:10.17226/19012
- Carruthers BM, van de Sande MI, De Meirleir KL et al. (2011). Myalgic encephalomyelitis: International Consensus Criteria. Journal of Internal Medicine, 270(4):327-338. doi:10.1111/j.1365-2796.2011.02428.x (ICC 2011)
- NICE NG206 (2021): Myalgic encephalomyelitis/chronic fatigue syndrome — guidance; www.nice.org.uk/guidance/ng206 Davenport et al., Workwell Foundation (2-day CPET / ventilatory threshold; the MET-minute cut-offs in REF are heuristic, not Workwell's)
- Davis et al. 2023, Nature Reviews (PEM biomarkers) — UNVERIFIED, no DOI found; no threshold in REF relies on it any more
- Flatt & Esco 2016, Int J Sports Med (DOI ausstehend) (HRV night measurement)
- Rowe PC, Underhill RA, Friedman KJ et al. (2017). Myalgic Encephalomyelitis/Chronic Fatigue Syndrome Diagnosis and Management in Young People: A Primer. Frontiers in Pediatrics, 5:121. doi:10.3389/fped.2017.00121 (Orthostasis & POTS in ME/CFS)
- Ohayon et al. 2004, Sleep 27(7):1255-73 (Tiefschlafanteil altersabhängig)

## Usage

```bash
python analyse_mecfs.py
python analyse_mecfs.py --help
python analyse_mecfs.py --from 2024-01-01 --to 2024-12-31
```
