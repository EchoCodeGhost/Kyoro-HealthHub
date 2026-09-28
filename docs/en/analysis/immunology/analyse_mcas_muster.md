# MCAS-Muster-Tracker

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/analysis/immunology/analyse_mcas_muster.py`

**Evidence tier:** heuristic (deliberate design from domain knowledge, no formal literature or validation basis)

## Purpose

Identifies wearable-based patterns (tachycardia, HRV drop, SpO₂ drop, temperature deviation) compatible with MCAS episodes — not a diagnostic instrument.

## Relevance

Enables detection of characteristic patterns of mast cell activation syndrome in wearable and symptom data, essential for the differential diagnosis of complex immunological diseases

## Method

Coincidence-based pattern tagging: ≥2 simultaneous signals on a day constitute a pattern day; thresholds are heuristic (own parameters, not clinically validated). SpO₂ signal uses a personalised threshold (lowest 10th percentile of the individual's own Garmin-source-deduplicated daily minima instead of a fixed literature value, see compute_spo2_threshold()); below 30 days of data the channel is deactivated ("not evaluable"). Pattern rate additionally computed over the intersection of days where rhr/hrv/spo2/temp ALL have data, to check whether the overall rate is dominated by single-channel availability.

## Scoring

```
Pattern-Tag: ≥2 gleichzeitige Signale an einem Tag aus {Tachykardie >90 bpm,
HRV-Abfall ≤−15%, SpO₂-Min. < eigenes 10%-Perzentil (personenbezogen, s. @method),
Wrist-Temp-Abweichung ≥+0.35°C, relevante Symptome}.
Kein klinischer Score — rein deskriptives Muster-Tagging.
Alle Schwellenwerte projektintern; nicht aus Validierungsstudie abgeleitet.
Orientierung: Afrin et al. 2020 (HaVOC-Konsensus), kein Wearable-Scoring.
```

## Data flow

- **Reads:** `measurements`, `symptoms`
- **Writes:** `analyses/immunology/mcas_muster_*.{md,png}`

## Limitations

Heuristic method: Wearable signals can neither confirm nor exclude patterns; specific validation requires laboratory evidence; symptom diary data sparse; temperature signal only usable from the availability date of a skin-temperature capable device. tachy_rhr=90 bpm is below the clinical tachycardia threshold of >100 bpm (ACC/AHA) — deliberately lower to capture sub-clinical elevations above individual baseline. The previous fixed SpO₂ threshold <94% (WHO hypoxaemia cutoff for clinical pulse oximetry) fired on 99.4% of all days with data — not transferable to optical wrist SpO2 (Garmin), whose raw readings are often structurally below 94% (sensor characteristic, not necessarily pathology). The 10th-percentile threshold is relative to the individual's own distribution, not an absolute clinically validated value, and unstable with too little history (<30 days) — hence deactivated rather than reporting an unreliable value.

## References

- Afrin LB, Ackerley MB, Bluestein LS, et al. (2021). Diagnosis of mast cell activation syndrome: a global "consensus-2". Diagnosis, 8(2), 137-152. doi:10.1515/dx-2020-0005
- Weiler CR (2020). Mast cell activation syndrome: tools for diagnosis and differential diagnosis. Journal of Allergy and Clinical Immunology: In Practice, 8(2), 498-506. doi:10.1016/j.jaip.2019.08.022

## Usage

```bash
python analyse_mcas_muster.py
python analyse_mcas_muster.py --help
python analyse_mcas_muster.py --from 2024-01-01 --to 2024-12-31
```
