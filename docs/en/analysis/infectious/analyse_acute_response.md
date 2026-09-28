# analyse_acute_response.py — Retrospektive Analyse akuter Systemreaktionen

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/analysis/infectious/analyse_acute_response.py`

**Evidence tier:** research (peer-reviewed literature basis, but no formal clinical validation study with endpoints)

## Purpose

Identifies acute episodes from the acute_events table, clusters consecutive days with score ≥ 1 into episodes, creates time-series plots with severity colour bands, and writes a Markdown report with optional LLM commentary. Launches an anamnesis dialog with mandatory red-flag screening for moderate/severe episodes.

## Relevance

Enables early detection and systematic documentation of acute health deteriorations, essential for emergency recognition and retrospective analysis of disease progression

## Method

Episode clustering: consecutive days with score_total ≥ 1, gaps of up to 2 days tolerated. Plot: score_total as bars, hrv_rmssd as line (right y-axis), SpO2 anomalies as scatter. Severity bands as background colours (none=white, mild=yellow, moderate=orange, severe=red). Clinical events from cfg.clinical.events as vertical lines. Anamnesis dialog: Tier 0 (emergency check) → Tier 1 (mandatory red flags: stroke/heart attack/anaphylaxis/ sepsis/tick bite) → Tier 2 (chief complaint) → Tier 3 (modules).

## Data flow

- **Reads:** `acute_events`
- **Writes:** `analyses/infectious/acute_response_{from}_{to}.{md,png}`

## Limitations

Requires a prior compute_acute_events run. Episode clustering is heuristic (gap_days=2 parameterised). No causal link between episode and trigger. Anamnesis dialog is not a validated medical device. LLM commentary requires a configured LLM endpoint.

## References

- Royal College of Physicians (2017). National Early Warning Score (NEWS) 2: Standardising the assessment of acute-illness severity in the NHS. RCP, London. https://www.rcp.ac.uk/resources/national-early-warning-score-news-2/ doi: nicht verfügbar (Leitliniendokument)
- DGN/DSG AWMF 030-046 (Schlaganfall); ESC ACS 2023; WAO/EAACI Anaphylaxis 2020;
- S3 Sepsis AWMF 079-001; AWMF 013-054 (Borreliose); RKI FSME 2023

## Usage

```bash
python3 scripts/analysis/infectious/analyse_acute_response.py
python3 scripts/analysis/infectious/analyse_acute_response.py --plot --no-llm
python3 scripts/analysis/infectious/analyse_acute_response.py --from 2023-01-01 --to 2024-12-31
python3 scripts/analysis/infectious/analyse_acute_response.py --min-severity moderate
python3 scripts/analysis/infectious/analyse_acute_response.py --no-interactive
```
