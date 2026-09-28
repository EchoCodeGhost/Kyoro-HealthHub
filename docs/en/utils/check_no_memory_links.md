# check_no_memory_links — Enforces that private memory-link syntax never reaches

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/utils/check_no_memory_links.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Checks all .py and .md files for `[[...]]` wikilink syntax — the reference format of the private, project-external memory system (not part of this repo, never committed). Such a link in a publicly visible file is always a copy-paste artifact: the target node does not exist for readers of the repo, and the pattern only appears when private context was carried into a public document unfiltered.

## Relevance

Prevents private memory references (note names pointing at a project-external, never-committed system) from leaking into a public repo — a recurring failure mode in AI-assisted documentation work, where private chat context and public file content can bleed into each other.

## Method

Regex `\[\[[a-zA-Z_][a-zA-Z0-9_]*\]\]` over git-tracked files (git ls-files) — restricted to identifier-like content (letter/ underscore first, then alphanumeric), because a naive `\[\[[^\[\]]+\]\]` blind scan false-positives on real Python code: fancy indexing like `arr[0][[0, -1]]` or `df.spines[['top','right']]` looks syntactically like a wikilink but is double square-bracket indexing. Real memory note names in this project are consistently snake_case (e.g. `project_mission`, `clinic_multi_patient`) and match the tight pattern; `[0, -1]` or `'top','right'` do not. Private/gitignored directories (intern/, data/, …) are never included via git ls-files in the first place. Exit code: 0 = clean, 1 = findings found.

## Data flow

- **Reads:** `all`, `git-tracked`, `.py/.md`, `files`, `in`, `the`, `scanned`, `directory`
- **Writes:** `stdout (report and JSON output)`

## Limitations

Only detects the `[[...]]` syntax itself, not other forms of unfiltered private context (e.g. personal-profession statements in prose like "The user professionally is ...") — no reliable, low-false-positive rule exists for that; it remains a review task.

## Usage

```bash
python scripts/utils/check_no_memory_links.py
python scripts/utils/check_no_memory_links.py --dir docs
python scripts/utils/check_no_memory_links.py --json
```
