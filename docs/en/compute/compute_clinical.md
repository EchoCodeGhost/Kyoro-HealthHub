# Clinical Findings Pre-Evaluation — Algorithmic computation of structured clinical findings.

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/compute/compute_clinical.py`

**Evidence tier:** heuristic (deliberate design from domain knowledge, no formal literature or validation basis)

## Purpose

Computes structured clinical findings before an LLM interprets the data — algorithms do the computation, the LLM only interprets the results. Serves as pre-structuring for medical assessments.

## Relevance

Enables calculation of clinical parameters, essential for medical analysis

## Method

Eight finding computations based on physiological data: 1. POTS criterion (ΔHR≥30 bpm supine→standing) - established clinical criterion (Freeman et al. 2011) 2. HRV change points - detection of significant HRV drops (rolling median, 7-day window, threshold: 2×MAD) 3. Post-Exertional Malaise (PEM) - detection of PEM patterns based on HRV drop >20% vs. baseline within 24-48h after exertion 4. HR recovery - heart rate recovery after exertion (1-minute window) 5. Sleep trend - linear regression of sleep quality over 30 days 6. Nocturnal SpO2 load - oxygen saturation burden during sleep 7. Post-exertional AF - atrial fibrillation detection in 3h window after exertion 8. ANS index - combined autonomic nervous system index

## Scoring

```
1. Orthostatic criterion   ΔHR >= 30 bpm supine->standing (POTS criterion)
2. HRV change points       (when did HRV drop? rolling median, 7-day window)
3. Post-Exertional Malaise  (HRV drop >20% vs. baseline, 24-48h post-exertion)
4. HR recovery class        after workout (bpm/min decline in first minute)
5. Sleep-quality trend      linear regression over 30 days
6. Nocturnal SpO2 load      burden score (min SpO2, % time <90%)
7. Post-exertional AF       within 3h after workout
8. ANS overall status       combined index (HRV + SpO2 + symptoms)
```

## Data flow

- **Reads:** `measurements`, `polar_nightly_hrv`, `daily_stress`, `sessions`, `session_metrics`, `sleep`, `health_canonical`
- **Writes:** `clinical_findings`

## Limitations

Heuristic method: Only the POTS criterion (ΔHR≥30 bpm supine→standing) is clinically established (Freeman et al. 2011); all other findings are unvalidated heuristics for pre-structuring. The heuristics are based on individual baselines and statistical thresholds. Does not replace clinical assessment.

## References

- Freeman R, Wieling W, Axelrod FB et al. (2011). Consensus statement on the definition of orthostatic hypotension, neurally mediated syncope and the postural tachycardia syndrome. Clinical Autonomic Research, 21(2):69-72. doi:10.1007/s10286-011-0119-5 (POTS Diagnostic Criteria)

## Usage

```bash
python3 compute_clinical.py
python3 compute_clinical.py --summary
python3 compute_clinical.py --person self
python3 compute_clinical.py --from 2024-01-01 --to 2024-12-31
```
