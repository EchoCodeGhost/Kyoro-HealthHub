# analyse_clinical_addendum.py — Klinisches Addendum zur Daten-Synthese

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/analysis/manual/analyse_clinical_addendum.py`

**Evidence tier:** heuristic (deliberate design from domain knowledge, no formal literature or validation basis)

## Purpose

Generates a clinical addendum for data synthesis

## Relevance

Enables health data analysis, essential for medical diagnostics

## Method

Reads the latest synthesis report and clinical observations from config (clinical.observations) and generates an addendum that addresses structural data gaps. Typical gaps: - Underestimation of patterns due to lack of measurement data - Pharmacological response patterns from clinical observation - Methodological biases (e.g., ceiling effect in orthostatic test)

## Scoring

```
Gewichtung basierend auf Datenverfügbarkeit und Beobachtungsqualität
```

## Data flow

- **Reads:** `Synthese-Berichte`, `aus`, `analyses/synthesis/`, `Config`, `clinical.observations`
- **Writes:** `Addendum als Markdown-Datei`

## Limitations

Heuristic method. Dependent on quality of clinical observations.

## References

- Topol EJ (2019). High-performance medicine: the convergence of human and artificial intelligence. Nature Medicine, 25(1):44-56. doi:10.1038/s41591-018-0300-7
- Moor M, Banerjee O, Abad ZSH, Krumholz HM, Leskovec J, Topol EJ, Rajpurkar P (2023). Foundation models for generalist medical artificial intelligence. Nature, 616(7956):259-265. doi:10.1038/s41586-023-05881-4

## Usage

```bash
python3 scripts/analysis/manual/analyse_clinical_addendum.py
python3 scripts/analysis/manual/analyse_clinical_addendum.py --synthesis analyses/synthesis/synthesis_20260704_2140.md
python3 scripts/analysis/manual/analyse_clinical_addendum.py --lang en
```
