# analyse_reha_klinik_empfehlung.py — LLM-gestützte Reha-Klinikempfehlung

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/analysis/manual/analyse_reha_klinik_empfehlung.py`

**Evidence tier:** heuristic (deliberate design from domain knowledge, no formal literature or validation basis)

## Purpose

Matches the current clinical picture (latest consult-synthesis report) against one or more parsed rehab facility lists (DRV, dasrehaportal.de) and has an LLM produce a justified, ranked recommendation — as a basis for exercising the German statutory right to request a specific facility (SGB IX §8), not an assignment.

## Relevance

Supports rehab planning with AI-assisted matching, direct relevance to personal health data (clinical picture)

## Method

Reads the latest full synthesis report from analyses/synthesis/ (only the main body before the appendix) and the compact facility overview of the sources selected via --sources (default: drv only). Each source is normalized to a shared schema (reference/source/name/city/categories/offer/cost carrier/extra field) and tagged with its own reference (e.g. "DRV-55", "REHAPORTAL-1") so the LLM can cite facilities unambiguously across sources. Optional: --kostentraeger excludes, in Python (not just via LLM instruction), facilities with confirmed evidence that they bill none of the named carriers — facilities with no cost-carrier data stay in and are marked "unknown". --priorities searches for text matches in categories/offer/description/extra field, moves matches to the front and marks them with ★ — weighted by position in the --priorities list (listed first counts most), not raw match count, so a single hit on the top priority outranks several hits on lower ones. Priorities with no match are reported explicitly instead of being silently ignored. --question appends a free-form additional question/constraint. The result is saved as a markdown report.

## Scoring

```
Rangfolge durch das LLM anhand inhaltlicher Übereinstimmung
zwischen Krankheitsbild und Kategorien/Klinikangebot der
jeweiligen Einrichtung — kein numerischer Score, freie Begründung.
```

## Data flow

- **Reads:** `analyses/synthesis/synthesis_*.md`, `(neuester`, `vollständiger`, `Bericht)`, `imports/drv-kliniken/kliniken.json`, `(Quelle`, `"drv")`, `imports/rehaportal/kliniken.json`, `(Quelle`, `"rehaportal")`
- **Writes:** `analyses/reha_klinik/empfehlung_<timestamp>.md`

## Limitations

Heuristic LLM analysis, not an assignment decision — the relevant payer makes the actual choice; this is only a basis for one's own application. "Offer" is facility-authored free text, not a controlled taxonomy. Cost-carrier data from dasrehaportal.de only exists for facilities whose detail page was already loaded via rehaportal_details_download.py. No automatic remote fallback — --backend must be chosen explicitly.

## References

- Muneer A, Zhang K, Hamdi I, Qureshi R, Waqas M, Fouad S, Ali H, Anwar SM, Wu J (2026). Foundation models in biomedical imaging: turning hype into reality. Nature Biomedical Engineering, 10:1557-1575. doi:10.1038/s41551-026-01762-z (REAL-FM framework — Grundlage für die über grounding_suffix() angehängte Konfidenz-/Beleg-Pflicht, dieselbe Referenz wie analyse_synthesis.py)

## Usage

```bash
python3 analyse_reha_klinik_empfehlung.py --list-backends
python3 analyse_reha_klinik_empfehlung.py --backend medical
python3 analyse_reha_klinik_empfehlung.py --backend default --top 8
python3 analyse_reha_klinik_empfehlung.py --backend default         --priorities "Orthopädie,Schmerztherapie" --question "nur Kliniken in Bayern"
python3 analyse_reha_klinik_empfehlung.py --backend default         --sources drv,rehaportal --kostentraeger "GKV,DRV"
```
