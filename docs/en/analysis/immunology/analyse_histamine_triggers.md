# Histamin-Trigger-Analyse

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/analysis/immunology/analyse_histamine_triggers.py`

**Evidence tier:** heuristic (deliberate design from domain knowledge, no formal literature or validation basis)

## Purpose

Analyses a histamine trigger diary for patterns of histamine intolerance: daily loads, top triggers, reaction time windows and symptom correlations.

## Relevance

Supports the clinical work-up and management of mast cell activation syndromes and histamine intolerance through systematic analysis of symptom patterns and triggers

## Method

Category-based histamine load scoring (high=3, medium=2, low=0, liberator=2); correlation with symptoms from the symptoms table.

## Scoring

```
Histaminlast-Score (kumuliert je Tag):
  high × 3  +  liberator × 2  +  medium × 2  +  blocker × 1  +  low × 0
Reaktionsrate: Einträge mit reaction_h-Angabe / Einträge gesamt (je Lebensmittel)
Basis: projektintern; Kategorie-Werte nicht aus einer Validierungsstudie abgeleitet.
Orientierung: Maintz & Novak 2007 Klassifikation histaminreicher Lebensmittel
(doi:10.1093/ajcn/85.5.1185). Kein Schwellenwert für klinische Bewertung.
```

## Data flow

- **Reads:** `food_triggers`, `symptoms`
- **Writes:** `analyses/immunology/histamine_triggers_*.{md,png}`

## Limitations

Heuristic method: Histamine load scoring is a simplified category model without individual portion-size calibration; not a validated instrument; missing lab values (DAO, histamine, tryptase) cannot be substituted.

## References

- Schnedl WJ, Enko D (2021). Histamine intolerance originates in the gut. Nutrients, 13(4), 1262. doi:10.3390/nu13041262
- Maintz L, Novak N (2007). Histamine and histamine intolerance. American Journal of Clinical Nutrition, 85(5), 1185-1196. doi:10.1093/ajcn/85.5.1185
- Afrin LB, Ackerley MB, Bluestein LS, et al. (2021). Diagnosis of mast cell activation syndrome: a global "consensus-2". Diagnosis, 8(2), 137-152. doi:10.1515/dx-2020-0005

## Usage

```bash
python analyse_histamine_triggers.py
python analyse_histamine_triggers.py --help
python analyse_histamine_triggers.py --from 2024-01-01 --to 2024-12-31
```
