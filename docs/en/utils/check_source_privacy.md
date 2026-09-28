# check_source_privacy — Source-Code- und Doku-Privacy-Compliance-Check für Kyoro-HealthHub

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/utils/check_source_privacy.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Checks Python source files AND doc/config files (.md, .json) for privacy compliance violations. Identifies: forbidden identifiers from privacy_check.forbidden_identifiers (all file types), exact personal data-volume statistics about actual usage (all file types — the triggering find was an archived OpenSpec tasks.md, not a script), hardcoded person IDs (string literals 'self' instead of OWN_PERSON_ID), hardcoded IANA timezone strings, fallback dicts with entity IDs (.py only — these categories are code conventions, not documentation errors).

## Relevance

Provides verification functions for data quality and privacy, essential for data integrity

## Method

Loads forbidden identifiers from ~/.config/kyoro/health_config.json → privacy_check.forbidden_identifiers. Scans the whole repo by default (.py, .md, .json) — more precisely, all git-tracked files with these extensions (git ls-files), so gitignored/private directories (intern/, data/, imports/, analyses/, exports/, logs/, medicine/, medizin/) fall out automatically without needing to be maintained here a second time. Static checks: hardcoded person IDs in SQL and assignments, IANA timezone strings (Africa/, America/, etc.), fallback dicts with entity IDs, hardcoded config paths — all four categories are .py-only, since they are code antipatterns and would false-positive on doc examples (e.g. SQL snippets showing person='self' or an IANA timezone as the documented schema default). The identifier check (forbidden_identifiers) runs on all file types — this is the mechanism that catches personal data embedded in Markdown/JSON. Supports recursive directory scanning, JSON output and strict mode. Skips own file (self-exclude) and specific directories. Exit code: 0 = clean, 1 = findings found.

## Data flow

- **Reads:** `~/.config/kyoro/health_config.json`, `alle`, `.py/.md/.json-Dateien`, `im`, `gescannten`, `Verzeichnis`
- **Writes:** `stdout (Berichte und JSON-Ausgabe)`

## Limitations

May produce false positives (e.g., in t() calls or comments). Docstrings and comments (.py) are not scanned. Free-text statistics (e.g. "six ECGs with AFib") aren't mechanically detectable — only via privacy_check.forbidden_identifiers or human review.

## Usage

```bash
python scripts/utils/check_source_privacy.py
python scripts/utils/check_source_privacy.py --dir /path/to/scan
python scripts/utils/check_source_privacy.py --json
python scripts/utils/check_source_privacy.py --strict
python scripts/utils/check_source_privacy.py --high-only
python scripts/utils/check_source_privacy.py --ext .py .md .json
# --dir: Verzeichnis zum Scannen angeben (Standard: Repo-Root)
# --json: Ausgabe als JSON
# --strict: Wertet auch low-confidence Findings als Fehler
# --high-only: Nur high-confidence Findings ausgeben
# --ext: Zu scannende Dateiendungen (Standard: .py .md .json)
```
