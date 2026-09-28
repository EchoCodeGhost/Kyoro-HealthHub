# Produkt-Inhaltsstoff-Lookup via Open Beauty Facts + Open Products Facts + Open Food Facts + PubChem + Claude Vision.

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/utils/lookup_ingredients.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Enables looking up product ingredients from multiple databases: Open Beauty Facts (cosmetics), Open Products Facts (household products), Open Food Facts (food/cosmetic borderline cases), plus optional enrichment with PubChem data (chemical properties, GHS classification). If text is missing, the product photo is downloaded and analyzed via vision LLM.

## Relevance

Enables data lookup and referencing, essential for data integration

## Method

Extended lookup chain: 1. Open Beauty Facts (Text) 2. Open Products Facts (Text) — fallback for household products 3. Open Food Facts (Text) — fallback for food/cosmetic borderline cases 4. Vision fallback (photo) — for all databases 5. PubChem enrichment (optional) — for each found INCI name Consistent allergen matching against local reference tables (ECHA-SVHC, CosIng) and hand-curated KNOWN_ALLERGENS list.

## Data flow

- **Reads:** `Open`, `Beauty`, `Facts`, `API`, `Open`, `Products`, `Facts`, `API`, `Open`, `Food`, `Facts`, `API`, `PubChem`, `API`, `(optional)`, `Produktfotos`
- **Writes:** `Keine Tabellen (gibt Inhaltsstoff-Daten zurück), data/reference/*.csv (lokal)`

## Limitations

Dependent on data quality of various APIs and vision accuracy. PubChem queries may fail for exotic ingredients. Reference tables (ECHA/CosIng) must be maintained locally. Detects one specific, actually-observed data defect: when OBF's/ OPF's/OFF's `ingredients_text` is missing commas between some INCI names, both the raw-text split and OBF's own "structured" ingredients array glue several names into one entry — and the previous >80-char cutoff silently discarded the worst-merged entries entirely instead of flagging them. Both symptoms (suspiciously long comma-less multi-word entries; discarded oversized entries) now raise a `data_quality_warning` and, if vision fallback is enabled, automatically trigger a photo cross-check. This detection is a heuristic (word count/length) and does not cover every possible form of source-text corruption.

## Usage

```bash
python lookup_ingredients.py
python lookup_ingredients.py --help
python lookup_ingredients.py "Elmex Gelee" --no-pubchem
python lookup_ingredients.py --barcode 8718951466043 --no-vision
```
