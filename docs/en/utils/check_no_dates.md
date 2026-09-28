# check_no_dates — Enforces the no-embedded-dates/versions convention (CONTRIBUTING.md)

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/utils/check_no_dates.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Checks .py and .md files for hardcoded date/version markers that record *when* something changed or *which* revision introduced it (a status word immediately before a date, like "Fixed <date>" or "Ordered (<date>)", "As of <date>", a bare "Version X.Y" revision marker, a filename with a date suffix before the extension) — exactly the patterns docs/CONTRIBUTING.md § "Versioning and changelogs" forbids, because git history already carries that information and a copy baked into file content goes stale without anyone noticing.

## Relevance

Technically enforces the date/version convention from CONTRIBUTING.md, prevents silently-staling changelog remnants in file content

## Method

Word-adjacent regex patterns instead of a blanket date scan: a bare "\d{4}-\d{2}-\d{2}" pattern would match every legitimate data field (clinical.events, `--from 2024-01-01` examples in @usage blocks, "birthdate" in the config template) — thousands of false positives. Instead: (1) a status word (Fixed/Resolved/Ordered/Bestellt/Behoben/ Found/Repaired/Dead/Benchmarked/Flagged/Befund/Finding/Korrigiert/ Corrected/Ergänzt/…) before or after a date (full date OR month-only YYYY-MM), case-insensitive, with up to 4 filler words allowed in between — catches "Fixed 2026-07-18" as well as "Found in production data 2026-07-20" or "2026-07-22 live verified"; (2) "As of"/"Stand:"/"seit"/"since" immediately before a date; (3) a filename with a date suffix before the extension; (4) a bare "Version X.Y" revision marker; (5) "commit `<hash>`" cited as narrative prose (not "git commit -m", since no hex string follows there); (6) a record count directly before a quantity noun (rows/Zeilen/Messungen/records/…) COMBINED WITH a date on the same line — both sub-patterns must match, so CSV example rows or ISO timestamps with milliseconds (".000") don't trigger it. Lines containing citation signal words (doi:, AWMF, RKI, WHO, guideline, Leitlinie, …) are exempt from category 4, since CONTRIBUTING.md explicitly allows citations (guideline versions, publication years, DOIs) as domain content, not project changelog. "ab"/"bis"/"until" immediately before a date is deliberately NOT checked — too many legitimate domain facts (device data available from date X, a data source covering a period up to date Y) would have false-positived. Scans git-tracked files (git ls-files) — private/ gitignored directories (intern/, data/, …) fall out automatically. Exit code: 0 = clean, 1 = findings found.

## Data flow

- **Reads:** `all`, `git-tracked`, `.py/.md`, `files`, `in`, `the`, `scanned`, `directory`
- **Writes:** `stdout (report and JSON output)`

## Limitations

Word list (status words, citation signal words, quantity nouns) is not exhaustive — unusual phrasings can slip through. Line-based: a status word and a date split across two comment/docstring lines (e.g. "...(N rows, back to # YYYY-MM-DD)") are NOT detected. Category 6 (count+date) requires an explicit quantity noun right after the number — a record-count fact with no such noun on the same line as the date (e.g. "measured: N rows across several device IDs" with no date on that line) goes undetected. Can rarely false-positive (e.g. a status word and an unrelated date field coincidentally on the same line with no causal link). Does not check whether a found date is actually correct/stale — only whether one of the patterns occurs at all.

## Usage

```bash
python scripts/utils/check_no_dates.py
python scripts/utils/check_no_dates.py --dir docs
python scripts/utils/check_no_dates.py --json
```
