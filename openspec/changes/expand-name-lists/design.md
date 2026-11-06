## Context

Name lists are used in three places:

- `modules/name_redaction.py` builds a regex from `name_lists.json`: a listed first name followed by a capitalised word, or a capitalised word followed by a listed surname. `find_name_spans()` is used by media redaction, synthesis scrubbing and `scrub_sensitive_health_data()`. `combined_pattern_source()` covers only the fixed patterns and is not affected.
- `utils/anonymize.py` loads the JSON and falls back to a hardcoded copy. `utils/name_validation.py` uses that loader.
- `utils/scrub_pii.py` has its own hardcoded first-name and surname regexes in `find_pii_in_database()`.

If the JSON is missing, `name_redaction._name_lists()` silently returns empty lists, and detection quietly gets worse.

Personal names of the owner and relatives already have a proper home: `privacy_check.patient_names` in local config and `person_name_map` in `identity.db`, both read by `load_known_names()`.

Source check so far:
- The US Social Security baby names dataset is listed under CC0.
- The Cologne registry office first-name dataset is public, but its metadata does not confirm a licence, and part of it is contradictory.
- Berlin and UK sources are not yet verified.

## Goals / Non-Goals

**Goals:**
- Substantially better first-name coverage for German and English text.
- Every bundled name is traceable to a public source with a compatible licence.
- No personal names in the repo's lists or code.
- Clinical terms and everyday German words are not treated as names.

**Non-Goals:**
- Surnames. Public lists contain medical eponyms, and the existing short list stays as it is.
- Detecting a first name on its own, without a following capitalised word.
- Named-entity recognition, which `llm-entity-redaction` covers at the point where text leaves the machine.
- Languages other than German and English.

## Decisions

### 1. Sources need a verified licence before anything is bundled

The English list starts from the US Social Security dataset (CC0). The German list needs at least one municipal or national open-data source whose licence page has been read and is compatible with redistribution in a GPL-licensed repo. The candidates are Cologne, Berlin and other German cities, and UK and further regional sources are optional. A source with an unclear licence is not used. If no German source qualifies, the English list ships and the German gap is reported, rather than weakening this rule.

`SOURCES.md` records each source's URL, publisher, licence and attribution text, as required by the licence.

### 2. Reproducible build, filtered output only

`build_name_lists.py` reads downloaded source files from a path given as an argument and writes plain, sorted, one-name-per-line files. It applies a frequency cut-off, drops names under three letters, and removes exclusions. Raw data and counts are not committed.

*Why a cut-off:* rare entries in baby-name data are often ordinary words or typos. Each added name adds false-positive risk, and rare names add little coverage. The threshold is set from the measurement in decision 6, not guessed.

*Alternative:* committing the full raw data. Rejected: size, and licence obligations with no benefit.

### 3. Exclusion list for names that are also words

German capitalises nouns, so "listed first name + capitalised word" collides with ordinary text: "Mark" also means bone marrow, and "Rose" is also a skin condition. English adds words such as "Will" and "Grace". `name_exclusions.txt` removes such entries from the bundled lists at build time, and a test keeps them out. It is seeded from a German word list check of all candidates, plus clinical terminology already used in the repo's lab and syndrome data.

Excluded names are still matched with a title or field label ("Frau Rose"), and exact known names from local config are unaffected.

### 4. Word lookup instead of a regex alternation

An alternation of tens of thousands of names is slow to compile and to match, and this runs on OCR output and long prompts. Instead, a regex finds capitalised words, and each is looked up in a set. If a following capitalised word exists, the pair becomes a span. Matching must not consume the second word, so that three-word names and the existing merge behaviour keep working. The surname direction keeps its regex, since its list stays short.

### 5. One source of names; missing lists are visible

`scrub_pii.py` and `anonymize.py` drop their hardcoded first-name data and read the bundled lists through one loader. The bundled files ship with the repo, so a missing or unreadable file is a real fault: the affected operation fails with a clear error, in line with the project's rule against fallback data in code. This applies to the loader, so `find_name_spans()` no longer silently degrades.

`find_pii_in_database()` matches first names on their own, which would flag far more values with a large list. It is changed to use `find_name_spans()`-compatible rules, so that a single common word cannot trigger a rewrite.

### 6. Measure before enabling

A report-only comparison runs old and new detection over synthetic clinical text in tests, and over the real databases and reports locally, printing counts only. It determines the frequency cut-off and shows newly matched words, which a person reviews locally. Results and matched text stay out of the repo.

### 7. Known names stay in config

Names of specific people belong in `privacy_check.patient_names` or `person_name_map`, not in the bundled lists. A test confirms that a configured name is detected whether or not it is on a bundled list.

## Risks / Trade-offs

- **[A clinical term gets overwritten]** → Exclusion list, cut-off, measurement, and a pair of capitalised words is required. Clinical columns in `medicine.db` are not scanned at all under `extend-pii-scan-to-medicine-db`.
- **[A common name on its own stays undetected]** → Accepted and documented. Only a pair, a title, a label or a known name is matched.
- **[Licence terms change, or a dataset moves]** → `SOURCES.md` records what was used, and the bundled file stays valid under the licence it was obtained under.
- **[Missing list now fails loudly]** → Intended, and the files are part of the repo.
- **[List age]** → Baby-name data is skewed towards recent years, so older German name data should be preferred where a source offers it.

## Migration Plan

1. Build lists and exclusions, and run the report-only comparison.
2. Switch the loader and remove the hardcoded lists.
3. Rollback: revert the commit. The old lists return with it.

## Open Questions

- Which German source has a usable licence, and does it cover older generations, or only recent births?
