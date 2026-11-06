## Context

The `calendar-ics-importer` proposal (not yet implemented) already worked out a full five-step scrubbing algorithm for doctor/practice names and addresses, but wrote it as if it only mattered for `.ics` fields. In reality the same raw-text risk shows up in at least three more places already identified today: `import_lab_results.py`'s `lab_manual.labor` column (code exists, running now), the planned `import_diagnosis_history.py`'s Leistungserbringer field (plan exists, importer doesn't), and potentially `export_health.py`'s output. `identity_resolver.py` currently hard-codes its two supported kinds (`"device"`, `"person"`) and raises on anything else, so a third call site for pseudonymizing provider names can't use it as-is.

## Goals / Non-Goals

**Goals:**
- One scrubbing function, callable from any importer/exporter, with no per-caller reimplementation of the registry-match / postal-code / title-pattern / safety-net logic.
- Reuse the existing pseudonymization infrastructure (`identity_resolver`) rather than inventing a second pseudonym scheme — a provider pseudonym and a person/device pseudonym should look and behave the same way to anything downstream that just treats them as opaque IDs.
- Never silently drop a provider name without a trace: anything the heuristics can't confidently resolve gets `needs_review=1`, not a silent discard — same no-data-loss principle as every two-stage importer in this project.

**Non-Goals:**
- Not a general NER system. The German-postal-code and professional-title heuristics are documented, best-effort pattern matches, not ML — a bare name with no title and no address (e.g. "mit Michael treffen") is an accepted, documented gap, exactly as already accepted in the `calendar-ics-importer` proposal.
- Not responsible for making `calendar-ics-importer` use this module — that proposal already has its own (currently inline) copy of the same algorithm; swapping it over is a follow-up, not blocked on anything in this change, but also not done here.
- Not a guaranteed `import_lab_results.py` code change — only a task to wire the existing provider-name write-path through this module; if that turns out to be larger than a few lines (e.g. the lab name isn't even isolated as its own token today), it becomes its own follow-up change instead of silently growing this one.
- Not a database migration — `diagnoses` doesn't exist as a populated table yet (the importer that would write to it isn't built), so adding `provider_pseudonym` to its schema is a planning-document edit, not a migration task.

## Decisions

**Standalone module, not a method on an existing class.** `scrub_provider_text()` is a free function in `scripts/modules/provider_scrubbing.py`, not a method on `identity_resolver`'s resolver class or on `Config`. It needs the provider registry (a different local file from `identity.db`'s salt) and calls into `identity_resolver.resolve("provider", ...)` as a dependency, but has no other state — a function is simpler than a class here, and keeps `identity_resolver.py` focused on pseudonym generation/storage, not text parsing. Alternative considered: adding this as a method on the resolver itself — rejected, since the resolver's job (stable salted pseudonyms, persisted lookups) is a different concern from text scrubbing (regex/registry matching on arbitrary strings), and conflating them would make `identity_resolver.py` harder to reason about for its existing two kinds.

**`kind="provider"` extends the existing resolver rather than a parallel pseudonym scheme.** The alternative — giving provider pseudonyms their own prefix/format outside `identity_resolver` — would mean two different pseudonymization code paths to audit for the same privacy property (salted, locally persisted, never reversible without the local salt). One resolver, three kinds, is simpler to verify.

**Registry is a flat list of entries with `match`/`category`/`city`/`country`/`region`, not a nested structure.** Matches the shape already specified in the `calendar-ics-importer` proposal verbatim — no reason to diverge, and keeping the same shape means a single `provider_registry.json` can serve both the (future) calendar importer and every caller of this new module; a user filling this in once covers both.

**`needs_review` is a boolean flag returned to the caller, not something this module acts on.** The module doesn't know whether the caller's target table even has a `needs_review` column (lab_manual and diagnoses may name it differently or not have one at all) — it's the caller's responsibility to decide what to do with a flagged result (set a column, append to a note, route to a review file). Keeps the module's contract small.

## Risks / Trade-offs

- **[Risk]** The postal-code and title-pattern heuristics are tuned against the `calendar-ics-importer` proposal's original examples (calendar event titles/locations), not against actual scanned OCR text from `import_lab_results.py`'s source documents, which has different noise characteristics (column-scrambling, broken umlauts, as already observed today in `sort_scan_batch.py` debugging). → Mitigation: ship the module with the algorithm unchanged from its original spec, but explicitly flag in `@limits` that OCR'd input may need the registry (exact match) to carry more weight than the pattern heuristics, since OCR noise degrades title-pattern matching faster than it degrades a known-string lookup. Re-tune only if real false-negatives show up once `import_lab_results.py` actually calls it.
- **[Risk]** Extending `identity_resolver`'s `kind` set is a change to a shared, security-relevant module used by every existing device/person pseudonymization call site. → Mitigation: purely additive branch (`elif kind == "provider":`), no change to the existing `"device"`/`"person"` code paths; the delta spec for `identifier-pseudonymization` should state this explicitly so a reviewer can see the existing behavior is untouched.
- **[Trade-off]** Keeping `import_lab_results.py`'s actual wiring as a "task, not a guaranteed deliverable" in this change means the module could ship without any real caller yet. → Accepted: the module is still useful in isolation (it's what the diagnosis-history plan update depends on conceptually), and forcing the `import_lab_results.py` change into this one risks scope creep into a script that's already working in production for the user's current batch.

## Migration Plan

Not applicable — new module, new local-only config file, additive resolver branch. No existing data to migrate (the registry starts empty/template-only; nothing currently stored needs re-processing since no provider names have been pseudonymized by anything yet).

## Open Questions

- Should `scrub_provider_text()` take the registry as a parameter (caller loads it once) or load it itself on each call (simpler call sites, repeated file I/O)? Leaning toward "load once, pass in" for anything processing many rows (e.g. a future diagnosis-history importer iterating hundreds of lines), but this is small enough to decide during implementation rather than block the proposal on it.
- Exact shape of the `import_lab_results.py` task: is the lab company name today already isolated as its own variable before being written to `lab_manual.labor`, or is it embedded in a larger OCR text blob that would need its own extraction step first? Needs a short look at the current importer code before scoping that task precisely — noted in tasks.md as a first sub-step (investigate) rather than assumed.
