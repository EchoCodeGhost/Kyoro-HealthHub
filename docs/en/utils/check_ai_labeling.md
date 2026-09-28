# KI-Kennzeichnungs-Compliance-Check

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/utils/check_ai_labeling.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Automatically checks that no script implements its own hand-rolled LLM chat-completion call without using the shared AI-generated label (modules.llm.ai_label()). openspec/specs/ethics-enforcement/spec.md ("Labeling of AI-generated output") was previously enforced only by manual PR review — an audit found most call_llm() callers without any labeling, plus two scripts (analyse_synthesis.py, analyse_clinical_addendum.py) that bypass modules.llm.call_llm() entirely and would therefore never reach its automatic labeling (call_llm(..., label_output=True), the default since this fix) either.

## Relevance

Technical enforcement of the AI-labeling requirement (see docs/ETHICS.md §6, openspec/specs/ethics-enforcement/spec.md) — without this check, a new bypass of call_llm() could silently produce unlabeled output.

## Method

Scans scripts/**/*.py for the OpenAI-compatible chat message pattern ("role": "system" AND "role": "user" in the same file — the signature of a hand-rolled chat-completion request). Where that matches, the same file must also call ai_label(. modules/llm.py and utils/llm_provider.py are the canonical implementation (labeling originates there) and are exempt; llm_benchmark.py is a developer tool for comparing models, not end-user-facing clinical output, and is documented as exempt.

## Data flow

- **Reads:** `scripts/**/*.py`
- **Writes:** `STDOUT/STDERR (Fehlermeldungen)`

## Limitations

Source-text heuristic (no AST/data-flow tracking) — does not detect chat payloads assembled dynamically from strings, nor labeling via aliases/ re-exports of ai_label.

## Usage

```bash
python3 scripts/utils/check_ai_labeling.py
python3 scripts/utils/check_ai_labeling.py --path scripts
```
