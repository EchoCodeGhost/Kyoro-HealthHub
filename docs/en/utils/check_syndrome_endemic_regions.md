# check_syndrome_endemic_regions — Haelt scripts/analysis/syndromes/*.json in Sync mit den echten Ausbruchsdaten

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/utils/check_syndrome_endemic_regions.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Automatically checks whether each syndrome JSON file's (scripts/analysis/syndromes/*.json) `endemic_regions` list matches the real, structured endemic/FSME reference data in import_outbreak_data.py (ENDEMIC_REFERENCE, FSME_RISIKOKREISE_BUNDESWEIT) -- without this script, an expansion of the outbreak data (e.g. a new federal state with FSME risk districts, a new country in ENDEMIC_REFERENCE) does not automatically surface in the corresponding syndrome files, which keep showing the old, shorter list. This exact pattern was already found manually (fsme.json was missing several real federal states, dengue/chikungunya/zika.json were missing Germany entirely even though districts with tiger mosquito vector presence were already in ENDEMIC_REFERENCE) -- this script exists so that doesn't happen a second time only by accident.

## Relevance

Closes exactly the gap that led to the manual audit work on the syndrome files -- without this check, the sync between outbreak data and syndrome files relies purely on memory.

## Method

Two checks: (1) FSME special case -- every federal-state key in FSME_RISIKOKREISE_BUNDESWEIT must appear as an entry in fsme.json's endemic_regions. (2) General -- for every syndrome_slug in ENDEMIC_REFERENCE (tiger mosquito entries included, since they're appended there), the set of countries present is checked against the identically-named JSON file's endemic_regions list (only if that file exists -- not every ENDEMIC_REFERENCE slug necessarily has its own syndrome file). Exact string comparison, no fuzzy matching -- matches the exact comparison logic in analyse_postinfectious_diagnose.py (`endemisch & visited_regions`, a set intersection), so a check that passes here actually means a working "Reise-Boost". Also an informational (non-failing) lint hint for unusually long endemic_regions entries (>40 chars), which typically bundle several names into one string that can then never exactly match (the same bug class found several times already) -- UNLESS the entry is an exact copy of a real travel_history entry (then it's intentionally personalized, not a bug).

## Data flow

- **Reads:** `scripts/analysis/syndromes/*.json`, `ENDEMIC_REFERENCE`, `and`, `FSME_RISIKOKREISE_BUNDESWEIT`, `(import_outbreak_data.py)`, `~/.config/kyoro/health_config.json`, `(travel_history`, `fuer`, `den`, `Lint-Hinweis)`
- **Writes:**

  ```
  Keine (reiner Pruefbericht, kein Auto-Fix -- die Syndrom-Dateien
  enthalten handgeschriebene klinische Texte, die ein Skript
  nicht sicher automatisch bearbeiten sollte)
  ```

## Limitations

Only covers `country` level, not district/state precision for tiger-mosquito/endemic entries (only FSME has its own federal- state structure in FSME_RISIKOKREISE_BUNDESWEIT) -- a missing state-level entry for dengue/chikungunya/zika will therefore NOT be caught automatically, only a completely missing country. The long-entry lint hint is a heuristic (character length), not semantic understanding -- can both miss real bugs (a short but still-bundled string) and produce false positives (a long but legitimate single name).

## Usage

```bash
python3 scripts/utils/check_syndrome_endemic_regions.py
python3 scripts/utils/check_syndrome_endemic_regions.py --quiet
```
