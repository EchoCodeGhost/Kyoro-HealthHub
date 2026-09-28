# analyse_saliva_ph.py — Speichel-pH Heimmonitoring Trendanalyse

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/analysis/manual/analyse_saliva_ph.py`

**Evidence tier:** heuristic (deliberate design from domain knowledge, no formal literature or validation basis)

## Purpose

Analyzes saliva pH data from home monitoring

## Relevance

Enables health data analysis, essential for medical diagnostics

## Method

Reads saliva pH data from medicine.db (lab_manual, parameter="Speichel-pH"), groups by context (fasting_morning, post_meal_1h …) and creates: - Trend table of all contexts over time - Alarm flagging from thresholds in ~/.config/kyoro/saliva_ph_ranges.json - Context means + min/max range - Optional: LLM comment (internist/allergologist perspective) - Optional: Plot (pH trend per context)

## Scoring

```
Anomalie-Score basierend auf Anteil der Messungen außerhalb kontextspezifischer pH-Referenzbereiche
```

## Data flow

- **Reads:** `medicine.db`, `(lab_manual)`, `~/.config/kyoro/saliva_ph_ranges.json`
- **Writes:** `Analyseergebnisse als Markdown (analyses/manual/)`

## Limitations

Heuristic method. pH strip accuracy ±0.5; pH meter values more precise. Context separation depends on correct CSV input.

## References

- Tenovuo J, Lagerlöf F (1994). Saliva. In: Thylstrup A, Fejerskov O (Hrsg.), Textbook of Clinical Cariology (2. Aufl.). Munksgaard, Kopenhagen. (kein DOI verfügbar, Buchkapitel)
- Bardow A, Moe D, Nyvad B, Nauntofte B (2000). The buffer capacity and buffer systems of human whole saliva measured without loss of CO2. Archives of Oral Biology, 45(1):1-12. doi:10.1016/S0003-9969(99)00119-3

## Usage

```bash
python3 scripts/analysis/manual/analyse_saliva_ph.py
python3 scripts/analysis/manual/analyse_saliva_ph.py --plot
python3 scripts/analysis/manual/analyse_saliva_ph.py --from 2026-01-01
python3 scripts/analysis/manual/analyse_saliva_ph.py --no-llm
```
