# Konsil-Synthese in Alltagssprache — Patientenversion des Vorsitz-Berichts.

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/analysis/manual/explain_synthesis.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Translates the consult chair's technical final report (analyse_synthesis.py) into plain language and adds concrete action guidance for the patient.

## Relevance

Makes the consult's final report understandable without jargon and adds concrete next steps for the patient

## Method

Reads the latest (or --file-specified) synthesis file, strips the working appendices (category notes, individual opinions — those are intermediate work product, not the final result), and has only the chair's final text translated into plain language by an LLM. Confidence/probability qualifiers must be preserved (see openspec/specs/documentation-conventions). The two standing recommendations (GP first, share reports between all treating doctors) are not left to the LLM — they are appended as a fixed section. If the source report mentions PEM, a fixed note is also appended clarifying that this project's PEM scores are a non-clinically-validated heuristic (see compute_pem.py @tier heuristic).

## Data flow

- **Reads:** `analyses/synthesis/synthesis_*.md`
- **Writes:** `analyses/synthesis/<name>_patientenversion.md (Markdown, lokal)`

## Limitations

Heuristic method: LLM translation, not medical advice. Does not replace talking to a doctor. No new medical claims are generated — only a rewording of the chair's existing text.

## Usage

```bash
python3 scripts/analysis/manual/explain_synthesis.py
python3 scripts/analysis/manual/explain_synthesis.py --file analyses/synthesis/synthesis_20260808_1704.md
python3 scripts/analysis/manual/explain_synthesis.py --lang en
```
