## 1. Scoping (must happen first)

- [ ] 1.1 Confirm ProMED access pattern already used in
      `import_outbreak_data.py` (RSS vs. API) can be reused/filtered for
      case-report-style items specifically, not just aggregate case counts
- [ ] 1.2 Decide run cadence (manual trigger vs. cron; monthly is a
      reasonable default given expected low volume of genuinely new
      transmission pathways)
- [ ] 1.3 Draft the LLM extraction prompt (animal, syndrome slug from
      `scripts/analysis/syndromes/`, transmission mechanism, source
      citation) and test it against 3-5 known ProMED case reports,
      including the roe-deer/tularaemia one that triggered this change

## 2. Review queue (build before extraction pipeline)

- [ ] 2.1 Design the local review-queue JSON schema (candidate animal,
      candidate syndrome slug, mechanism, source URL/date, status:
      pending/confirmed/discarded)
- [ ] 2.2 Build a small CLI (`show` / `confirm <n>` / `discard <n>`),
      following the `manage_exposure_history.py` pattern (local file
      under `~/.config/kyoro/`, `backup_before_write`, i18n via `t()`)

## 3. Extraction pipeline

- [ ] 3.1 Fetch new ProMED items since last run (reuse
      `import_outbreak_data.py` fetch logic, do not duplicate)
- [ ] 3.2 Run LLM extraction on new items, write candidates with status
      `pending` into the review queue
- [ ] 3.3 Handle "no matching syndrome slug" case explicitly — surface
      as a separate "needs a new syndrome file" note, not a forced
      approximate match

## 4. Merge on confirmation

- [ ] 4.1 On `confirm <n>`, write the candidate into
      `ANIMAL_SYNDROME_MAP` (`manage_exposure_history.py`) and, where
      relevant, append to the matching syndrome's `endemic_regions`
      list, carrying the source citation
- [ ] 4.2 Confirmed entries must be distinguishable in the merged data
      as "single case report" provenance vs. well-established
      associations (see design.md Decisions)

## 5. Review

- [ ] 5.1 Verify no auto-merge path exists anywhere in the pipeline —
      every reference-data change must go through explicit human
      confirmation
- [ ] 5.2 `python3 tools/gen_docs.py` on all new/changed scripts
