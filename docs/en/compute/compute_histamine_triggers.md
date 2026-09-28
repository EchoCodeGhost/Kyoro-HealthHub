# Histamine trigger correlation: nutrition x histamine_food_db x symptom track.

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/compute/compute_histamine_triggers.py`

**Evidence tier:** heuristic (deliberate design from domain knowledge, no formal literature or validation basis)

## Purpose

Derives candidate food triggers by temporally correlating symptoms with preceding high-histamine meals.

## Relevance

Enables histamine trigger analysis, essential for allergological diagnostics

## Method

Meals (timestamped) are categorised via histamine_food_db; a symptom within the reaction window after a high-histamine meal produces a computed trigger. Symptom severity is mapped from scale 0–10 to 0–4 (/2.5).

## Scoring

```
Trigger-Score = Haeufigkeit * 30 + Symptomschwere * 20 + Konsistenz * 50
```

## Thresholds

| Value | Meaning |
|---|---|
| `histamine_cat in (high, liberator, blocker)` | counted as trigger |
| `histamine_cat = medium` | optional (--medium) |
| `reaction window` | default 8 h (--hours) |

## Data flow

- **Reads:** `nutrition_entries`, `histamine_food_db`, `symptoms`
- **Writes:** `food_triggers (INSERT OR IGNORE, source='computed')`

## Limitations

Heuristic method: Purely temporal correlation, not proof of causation. Confounders (other triggers, delayed reactions, cumulative load) are not modelled. Hypothesis-generating, not diagnostic.

## References

- Schnedl WJ, Enko D (2021). Histamine intolerance originates in the gut. Nutrients, 13(4), 1262. doi:10.3390/nu13041262
- Maintz L, Novak N (2007). Histamine and histamine intolerance. The American Journal of Clinical Nutrition, 85(5):1185-1196. doi:10.1093/ajcn/85.5.1185

## Usage

```bash
python3 compute_histamine_triggers.py
python3 compute_histamine_triggers.py --medium
python3 compute_histamine_triggers.py --hours 6
python3 compute_histamine_triggers.py --rebuild
python3 compute_histamine_triggers.py --dry-run
```
