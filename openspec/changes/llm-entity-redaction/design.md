## Context

`modules/llm.py::call_llm()` is already the single choke point for every remote LLM call in this repo — dozens of `analyse_*.py` scripts, `health_query.py`, `anamnese_interview.py`, `medical/medical_query.py`, and more all go through it, never calling a provider directly (and where one did, `location-privacy`'s own spec already calls that a convention violation). It already runs exactly one filter before sending to a remote provider: `location_store.filter_prompt_text()`, gated on `is_remote = not provider.is_local`. That filter only targets coordinates and a configured list of place names — it has no concept of a person's name. Meanwhile, several tables already hold arbitrary free text with no scrubbing at write time (`symptoms.value_text`, `self_care.notes`, `user_context` notes) — unlike the calendar importer (separate change), which scrubs doctor/practice names and addresses before they're even written to disk, these tables' content reaches `call_llm()` completely unfiltered today.

This change adds the missing filter at the same choke point, for the same reason the location filter exists there: it is the one place that reliably sees every outbound prompt, regardless of which of the dozens of calling scripts produced it.

## Goals / Non-Goals

**Goals:**
- Reduce (not claim to eliminate) the risk of a person's name reaching a remote LLM provider, for every existing and future caller of `call_llm()`, without editing each caller.
- Reuse existing infrastructure: the `is_remote` gate and `(text, count)` filter shape from the location filter, the `identity_resolver` pseudonym mechanism, and (when present) the calendar importer's `provider_registry.json` as a free, exact-match first pass.
- Keep the NER model and its inference entirely local — no entity text is ever sent to an external NER service to detect entities in text that's about to be protected from being sent externally; that would defeat the purpose.
- Make the filter's own limitations visible (count logged, no raw text logged) and documented, not silently assumed to be complete.

**Non-Goals:**
- Not a replacement for the calendar importer's import-time scrubbing — that remains a separate, independent layer (data never written unscrubbed), while this change is an outbound layer (data already stored, filtered only at the moment it would leave the machine).
- Not a guarantee of zero leakage — NER has a real, non-zero false-negative rate (and a false-positive rate, which costs coherence, not privacy). This is a defense-in-depth risk reduction, not a certified anonymization.
- Not applied to images — image metadata stripping is already handled separately (`_strip_image_metadata`); this change is text-only.
- Not a per-caller allow-list with graduated precision levels like the location filter's `none`/`region`/raster/`token` — a person's name doesn't have a meaningful "coarser" version the way a coordinate does. The control surface here is a single on/off switch (`llm.redact_entities`), not a precision scale.
- Does not change `health.db`/`medicine.db` content — purely a transient, outbound-only transformation of the text passed to `call_llm()`.

## Decisions

**1. Hook point: inside `call_llm()`, alongside the existing location filter, same `is_remote` gate.**
This is the only place guaranteed to see every outbound prompt/system text regardless of caller — exactly the same reasoning that put the location filter there. Adding a second, independent filter call at the same point (rather than building a new, separate choke point) keeps the "one place sees everything" property intact instead of fragmenting it.

**2. Two-tier detection: registry exact-match first, NER model second.**
The calendar importer (separate change) already builds a local `provider_registry.json` of known doctors/practices/addresses with an exact, zero-false-positive substring match. Running that same registry against outbound prompt text first means any name the user has already registered (for the stronger reason of appearing in a calendar event) gets caught here too, for free, with no NER uncertainty at all. The NER model then only has to catch what the registry doesn't know about — names in `symptoms.value_text`/`self_care.notes`/`user_context` that were never part of a calendar event. This also means the change still provides full NER-based protection even if `calendar-ics-importer` hasn't been implemented yet; the registry tier is additive, not required.

**3. NER via local spaCy pipelines, selected per-language after language detection — not a single multilingual model.**
This project is explicitly bilingual (`t("DE", "EN")`, `KYORO_LANG`), and several data sources already produce English free text (e.g. English-language exports from Bearable, HRV4Training, Shotsy, or entries the user writes in English herself). A single multilingual spaCy model (e.g. `xx_ent_wiki_sm`) exists but trades accuracy for breadth — it's measurably weaker per language than a dedicated pipeline. Given this filter's whole purpose is risk reduction where accuracy directly matters, the chosen approach is:
- Run a lightweight language-detection step (`langdetect`, pure-Python, no model download) on the text first.
- Load the matching dedicated spaCy pipeline for the detected language — German (`de_core_news_md` default) or English (`en_core_web_md` default) — lazily and cached per language for the life of the process (a German-only user never pays to load the English model, and vice versa).
- Both model choices are configurable (e.g. `llm.ner_models: {"de": "de_core_news_md", "en": "en_core_web_md"}`), same rationale as the single-model config in the original draft: the size/accuracy trade-off per language is a judgment call that may need revisiting, not a code change.
- **Fallback when detection is uncertain or the language isn't DE/EN:** run NER with the pipeline for the project's currently configured language — `modules.i18n.get_lang()` (set via `KYORO_LANG`/`set_lang()`/`--lang`, defaulting to German) — rather than hardcoding German as the fallback or skipping NER entirely. This is the one existing, already-correct source of "what language is this session in" (cross-cutting convention: no hardcoded single-language behavior, always go through `i18n`); hardcoding German here would silently misbehave for a session explicitly run with `KYORO_LANG=en`. Under-detecting and still attempting redaction (in the configured-language model) remains the safer failure mode than silently not redacting at all.
- Scoped to DE/EN for now, matching the two languages this project currently actually supports (`KYORO_LANG`); the per-language config dict is structured so a third language could be added later (e.g. once `add-catalog-based-i18n-languages` lands) without a redesign — not built speculatively now, just not architecturally blocked either.

**4. Detected names are pseudonymized via `identity_resolver`, not simply deleted.**
Deleting a name outright (replacing with nothing or a generic placeholder) loses the ability to tell two different people apart across a conversation, which can matter for a pattern-analysis prompt (e.g. distinguishing "person A" from "person B" across several symptom entries). `identity_resolver.resolve("llm_mention", <normalized detected name>)` gives a stable, locally-resolvable pseudonym per distinct name — consistent with how `calendar-ics-importer` already uses the same resolver for `kind="provider"`. No new pseudonymization mechanism is introduced.

**5. Single on/off switch (`llm.redact_entities`, default `true`), not a graduated policy.**
Unlike location precision, there is no meaningful "partial" version of a person's name — either it's there or it isn't. A per-caller allow-list (mirroring the location filter's `llm.allow`) would imply some callers legitimately need unredacted names sent to a remote provider, which isn't a real use case here. The simpler control surface avoids inventing a nuance the problem doesn't actually have. The default is the restrictive one (filter on), matching the location filter's own default-restrictive stance.

**6. Logs only counts, never matched text.**
Directly mirrors the location filter's existing logging convention (`The filter SHALL log only counts`) — a log that contained the detected name would recreate exactly the leak this change prevents, just in a log file instead of an LLM request.

## Risks / Trade-offs

- **[Risk]** NER false negatives (a real name not detected, e.g. an unusual name, a nickname, or text where capitalization/structure confuses the model) → **Mitigation:** documented explicitly as a known limitation (see Non-Goals); this is risk *reduction*, and is combined with the registry tier for names the user already knows to flag. Not claimed as complete.
- **[Risk]** Language detection misclassifies short or mixed-language text (e.g. a two-word prompt, or German text with English medical terms mixed in), causing the wrong model to run and missing a name that the correct-language model would have caught → **Mitigation:** fallback to the pipeline for the session's configured language (`i18n.get_lang()`, not a hardcoded language) rather than skipping NER on detection failure (decision 3); accepted as a residual gap on top of the already-documented NER false-negative rate, not a new category of risk.
- **[Risk]** NER false positives (an ordinary word misclassified as a person name) → **Mitigation:** costs response coherence, not privacy — an acceptable trade-off direction (over-redaction is the safe failure mode, under-redaction is not).
- **[Risk]** New dependency (`spacy` + a model download, potentially several hundred MB) adds setup weight → **Mitigation:** this is consistent with how other optional capabilities in this repo already add heavy dependencies (e.g. `playwright`, `wfdb`, `neurokit2`); `onboard.py`/README should note the model download step, same as other post-install steps already documented elsewhere in this repo.
- **[Risk]** Per-call NER inference adds latency to every remote `call_llm()` invocation → **Mitigation:** local CPU-based spaCy inference on a single short-to-medium prompt is fast (well under a second typically); not expected to be noticeable relative to the remote LLM round-trip itself, but worth confirming empirically during implementation (see Open Questions).
- **[Risk]** `identity_resolver` gains a new, less-constrained `kind` (`"llm_mention"`) whose input is NER-detected free text rather than a curated identifier list — pseudonym churn could grow large over time (one entry per distinct detected name variant) → **Mitigation:** acceptable; `identity.db` is a local, unbounded append-only store already serving this role for other kinds, and the privacy property (no real name stored except here, locally) still holds.

## Migration Plan

Not applicable — purely additive. No schema change to `health.db`/`medicine.db`. Rollback is removing the filter call from `call_llm()` and the new module; no other code depends on it.

## Open Questions

- Exact spaCy model defaults per language (`de_core_news_md`/`en_core_web_md` proposed) and whether a lighter/heavier alternative should be the shipped default for either — decide after a quick empirical check against a handful of real (not fabricated) `symptoms.value_text`/`self_care.notes` entries in both languages during implementation.
- Whether `langdetect` is reliable enough on short prompt fragments, or whether a more robust (but heavier) alternative should be used instead — check empirically during implementation; this is the main open question introduced by the per-language design.
- Whether `ORG` entities (not just `PERSON`) should also be redacted by default, given practice names are organizations too — leaning yes, but should be confirmed against false-positive rate in practice (German `ORG` NER tends to be noisier than `PERSON`).
- Whether to also run this filter on structured JSON/CSV blocks that get embedded in a prompt (e.g. SQL query results formatted as text) — likely yes, since those are still just `prompt`/`system` text by the time they reach `call_llm()`, but worth confirming no caller bypasses the string-based prompt argument for some other transport.
