# analyse_skin.py — Hautlaesionen Verlaufsanalyse

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/analysis/manual/analyse_skin.py`

**Evidence tier:** heuristic (deliberate design from domain knowledge, no formal literature or validation basis)

## Purpose

Shows temporal progression of skin lesions with LLM/VLM analysis

## Relevance

Enables health data analysis, essential for medical diagnostics

## Method

Analyzes skin lesions and shows: - Overview of all lesions with current triage status - Timeline of a single lesion (all photos + VLM findings) - VLM analysis of all unanalyzed photos (--analyse) - LLM delta analysis: changes between recordings

## Scoring

```
Triage-Score basierend auf Läsionsgröße, Veränderungsrate und VLM-Klassifikation
```

## Data flow

- **Reads:** `lesion_photos`, `lesion_metadata`
- **Writes:** `Analyseergebnisse als Markdown`

## Limitations

Heuristic method. VLM/LLM analysis may be inaccurate.

## References

- Esteva A, Kuprel B, Novoa RA et al. (2017). Dermatologist-level classification of skin cancer with deep neural networks. Nature, 542(7639):115-118. doi:10.1038/nature21056
- Tschandl P, Codella N, Akay BN et al. (2019). Comparison of the accuracy of human readers versus machine-learning algorithms for pigmented skin lesion classification: an open, web-based, international, diagnostic study. The Lancet Oncology, 20(7):938-947. doi:10.1016/S1470-2045(19)30333-X

## Usage

```bash
python3 scripts/analysis/analyse_skin.py              # Uebersicht alle Laesionen
python3 scripts/analysis/analyse_skin.py --analyse    # VLM fuer alle neuen Fotos
python3 scripts/analysis/analyse_skin.py --lesion 3   # Verlauf Laesion 3
python3 scripts/analysis/analyse_skin.py --lesion 3 --compare  # LLM-Delta
python3 scripts/analysis/analyse_skin.py --watch-list  # Nur Laesionen mit Handlungsbedarf
```
