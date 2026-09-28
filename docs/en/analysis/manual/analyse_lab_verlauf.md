# analyse_lab_verlauf.py — Zeitlicher Verlauf aller Laborwerte als Tabelle + Plot

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/analysis/manual/analyse_lab_verlauf.py`

**Evidence tier:** heuristic (deliberate design from domain knowledge, no formal literature or validation basis)

## Purpose

Creates a longitudinal table of all lab values from lab_manual: rows = parameters (grouped by category), columns = measurement dates. Out-of-range values (↑ / ↓) are flagged.

## Relevance

Enables health data analysis, essential for medical diagnostics

## Method

Reads lab_manual from medicine.db, pivots by (kategorie, parameter) × date, prints one table per category, optionally generates plots. Qualitative values (neg/pos) are shown as text, not plotted.

## Scoring

```
Anomalie-Score pro Parameter: Anzahl außerhalb-Referenz-Messungen / Gesamtmessungen
```

## Data flow

- **Reads:** `medicine.db`, `(lab_manual)`
- **Writes:** `Analyseergebnisse als Markdown (analyses/manual/), optional PNG`

## Limitations

Reference values come directly from the DB (set during import) and may vary between labs. Qualitative parameters are not plotted.

## References

- Ozarda Y (2016). Reference intervals: current status, recent developments and future considerations. Biochemia Medica, 26(1), 5-16. doi:10.11613/BM.2016.001

## Usage

```bash
python3 scripts/analysis/manual/analyse_lab_verlauf.py
python3 scripts/analysis/manual/analyse_lab_verlauf.py --plot
python3 scripts/analysis/manual/analyse_lab_verlauf.py --kategorie Blutbild
python3 scripts/analysis/manual/analyse_lab_verlauf.py --from 2024-01-01 --plot
python3 scripts/analysis/manual/analyse_lab_verlauf.py --no-llm
python3 scripts/analysis/manual/analyse_lab_verlauf.py --exclude-source import_urine_strip
```
