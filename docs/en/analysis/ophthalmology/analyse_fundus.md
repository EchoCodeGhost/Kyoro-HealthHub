# analyse_fundus.py — Fundusfotos auswerten (VLM) und Verlauf anzeigen

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/analysis/ophthalmology/analyse_fundus.py`

**Evidence tier:** heuristic (deliberate design from domain knowledge, no formal literature or validation basis)

## Purpose

Evaluates fundus photographs via Vision Language Model (VLM): optic disc (cup-to-disc ratio, ISNT rule), vessel findings and retina; stores structured findings text in imaging_analysis.

## Relevance

Enables automated evaluation of fundus photographs for early detection of retinal changes, essential for supporting ophthalmological assessment and monitoring

## Method

Structured VLM prompt for clinical findings description (no assessment output); results stored in imaging_analysis (DB). No automatic quantitative image analysis — pure LLM text generation.

## Scoring

```
Finding categories: optic_disc | vessels | retina | other
Severity: normal | mild | moderate | severe | not_assessable
```

## Data flow

- **Reads:** `imaging_files`, `(medicine_imaging_db)`, `imaging_analysis`, `(medicine_imaging_db)`
- **Writes:** `imaging_analysis (DB-Write), analyses/ophthalmology/*.{md,png}`

## Limitations

Heuristic method: VLM output is not validated for clinical diagnoses. Image quality and illumination affect description quality. No comparison with ophthalmological reference assessment. n=1, exploratory.

## References

- Esteva A, Kuprel B, Novoa RA et al. (2017). Dermatologist-level classification of skin cancer with deep neural networks. Nature, 542(7639):115-118. doi:10.1038/nature21056
- Gulshan V, Peng L, Coram M et al. (2016). Development and Validation of a Deep Learning Algorithm for Detection of Diabetic Retinopathy in Retinal Fundus Photographs. JAMA, 316(22):2402. doi:10.1001/jama.2016.17216

## Usage

```bash
python analyse_fundus.py
python analyse_fundus.py --help
python analyse_fundus.py --from 2024-01-01 --to 2024-12-31
```
