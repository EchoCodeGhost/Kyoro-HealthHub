# OpenSpec

> **German version:** [OPENSPEC_DE.md](OPENSPEC_DE.md)

Kyoro-HealthHub uses [OpenSpec](https://openspec.dev/) to keep architectural
requirements as living, versioned specs alongside the code — separate from
the per-script documentation generated from docstrings (see
[docstring_onboarding_guide.md](docstring_onboarding_guide.md)).

---

## Why

CLAUDE.md and the generated per-script docs describe *how* the code works.
OpenSpec specs describe *what the system is required to do* — in a form that
survives beyond a single chat session and can be diffed when requirements
change. This matters most for contributors who join after the initial
release and need a structured starting point beyond reading the whole
codebase.

## Where specs live

```
openspec/
├── config.yaml        — project context shown to AI tools when authoring specs
├── specs/              — current baseline: one spec.md per capability
│   ├── pipeline-architecture/
│   ├── db-schema-conventions/
│   ├── privacy-rules/
│   ├── importer-pattern/
│   └── … (14 capabilities total, see table below)
└── changes/
    ├── <proposal-name>/  — active change proposals in flight (proposal.md, design.md, tasks.md)
    ├── …
    └── archive/           — completed change proposals, merged into specs/
```

Each `spec.md` contains `### Requirement:` blocks with `#### Scenario:`
sections in WHEN/THEN form — testable statements, not prose.

## Current baseline specs

| Capability | Covers |
|---|---|
| `pipeline-architecture` | Import → Compute → Analyse ordering, fixed compute dependency chain, silent-empty-output behavior when a stage is skipped |
| `db-schema-conventions` | EAV pattern for time series, `person`/`OWN_PERSON_ID` convention, compatibility views, `INSERT OR IGNORE`, `ts`/`date` semantics |
| `privacy-rules` | No diagnosis/entity identifiers in code, no hardcoded timezones, no hardcoded-entity fallback dicts, mandatory `check_source_privacy.py` pass |
| `importer-pattern` | Required `run()` signature, `resolve_person()`/`resolve_timezone()` usage, atomic `log_import()`, registration in `import_all.py` |
| `cross-cutting-conventions` | No hardcoded timezones/devices/languages across every new script, structural-change and impossible-value handling |
| `data-provenance` | Import/migration attribution and code-version logging, analysis-run logging, no false per-person attribution claims |
| `documentation-conventions` | `label_finding()` confidence qualifiers, mandatory `@relevance.de`/`@relevance.en` docstring field, bilingual (DE-first) content, docstring schema as source of truth |
| `ethics-enforcement` | Prohibited-use list, local-by-default storage, authenticated API access, no credentials in code/logs, import-time data minimization |
| `fhir-export` | FHIR as an additional export format, no fabricated terminology codes, pseudonymous patient reference, offline schema validation, export-only (no network transmission) |
| `identifier-pseudonymization` | Central `identity_resolver` module, deterministic salted pseudonyms stored locally, `sensor_type`-based device routing instead of raw device pseudonyms |
| `image-importer-pattern` | Mandatory PII stripping for photo/image imports, GPS capture-before-discard, RAW+preview retention, device-serial pseudonymization for RAW, location data scoped to medically relevant analyses |
| `privacy-by-design-access-control` | Equal-standing private-use contexts, security/privacy by design and by default, anonymization-first with pseudonymization as the floor, tested multi-user authorization |
| `reference-device-configuration` | Per-metric reference-device configuration with hardcoded fallback, config-driven anchors in `compute_calibrate_sources.py`/`compute_pem.py`, `device_registry.source_apps` resolution |
| `research-cohort-export` | Consent-gated instance inclusion, per-patient deterministic date shifting, age banding, k-anonymity enforcement, local-only output |

The first four were authored as a **brownfield baseline**: they document
behavior that already existed in the code and in CLAUDE.md at the time of
writing — no functionality changed when they were introduced. The rest were
added incrementally as change proposals were archived (see "Where specs
live" above).

## Using OpenSpec for a new contribution

If Claude Code is set up with the OpenSpec integration (`openspec init
--tools claude`), the following slash commands are available:

| Command | Purpose |
|---|---|
| `/opsx:propose` | Describe what you want to build; generates proposal, design, spec deltas and tasks in one step |
| `/opsx:explore` | Think through an idea or requirement before committing to a proposal |
| `/opsx:apply` | Implement the tasks of an existing change |
| `/opsx:update` | Revise an existing change's artifacts |
| `/opsx:sync` | Sync a change's spec deltas into the main specs without archiving |
| `/opsx:archive` | Finalize a completed change and merge its spec deltas into `openspec/specs/` |

A typical flow for a new importer: `/opsx:propose "importer for <device>"`
→ review the generated proposal/spec delta against
[importer-pattern](../openspec/specs/importer-pattern/spec.md) and
CONTRIBUTING.md → `/opsx:apply` to implement → have the
`review-importer` skill check the result → `/opsx:archive` once merged.

## What this is not

- Not a replacement for CLAUDE.md (day-to-day workflow, commands, conventions)
  or the per-script docs in `docs/de/`/`docs/en/` (implementation detail).
- Not enforced by CI — specs are a review aid, not a runtime gate.
- Not meant to cover every corner of the codebase. New specs should be added
  when they help onboard contributors to a specific area, not as a blanket
  documentation exercise.
