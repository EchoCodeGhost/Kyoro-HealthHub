# analyse_synthesis.py — LLM-basierte Synthese aller Einzelanalysen

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/analysis/manual/analyse_synthesis.py`

**Evidence tier:** heuristic (deliberate design from domain knowledge, no formal literature or validation basis)

## Purpose

Creates LLM-based synthesis of all individual analyses

## Relevance

Enables health data analysis, essential for medical diagnostics

## Method

Reads the latest markdown reports from analyses/ and has the LLM evaluate all individual findings impartially in the overall context: cross-cutting patterns, likely connections, next steps, priorities. The LLM does not receive any pre-diagnoses — it derives everything from the data. Optional: Multi-model panel (consult mode) — multiple LLMs assess independently (each given the full analysis prompt). The chair then reads the raw data category by category (one round per medical category under scripts/analysis/, e.g. cardiovascular, sleep, infectious) instead of all at once, to stay within context-window limits; each category round gets all four complete panel opinions plus all prior category notes (unchanged, never overwritten) and writes its own, final note. A final round reads all category notes + all panel opinions again and writes the final synthesis. All category notes remain as standalone artifacts in the appendix (chain of custody). Enabled via synthesis_panel.enabled=true in health_config.json.

## Scoring

```
Synthese-Score basierend auf Konsistenz, Schweregrad und zeitlicher Persistenz der Befunde
```

## Data flow

- **Reads:** `Alle`, `Analyse-Berichte`, `aus`, `analyses/`
- **Writes:** `Synthese-Bericht als Markdown (mit Anhang: Einzelmeinungen bei Panel-Modus)`

## Limitations

Heuristic method: Heuristic LLM analysis. No medical diagnosis.

## References

- Singhal K, Azizi S, Tu T et al. (2023). Large language models encode clinical knowledge. Nature, 620(7972):172-180. doi:10.1038/s41586-023-06291-2
- Topol EJ (2019). High-performance medicine: the convergence of human and artificial intelligence. Nature Medicine, 25(1):44-56. doi:10.1038/s41591-018-0300-7
- Muneer A, Zhang K, Hamdi I, Qureshi R, Waqas M, Fouad S, Ali H, Anwar SM, Wu J (2026). Foundation models in biomedical imaging: turning hype into reality. Nature Biomedical Engineering, 10:1557-1575. doi:10.1038/s41551-026-01762-z (REAL-FM framework — Grundlage fuer Abschnitt "Konfidenz & Beleglage" und die Vorsitz-Gegenprüfung gegen die eigenen Kategorie-Notizen weiter unten)

## Usage

```bash
python3 scripts/analysis/analyse_synthesis.py
python3 scripts/analysis/analyse_synthesis.py --since 2026-06-01
python3 scripts/analysis/analyse_synthesis.py --top 25 --bottom 80
python3 scripts/analysis/analyse_synthesis.py --dry-run
python3 scripts/analysis/analyse_synthesis.py --lang en
python3 scripts/analysis/analyse_synthesis.py --no-panel
python3 scripts/analysis/analyse_synthesis.py --yes
```
