## Why

Name detection knows only 26 first names, so most names without a title or field label go undetected. The same short list is also hardcoded in `scrub_pii.py` and as a fallback in `anonymize.py`, so it can drift. Public name statistics give much better coverage and one traceable source.

## What Changes

- New bundled first-name lists for the German- and English-speaking regions, built from public datasets whose licence is verified and documented.
- New build script that turns downloaded source data into the bundled lists reproducibly, with a frequency cut-off. Raw data and counts stay out of the repo.
- New exclusion list for names that are also German words or medical terms, such as "Mark" or "Rose".
- `modules/name_redaction.py` looks up first names per word instead of compiling one regex alternation, which would not scale to a list of this size.
- `scrub_pii.py` and `anonymize.py` lose their hardcoded first-name lists and read the bundled lists. A missing list becomes a visible error instead of a silent loss of detection.

Not part of this change: surnames, because public surname lists contain many medical eponyms.

## Capabilities

### New Capabilities
- `name-detection-lists`: Provenance, build, content rules and false-positive protection for the bundled first-name lists used in name detection.

### Modified Capabilities
<!-- None: no existing spec describes name lists. -->

## Impact

- **New:** `scripts/utils/build_name_lists.py`, first-name and exclusion lists plus a source and licence document under `scripts/utils/name_lists/`, tests.
- **Modified:** `scripts/modules/name_redaction.py`, `scripts/utils/scrub_pii.py`, `scripts/utils/anonymize.py`, `scripts/utils/name_lists/README.md`.
- **Behaviour:** more names are detected, and every path using `find_name_spans()` is affected: media redaction, synthesis scrubbing and post-import sanitising. A wrongly matched word is overwritten there, which is why the rollout includes a measurement on real data.
- **Related changes:** planned after `extend-pii-scan-to-medicine-db`. Heuristic matches in `medicine.db` stay report-only under that change, so this one does not add rewrites there.
