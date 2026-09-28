## Why

The `add-guided-anamnesis-interview` change writes extracted findings into a new, isolated `anamnese_findings` table — but this project already has four mature, purpose-built local JSON stores for exactly these categories of data (`family_history.json`, `travel_history.json`, `exposure_history.json`, `known_risk_exposures.json`), each with its own interactive management script, and each already read by real downstream consumers (`export_arzt_komplett.py`, `analyse_outbreak_exposure.py`, `analyse_pathogen_exposure.py`). Without a bridge, a finding surfaced by the interview would never reach a doctor-letter export or an outbreak-exposure analysis unless a human manually re-types it into the right file after the fact — silently defeating the interview tool's actual purpose. This change adds that bridge: a human-confirmed promotion path from raw interview captures into the existing canonical stores, reusing their existing schema/validation logic rather than duplicating it.

## What Changes

- New non-interactive "append a pre-built entry" function added to each of the four existing management scripts (`manage_family_history.py`, `manage_travel_history.py`, `manage_exposure_history.py`, `manage_known_risk_exposures.py`), alongside their existing interactive `cmd_add`-style functions — reusing each script's own `load()`/`save()` I/O and field validation (e.g. `RELATIVES`/`SIDES`/`STATUSES` in family history, the `syndrome_slug` constraint in known-risk-exposures), not reimplementing it elsewhere.
- New promotion mode on the anamnesis-interview review/export helper (`--promote`, extends the helper from `add-guided-anamnesis-interview` task 4.1): walks a session's `anamnese_findings` rows, proposes for each a target store (see mapping below) and a pre-filled entry, and requires an explicit per-finding confirmation before writing — no silent/automatic promotion, matching the "human review gate" principle the interview itself already establishes.
- Track → target-store mapping:
  - exposure/travel history → `travel_history.json`
  - animal contact → `exposure_history.json` (`animal_contacts[]`)
  - occupational history & exposures → `exposure_history.json` (`occupational_exposures[]`)
  - family history → `family_history.json`
  - leisure & hobbies → `known_risk_exposures.json` (its documented scope already explicitly names "Hobbys"/residence-type/occupation as chronic risk categories; a hobby finding is promoted here when it maps to a pathogen-relevant `syndrome_slug` from `analyse_outbreak_exposure.py`'s known slug set — that is the same associative-relevance judgment the interview's system prompt already makes, so most flagged hobby findings should have a plausible candidate slug)
- A finding MAY be offered for promotion into more than one store when applicable (e.g. a chronic occupational exposure can go into both `exposure_history.json`'s `occupational_exposures[]` as the historical record and `known_risk_exposures.json` as a risk-weighting entry, if it represents an ongoing/repeated exposure rather than a one-off event) — the promotion step offers each applicable target independently, the human confirms each separately.
- Findings with no applicable target (e.g. a hobby fact with no plausible pathogen-relevance, or anything from a future track this mapping doesn't cover) remain in `anamnese_findings` only and continue to reach a doctor's letter draft via the existing plain-Markdown export (task 4.1) — this is not a gap to fix, it mirrors how most doctor's-letter content is already hand-assembled without living in a structured config first.
- **BREAKING**: none — purely additive; existing interactive `cmd_add` flows in all four scripts are untouched.

## Capabilities

### New Capabilities
- `anamnese-findings-promotion`: a human-confirmed bridge that promotes selected `anamnese_findings` rows (from the guided anamnesis interview) into this project's existing per-domain structured history stores (`family_history.json`, `travel_history.json`, `exposure_history.json`, `known_risk_exposures.json`), so interview output actually reaches the analysis/export pipelines that already consume those stores.

### Modified Capabilities
(none — no existing spec's requirements change; this only adds new non-interactive entry points to scripts that aren't yet governed by a formal spec)

## Impact

- Depended on `add-guided-anamnesis-interview` for the `anamnese_findings` table this change promotes rows out of — that table exists now, implementation here proceeded once it did. Task 4.3 still needs a real interview session from that change to run its final dogfooding check against (see `tasks.md`).
- Modified files: `scripts/utils/manage/personal/manage_family_history.py`, `manage_travel_history.py`, `manage_exposure_history.py`, `manage_known_risk_exposures.py` (each gets one new non-interactive append function; existing interactive commands unchanged).
- Modified file: the anamnesis-interview review/export helper from `add-guided-anamnesis-interview` task 4.1 (new `--promote` mode).
- No impact on importers, compute scripts, or the schema of `health.db`/`medicine.db`.
- Downstream beneficiaries (unchanged themselves, now actually reachable from interview output): `export_arzt_komplett.py`, `analyse_outbreak_exposure.py`, `analyse_pathogen_exposure.py`.
