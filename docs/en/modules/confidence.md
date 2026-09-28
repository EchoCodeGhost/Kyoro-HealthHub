# confidence.py — Einheitliche Konfidenz-Kennzeichnung für Analyse-Befunde

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/modules/confidence.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Provides a unified vocabulary to tag every finding communicated in an analysis report with one of three confidence levels: confirmed, suspected, open lead.

## Relevance

Without a unified label, analysis reports mix established facts with mere hypotheses without readers (patient, physician, expert witness) being able to tell them apart — critical for a project with a court-admissibility goal.

## Method

Pure formatting module, no computation. A single function `label_finding()` takes German text, English text and a confidence level, and returns both texts with the matching emoji prefix.

## Data flow

- **Reads:** `keine`
- **Writes:** `keine`

## Limitations

Pure formatting module with no medical logic or limitations.

## Usage

```bash
from modules.confidence import label_finding
de, en = label_finding("Borrelia-Infektion serologisch bestätigt",
                       "Borrelia infection serologically confirmed",
                       "confirmed")
# de == "✅ Bestätigt: Borrelia-Infektion serologisch bestätigt"
from modules.confidence import label_finding
de, en = label_finding("Erhöhtes AFib-Risiko", "Elevated AFib risk", "suspected")
```
