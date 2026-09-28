## Why

Kyoro-HealthHub processes highly sensitive personal health data and is a
public repo on GitHub. The privacy rules ("no
diagnosis names/entity IDs in code", "no hardcoded timezones", "no
fallback dict with real entity IDs") are the most important protection
mechanism so that future contributors (and the maintainer themselves) don't
accidentally leak personal data into the public code portion. So far
these rules only live in CLAUDE.md and in the compliance script
`check_source_privacy.py`. A spec makes them explicit as checkable
requirements — especially important for PR reviews from contributors who
don't know this sensitivity from the start.

## What Changes

- New `privacy-rules` spec documenting the existing privacy conventions
  as requirements/scenarios.
- No code change; purely documenting existing behavior.

## Capabilities

### New Capabilities
- `privacy-rules`: prohibition of diagnosis names/entity IDs/person IDs
  in identifiers and filenames, prohibition of hardcoded IANA
  timezones, prohibition of fallback dicts with real entity IDs
  (`sys.exit` on missing config instead of a default), mandatory
  compliance check `check_source_privacy.py`.

### Modified Capabilities
(none — purely new documentation of existing behavior)

## Impact

- Affects no code files directly.
- References: `scripts/utils/check_source_privacy.py`,
  `scripts/health_config.py`, `~/.config/kyoro/health_config.json`
  (`privacy_check.forbidden_identifiers`).
- Serves future contributors as a binding review checklist alongside
  CLAUDE.md, especially for first-time contributions without prior
  knowledge of the data's sensitivity.
