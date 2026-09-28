# Umwelt-Substanz-Korrelation

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/analysis/internal_medicine/analyse_environmental_triggers.py`

**Evidence tier:** heuristic (deliberate design from domain knowledge, no formal literature or validation basis)

## Purpose

Identifies possible correlations between environmental substances and documented events by comparing frequency before vs. during exposure period, as well as INCI ingredient-level correlation (not just brand-level).

## Relevance

Enables health data analysis, essential for medical diagnostics

## Method

1. Loads all entries from environmental_substances.json and groups by category. 2. For each entry: compares event frequency in the n days before date_from (baseline) vs. during date_from-date_to (exposure). 3. If verdachtssymptom is set: targeted filtering for this term in symptoms.symptom_type or symptoms.notes (substring search). 4. Output: table per substance with baseline rate vs. exposure rate, sorted by largest difference. 5. Additional aggregation: Collect all ingredients across all entries and calculate the same rate difference per ingredient. Entries without ingredients are skipped. 6. Output: Second section "Suspected Ingredients" with cross-reference to known allergens from lookup_ingredients.KNOWN_ALLERGENS.

## Scoring

```
Rate-Differenz: (Expositions-Rate - Baseline-Rate), hoeher = staerkerer Verdacht
Basis: Tage mit Ereignissen / Gesamttage im Zeitraum
INCI-Scoring: gleiche Berechnung pro Inhaltsstoff
```

## Data flow

- **Reads:** `environmental_substances.json`, `(inkl.`, `ingredients`, `ingredients_source)`, `symptoms`, `measurements`
- **Writes:** `analyses/internal_medicine/environmental_triggers_*.{md,png}`

## Limitations

Heuristic method: No control group design, correlative, n=1. Causal attribution not possible. Confounding by parallel factors not controlled. verdachtssymptom is unstructured free text. INCI lookup data quality varies by source (obf_text vs obf_vision).

## References

- Whitaker et al. 2006, Stat Med (Self-Controlled Case Series Methode, Grundprinzip des Baseline-vs.-Expositionsvergleichs innerhalb derselben
- Whitaker HJ, Paddy Farrington C, Spiessens B, Musonda P (2006). Tutorial in biostatistics: the self‐controlled case series method. Statistics in Medicine, 25(10):1768-1797. doi:10.1002/sim.2302
- Choi SW, Wong GTC (2018). Quality improvement studies - pitfalls of the before and after study design. Anaesthesia, 73(11):1432-1435. doi:10.1111/anae.14451 (Limitationen unkontrollierter Vorher/Nachher-Vergleiche)

## Usage

```bash
python analyse_environmental_triggers.py
python analyse_environmental_triggers.py --help
python analyse_environmental_triggers.py --from 2024-01-01 --to 2024-12-31
```
