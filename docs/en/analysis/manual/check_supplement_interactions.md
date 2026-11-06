# check_supplement_interactions.py — Interaktions-Hinweise Supplement × aktuelle Medikamentenliste

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/analysis/manual/check_supplement_interactions.py`

**Evidence tier:** experimental (exploratory, no stable conceptual foundation, hypothesis-generating)

## Purpose

Lists current chronic entries from medicine.db and has an LLM name known, well-established interaction/contraindication concerns with one or more supplements under consideration. NOT a safety clearance — only a discussion basis for a professional.

## Relevance

Provides a discussion basis for supplement interactions, not a substitute for professionals

## Method

Reads medications (medicine.db), takes the most recent entry per drug_name with is_chronic=1. Builds a prompt from that plus the given supplement names to the configured LLM (analysis tier, no local-only requirement like raw document extraction — same as analyse_lab_verlauf.py). The system prompt explicitly requires: name only well-established concerns, no final safety verdict, always refer to professional consultation. Grounding suffix and AI labeling run automatically via modules.llm.call_llm. No numeric score — the "established/not established" judgment rests entirely with the configured LLM.

## Data flow

- **Reads:** `medicine.db`, `(medications)`
- **Writes:** `Analyseergebnis als Markdown (analyses/manual/)`

## Limitations

NOT a substitute for a professional review. Quality depends on the configured LLM's knowledge — it can miss established interactions or phrase things with false confidence. No structured interaction database involved, since none exists in this project.

## Usage

```bash
python3 check_supplement_interactions.py --supplement "Vitamin D3"
python3 check_supplement_interactions.py --supplement "Magnesium" --supplement "Melatonin"
```
