## Context

No importer in this repo currently handles free-text content with this level of third-party-identifying risk. Existing free-text columns (`symptoms.value_text`, `self_care.notes`, `user_context` notes) are allowed to stay as local-only plain text, on the reasoning that health.db never leaves the machine. The user explicitly overrides that default for calendar data specifically: doctor names, practice names, and complete addresses must not be persisted at all, even locally — because calendar entries are judged the most likely place in this pipeline for identifying third-party data (a named doctor, a named practice, a specific street address) to appear, and because this data will later feed the `health-dossier-query` change's optional `--llm` path, where a leak would mean sending a real doctor's name to a remote provider.

This repo already has exactly one established pattern for turning a real-world identifier into something safe to store: `scripts/modules/identity_resolver.py`, documented in `openspec/specs/identifier-pseudonymization/spec.md` — a single resolver module, deterministic SHA-256 pseudonyms, mapping stored exclusively in a local `identity.db`, never in health.db or the repo. This change reuses that pattern rather than inventing a parallel one.

## Goals / Non-Goals

**Goals:**
- Import `.ics` calendar data (single or multiple files, one-time or recurring events) into a queryable table, source-agnostic between Apple/Google/any RFC 5545 export.
- Guarantee that no complete address (street + house number) and no doctor/practice name is ever written to `health.db`, not even locally — only a generic category+city+country label and an opaque pseudonym.
- Reuse the existing `identity_resolver` pseudonymization mechanism rather than building a second one.
- Make non-detection visible (`needs_review`) rather than silently passing unscrubbed text through.
- Produce a table shape (`date` + `person` columns) that slots into the generic table-discovery design of the separately planned `health-dossier-query` change without special-casing.

**Non-Goals:**
- No true NER/ML-based name or address detection — this is explicitly out of scope; the scrubbing is registry-match plus a postal-code heuristic, with a documented detection gap for anything neither registered nor postal-code-shaped.
- No live calendar sync (CalDAV, Google Calendar API) — file import only.
- No update-in-place for a changed event with the same UID/start (`--update` adds new occurrences; it does not detect or apply content changes to an already-imported occurrence — see Risks).
- No implementation of the `health-dossier-query` `--llm` allow-list itself — this change only establishes the data contract (which columns are safe) that the other change must honor when it's implemented.

## Decisions

**1. Dedicated table, not EAV.**
A calendar occurrence has several attributes per data point (title, location, description, all-day flag, provider fields) — the same reasoning the project already applies to `self_care`/`symptoms` over `measurements`. `calendar_events` is a standalone table.

**2. Expand recurring events into concrete rows at import time, not store the RRULE.**
Storing the raw recurrence rule would push "what happened on day X" logic into every consumer (including the future dossier). Expanding once at import time via `recurring_ical_events.of(calendar).between(horizon_start, horizon_end)` means every consumer — including a plain `SELECT ... WHERE date = ...` — just works. Horizon constants (`RECURRENCE_PAST_DAYS=3650`, `RECURRENCE_FUTURE_DAYS=400`) bound the expansion so an unbounded `FREQ=WEEKLY` rule with no `UNTIL`/`COUNT` can't produce unbounded rows; the window itself is the safeguard, no separate occurrence cap needed.

**3. Scrubbing is mandatory and happens before any insert — not a post-processing pass, not an opt-in flag.**
Doing this after the fact (e.g. a periodic cleanup job scrubbing already-stored rows) would mean there's a window where raw data sits in health.db. The scrubbing function runs inline inside `import_file()`, before the `INSERT`, so unscrubbed text is never written to disk in the first place.

**4. Scrubbing mechanism: local registry (match → category/city/country) + existing `identity_resolver` for the pseudonym, not a new pseudonymization scheme.**
`identity_resolver.resolve(kind, real_value)` already provides deterministic, locally-stored-only pseudonyms (`openspec/specs/identifier-pseudonymization/spec.md`). This change adds a `kind="provider"` usage of that same function (extending `identity_resolver.py` with that kind if it isn't already generic over arbitrary kinds) rather than building a second resolver. The registry (`provider_registry.json`) itself is a new, separate, local-only JSON file (analogous to `device_registry` in `health_config.json`) because it carries metadata (`category`, `city`, `country`) that `identity_resolver` doesn't model — `identity_resolver` only ever returns an opaque pseudonym string, never metadata. `country` (ISO 3166-1 alpha-2) is a required field on every registry entry: a bare city name is not globally unique (the same place name exists in more than one country), so dropping country would reintroduce exactly the kind of ambiguity the city-only reduction (decision 5) is trying to avoid on the privacy side — country is the one piece of location context kept at full precision because, unlike a postal code, it doesn't narrow things down within a city.

City names aren't even unique *within* one country (e.g. Germany has more than one place called Neustadt). For registry entries this ambiguity doesn't actually matter in practice — the user already knows which real-world provider a given registry entry/pseudonym refers to (she wrote the `match` strings herself), and `provider_pseudonym` resolves it precisely regardless of what the display label says. The category/city/country label is a coarse, LLM-safe hint, not the mechanism of identification. So: add an **optional** `region` field to registry entries (e.g. a German `Regierungsbezirk`/state name like "Oberbayern") for the cases where the user wants that extra disambiguation at a glance — surfaced as `provider_region` (nullable) alongside `provider_category`/`provider_city`/`provider_country`. It is never auto-derived (no postal-code-to-region lookup table is added for this) — only ever set when a registry entry explicitly provides it. The postal-code heuristic fallback path (unregistered addresses, decision 5) does not get a region at all; building a full PLZ→Regierungsbezirk mapping just for the unregistered-fallback case isn't worth the added infrastructure for a path that's already the less-precise, flagged-as-heuristic one.

**5. Two-tier address handling: registry match (exact) vs. postal-code heuristic (fallback) vs. safety-net flag (last resort).**
- Registry match handles known/recurring doctors, practices, and the user's own home/work addresses (which also need reducing, not just third parties — the user's own exact location is equally sensitive).
- Unregistered addresses get a best-effort regex reduction to **city-name-only** (German `\d{5}\s+<Ort>` pattern is used to *locate* the city, but the postal code itself is then also discarded, not just the street/house number before it) — deliberately coarser than "PLZ + city": a postal code narrows a large city down to a specific district (Munich alone spans dozens of distinct postal codes), so dropping it is strictly more private than keeping it, at the cost of losing within-city precision the design doesn't need anyway. This is explicitly a heuristic, not reliable address parsing — documented as such, not oversold.
- Anything that still looks address-/name-like after both passes (street-type suffixes, a leftover postal code, runs of capitalized words) sets `needs_review = 1` and the row is still imported. The alternative — dropping the row or blocking the import — would lose legitimate calendar data over a false positive; flagging for manual review preserves the data while surfacing the uncertainty.
- No row is ever silently imported with unflagged, unscrubbed raw address/name text that the heuristics could have caught — the three tiers together are the whole scrubbing contract, not independent optional steps.

**6. Title-pattern name stripping: also catches an unregistered doctor name with no address at all.**
The gap in decision 5's address-only handling: "Termin bei Dr. Müller" has no address and no postal code — the postal-code heuristic never fires, and a single capitalized word after a title doesn't trigger the "multiple capitalized words" safety net either (that net is tuned for *address*-shaped leftovers, not bare names), so a titled name with nothing else could otherwise slip through unredacted. This was an explicit gap called out during design review, and the user asked for it to be closed, specifically for the no-address case. German professional/academic titles are a small, fixed vocabulary — not NER, a short regex alternation: `Dr\.|Dr\. med\.|Prof\.|Prof\. Dr\.|Facharzt(?:in)?\s+für\s+\w+|Zahnarzt(?:in)?`, etc. When such a title is immediately followed by one or two capitalized words, that is treated as a positive name match, independent of whether any address or postal code is also present:
- If the matched title+name also matches a registry entry, the registry path (decision 4) already handles it — registry matching runs first, no conflict.
- If it is **not** in the registry: the entire matched "title + name" substring is stripped from the text (removed, same as a registry match — not merely flagged), and `needs_review = 1` is set, since there is no category/city/country to offer for a doctor who isn't registered, so the row still needs a human decision (add to registry, or leave as a generic flagged entry).
This closes the specific "titled name, no address" gap, but not every gap: a bare name with **neither** a title **nor** an address (e.g. "mit Michael treffen") still isn't reliably distinguishable from an ordinary non-medical entry without actual NER, which stays out of scope (Non-Goals, see also the updated Risk below). Documented plainly, not glossed over.

**7. `--update` is file-level reimport, not incremental.**
Like other small reference-style imports in this repo, a full `.ics` file is cheap to reparse completely; `INSERT OR IGNORE` against the `(uid, occurrence_start, person)` primary key keeps re-imports idempotent. This deliberately does not detect or apply a content change to an already-stored occurrence (see Risks) — building real change detection would require tracking `SEQUENCE`/`LAST-MODIFIED` per UID, judged not worth the complexity for a first version.

## Risks / Trade-offs

- **[Risk]** A doctor name with **neither** a title (Dr./Prof./Facharzt für .../Zahnarzt etc.) **nor** an address/postal code (e.g. a calendar entry that just says "Termin mit Michael") is caught by neither decision 5 nor decision 6 → **Mitigation:** this is an accepted, documented detection gap (Non-Goals) — no NER model is being added to this pipeline; a bare first name with no other cue is indistinguishable from an ordinary personal appointment without one. The user is expected to grow the registry over time, same as `device_registry`, for recurring cases. This is stated plainly in the importer's `@limits` docstring, not hidden. (The titled-name case, e.g. "Dr. Müller" with no address, is now covered by decision 6 and is no longer part of this gap.)
- **[Risk]** A changed event (same UID+start, edited title/description) is not updated on re-import → **Mitigation:** documented limitation; acceptable because the primary use case (dossier correlation by date) only needs the occurrence's date/provider-category, which rarely changes after the fact; a future change can add `SEQUENCE`-based update detection if this becomes a real problem.
- **[Risk]** `needs_review` rows still contain the scrubbing-surviving text in `title`/`location_text`/`description` locally — if the dossier's future `--llm` path forgot to exclude them, that text could reach an LLM → **Mitigation:** decision recorded as a hard contract in the proposal's "What Changes" section and in this change's spec, to be enforced in the `health-dossier-query` change's own implementation/tasks when that proceeds.
- **[Risk]** `RECURRENCE_FUTURE_DAYS=400`/`RECURRENCE_PAST_DAYS=3650` are somewhat arbitrary → **Mitigation:** both are named module constants, trivially adjustable without touching parsing logic; not a schema or API commitment.

## Migration Plan

Not applicable — new table, no existing data affected. Rollback is removing the table/script; no other code depends on `calendar_events` yet.

## Open Questions

- Exact wording/placeholder for scrubbed text (empty string vs. a neutral placeholder like `"[Termin]"`) — implementation detail, decide while writing `scrub_text()`.
- Whether `identity_resolver.py` already accepts an arbitrary `kind` string or needs an explicit allow-list update to add `"provider"` — check during implementation.
