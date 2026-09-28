# check_commit_message_privacy — Blocks personal data in commit messages

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/utils/check_commit_message_privacy.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Checks a commit message for concrete personal values read from the real health/device database (percentages, row counts, clinical-unit measurements, exact dates, month+year timeframes) — commit messages are just as public as code in this repo; a bugfix message may explain the mechanism but must not cite specific figures from the user's own health history or device history.

## Relevance

Prevents concrete personal health/device values from entering the public repo history via commit messages

## Method

Word-adjacent regex patterns, mirroring check_no_dates.py: decimal percentage, decimal value with a clinical/technical unit (mg/dl, mmol, ms, bpm, min, kg, km/h, dB, °C, ml/kg/min), "N rows/entries/values/days affected", exact ISO date, month name + year. Lines with citation signal words (doi:, WHO, AWMF, guideline, Leitlinie, et al., …) are exempt — external reference values from medical literature are domain content, not a personal finding.

## Data flow

- **Reads:** `commit`, `message`, `text`, `(file`, `path`, `or`, `stdin)`
- **Writes:** `stdout (report), process exit code`

## Limitations

Heuristic, not exhaustive — unusual phrasing can slip through, or a legitimate technical value (e.g. a threshold constant in the code itself) can false-positive. Checks the message only, not the diff — a finding doesn't necessarily mean the cited value came from real personal data, only that it looks suspicious.

## Usage

```bash
python scripts/utils/check_commit_message_privacy.py .git/COMMIT_EDITMSG
echo "some message" | python scripts/utils/check_commit_message_privacy.py -
```
