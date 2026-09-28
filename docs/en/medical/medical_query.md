# medical_query.py — Medizinische Datenanalyse via LLM

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/medical/medical_query.py`

**Evidence tier:** heuristic (deliberate design from domain knowledge, no formal literature or validation basis)

## Purpose

Analyzes medical data from CSV files directly via LLM models. Enables natural language queries on lab results and medication data.

## Relevance

Provides health data functions, essential for medical data processing

## Method

Reads CSV files from various sources: lab results, medications, health data. Supports various specialized medical models (Med42, OpenBioLLM, MMed, BioMistral) and ensembles.

## Scoring

```
Relevanz-Score basierend auf Abweichung von Referenzbereichen und klinischer Signifikanz
```

## Data flow

- **Reads:** `medicine/laborbefunde/*.csv`, `medicine/medikamente.csv`, `imports/manual/health_visits.txt`
- **Writes:** `analyses/medical/ Verzeichnis (LLM-Analyseergebnisse)`

## Limitations

Heuristic method: Results depend on LLM model quality and input data quality. No automatic validation. For support only, not for diagnosis.

## References

- Singhal K, Azizi S, Tu T et al. (2023). Large language models encode clinical knowledge. Nature, 620(7972):172-180. doi:10.1038/s41586-023-06291-2
- Moor M, Banerjee O, Abad ZSH et al. (2023). Foundation models for generalist medical artificial intelligence. Nature, 616(7956):259-265. doi:10.1038/s41586-023-05881-4

## Usage

```bash
python medical_query.py labor                    # Med42 (Standard)
python medical_query.py labor --model qwen3
python medical_query.py labor --ensemble
python medical_query.py medikamente
python medical_query.py health_visits
```
