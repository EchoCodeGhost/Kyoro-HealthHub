## 1. Registry and resolver foundation

- [x] 1.1 Design the `provider_registry.json` entry schema (`match` list, `category`, `city`, `country`, optional `region`) exactly as specified in `calendar-ics-importer`'s proposal — no new fields invented here
- [x] 1.2 Add `templates/provider_registry.example.json` with dummy entries covering: a registry match, a German-postal-code-only case (no registry entry), and a title-pattern-only case (no registry entry) — one example per heuristic tier
- [x] 1.3 Extend `scripts/modules/identity_resolver.py`: add `kind="provider"` to `_generate_pseudonym()` and `resolve()`, purely additive, existing `"device"`/`"person"` branches untouched
- [x] 1.4 Verify `kind` other than `"device"`/`"person"`/`"provider"` still raises `ValueError` (regression check for the existing behavior)

## 2. `provider_scrubbing.py` module

- [x] 2.1 Create `scripts/modules/provider_scrubbing.py` with SPDX header and structured docstring (`@tier infrastructure`, since this is shared plumbing, not an importer/analysis script itself)
- [x] 2.2 Implement registry loading (from `~/.config/kyoro/provider_registry.json`, via `health_config.Config` or a direct path — decide during implementation per design.md's open question on load-once-vs-per-call) — resolved: direct path, optional pre-loaded registry param for bulk callers
- [x] 2.3 Implement step 1: registry exact-match (case-insensitive substring against `match` lists) → strip, set `provider_category`/`provider_city`/`provider_country`/`provider_region`, resolve `provider_pseudonym` via `identity_resolver.resolve("provider", ...)`
- [x] 2.4 Implement step 2: German postal-code pattern (`\d{5}\s+[A-ZÄÖÜ][a-zäöüß]+`) → reduce to city, set `provider_country="DE"` (extended to also strip a preceding street+house-number, per spec's "Straße/Hausnummer entfernen" — caught by a real test failure, not assumed)
- [x] 2.5 Implement step 3: professional-title-plus-name pattern (`Dr.`, `Dr. med.`, `Prof.`, `Prof. Dr.`, `Facharzt/Fachärztin für ...`, `Zahnarzt/Zahnärztin`, etc. + 1-2 capitalized words) → strip, set `needs_review=True` unless already resolved by step 1
- [x] 2.6 Implement step 4: safety-net check (street-suffix words, leftover 5-digit number, multiple consecutive capitalized words) → `needs_review=True`, text retained, never discarded
- [x] 2.7 Define `ProviderScrubResult` (dataclass) with `clean_text`, `provider_category`, `provider_city`, `provider_country`, `provider_region`, `provider_pseudonym`, `needs_review`
- [x] 2.8 Write unit tests covering each of the 4 scenarios in `specs/provider-text-scrubbing/spec.md` plus the two "bare name" and "unknown kind rejected" edge cases — `tests/test_provider_scrubbing.py` (8 tests) + extended `tests/test_identity_resolver.py` with provider-kind coverage (15 tests total), all passing
- [x] 2.9 Document the `@limits`: no NER, bare names without title/address are an accepted gap, heuristics tuned against calendar-style text not yet validated against OCR noise (per design.md risk)
- [x] 2.10 `python3 tools/gen_docs.py scripts/modules/provider_scrubbing.py` → OK
- [x] 2.11 `python3 scripts/utils/check_source_privacy.py` → exit 0

## 3. Diagnosis-history plan update (planning document only)

- [x] 3.1 Update `intern/plan_import_diagnosis_history_2026-10.md`: change the Leistungserbringer handling from "wird nicht in diagnoses übernommen" to "pseudonymisiert via `scrub_provider_text()`, gespeichert als neue Spalte `provider_pseudonym`"
- [x] 3.2 Add the `provider_pseudonym TEXT` column to the plan's `diagnoses` CREATE TABLE snippet and to the Spalten-Belegung section
- [x] 3.3 Update the plan's docstring (`@writes` section) and Mistral checklist to reflect the new column and the `provider_scrubbing` dependency

## 4. `import_lab_results.py` investigation (task only, not a guaranteed code change)

- [x] 4.1 Read the current `import_lab_results.py` code path that writes to `lab_manual.labor` — determine whether the lab company name is already an isolated variable or embedded in a larger text blob. Finding: isolated the whole time — `labor` is either the explicit `--labor` CLI value or `pdf_path.stem` (filename), never extracted from OCR text; computed once in `_ocr_pdf()` and passed down to both the regex and VLM row-building paths
- [x] 4.2 If isolated: wire it through `scrub_provider_text()` before writing, verify against a real sample file, re-run `check_source_privacy.py` and `gen_docs.py`. Done: single call site in `_ocr_pdf()` right after `labor = labor or pdf_path.stem`; verified end-to-end with a real dry-run import against a sorted `laborbefund` file (42 rows, no crash) and separately confirmed the pseudonym actually resolves once a registry entry matches (temporary test registry, cleaned up after); docstring `@limits` updated in both languages
- [x] 4.3 If not isolated: n/a, was isolated

## 5. Export-path audit (research only)

- [x] 5.1 Grep `scripts/export_health.py` and `scripts/exporters/profiles/*.json` for any query selecting a column that could carry a raw provider name (e.g. `labor`, a future `provider_pseudonym`-adjacent raw column, free-text notes fields)
- [x] 5.2 Findings: 7 clinical-specialty profiles (`immunology`, `rheumatology`, `infectiology`, `metabolic`, `functional_medicine`, `general_practitioner`, `oncology`) select `labor AS lab` from `lab_all` — intended for handing data to a treating doctor, where the raw lab name is normally useful context, not a leak. `research.json` (the profile meant for `--person all` cohort export) only queries `health.db` wearable tables and never touches `lab_manual`/`lab_all`, so there is no active leak into a cohort/research export today. `export_health.py` already has a general mechanism for exactly this class of problem for a *different* sensitive column type — `_redact_location_columns()`/`_get_allowed_location_level()`/the `exports_allow` config — but no equivalent exists yet for a `lab`/provider column. **Follow-up, not implemented here**: if a future cohort/research-style profile is ever extended to pull from `lab_all`/`lab_manual`/`diagnoses`, it needs the same kind of per-profile allow-level mechanism for the `labor`/`provider_pseudonym` columns that location columns already have — tracked as a new task/change at that point, not now, since no current profile needs it.

## 6. Follow-up note (not implemented by this change)

- [x] 6.1 Record as an explicit follow-up: once `provider_scrubbing.py` exists, `calendar-ics-importer`'s proposal/design should be updated to call it instead of keeping its own inline copy of the same algorithm — out of scope here, just not forgotten. (`provider_scrubbing.py` now exists; `calendar-ics-importer`'s own proposal/design still has its own inline copy — this follow-up remains open for a future session.)
