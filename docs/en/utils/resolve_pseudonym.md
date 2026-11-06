# resolve_pseudonym.py — Pseudonyme (DEV-/PER-/PRV-/SRC-) menschenfreundlich zurückauflösen

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/utils/resolve_pseudonym.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Resolves one or more pseudonyms of EVERY type used in the project (DEV-/PER-/PRV-/SRC- from identity.db, SN-/UID- from identity.db side tables, LOC- from location_store.py) back to their real value -- without having to write Python snippets or raw sqlite3 queries (modules.identity_resolver.reverse_resolve() already existed, but had no CLI entry point for someone who just wants to ask "what does PRV-701ef95f mean?"). LOC- tokens (GPS grid cells) are deliberately NOT resolved, see @limits -- they're irreversible by design, not a missing feature.

## Relevance

Makes resolving pseudonyms practical for everyday use, essential so review work on pseudonymized candidate JSONs doesn't constantly require Python snippets

## Method

Two modes: pseudonyms given directly as arguments ("resolve_pseudonym.py PRV-701ef95f SRC-6d5bc39f"), OR with no arguments, read from stdin and regex-match ALL pseudonym hits (any prefix) in the text -- so you can pipe a whole candidate JSON or a "grep icd_catalog_flag ..." output through it without first hunting down the pseudonyms by hand. Each pseudonym found is resolved EXACTLY ONCE (duplicates are deduplicated), via modules.identity_resolver.reverse_resolve() (determines the table automatically from the prefix).

## Data flow

- **Reads:** `~/.config/kyoro/identity.db`, `(über`, `modules.identity_resolver)`
- **Writes:** `keine Tabellen (reiner Lookup nach stdout)`

## Limitations

Only resolves what's in the local identity.db -- a pseudonym from a different installation/different salt yields "not found", not an error. Detects pseudonyms purely by pattern (prefix + 8 hex chars) -- a coincidentally similar-looking string that isn't a real pseudonym would also be reported as "not found", not flagged as an invalid input format. LOC- tokens (GPS grid cells from location_store.py) are deliberately NEVER resolved -- per that module's own docstring, precision there is "ALWAYS applied before writing and is irreversible", a different mechanism than the 1:1 pseudonyms in identity.db, not a bug in this script.

## Usage

```bash
python3 resolve_pseudonym.py PRV-701ef95f SRC-6d5bc39f
grep icd_catalog_flag kandidaten.json | python3 resolve_pseudonym.py
cat kandidaten.json | python3 resolve_pseudonym.py
```
