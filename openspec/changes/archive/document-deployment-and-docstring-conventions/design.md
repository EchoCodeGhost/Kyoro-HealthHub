## Context

This change formalizes lived but so far unrecorded practice as a spec —
no new mechanism is being built. The trigger was finding a hardcoded
real Linux username and an absolute path in `pwa/symptom-pwa.service`
/ `tools/KST-PWA/symptom-pwa.service`, which were already switched to a
`CHANGEME` placeholder ad hoc the same day. Without a binding
requirement, the same mistake can recur with the next deployment
artifact (further systemd units, Caddyfiles, `.env.example` files).

In parallel, a structured, bilingual docstring schema
(`docs/docstring_template.md`, `docs/docstring_faq.md`) has existed
since the project began, validated by `scripts/check_docstrings.py` and
rendered by `tools/gen_docs.py` into `docs/de/`/`docs/en/`. This schema
underlies all the other already-archived `document-*-conventions`
changes (db-schema, importer-pattern, pipeline-architecture,
privacy-rules itself follows it), but was never anchored as a binding
spec itself — it only lived as a documentation file.

## Goals / Non-Goals

**Goals:**
- Add a requirement to `privacy-rules` that forbids hardcoded host/user
  values in deployment artifacts (systemd units, Caddyfiles, comparable
  infra configs) and mandates the `CHANGEME` placeholder as the standard
  solution.
- Create a new `documentation-conventions` capability that records as
  binding requirements (a) the bilingualism convention (German before
  English) for all user-/contributor-facing text and (b) the structured
  docstring field schema.
- Mirror existing conventions already lived in the repo 1:1 — invent no
  new rules beyond what `docs/docstring_template.md` and today's
  `.service` fixes already show.

**Non-Goals:**
- No new tooling (no new linter, no new compliance-check mode) —
  `check_source_privacy.py` and `check_docstrings.py` already cover
  enforcement, or a separate follow-up change may extend them with a
  deployment-artifact check.
- No retroactive migration of all existing deployment files in this
  change — only `pwa/symptom-pwa.service` and
  `tools/KST-PWA/symptom-pwa.service` are affected and already fixed;
  other possibly hardcoded files are not searched for in this change.
- No statement about languages beyond German/English.

## Decisions

**1. New requirement in `privacy-rules` instead of a new spec capability.**
Hardcoded host/user values are, in substance, the same category of
problem as the rules already anchored there (no diagnosis identifiers,
no `'self'` literal, no hardcoded timezone, no fallback dicts with real
entity IDs) — all five rules boil down to "no real, personal/
identifying value in the committed artifact, use a placeholder/config/
exit instead". A separate spec for this would be artificial
fragmentation.
*Alternative considered:* a dedicated `deployment-conventions` spec —
rejected, since it's only a single requirement and not a self-contained
architecture topic.

**2. `documentation-conventions` as its own new capability instead of
extending `privacy-rules`.**
Bilingualism and the docstring schema are not a privacy topic (they're
about readability/consistency for two language groups and documentation
completeness, not about protecting personal data) — so they belong in
their own capability instead of being mixed into `privacy-rules`.

**3. `CHANGEME` as the standard placeholder token (not `%h`/systemd
specifiers).**
`scripts/cluster/rpc-node.service` uses `%h`, which only works reliably
for `systemd --user` units with a user context; the PWA units are
system units with an explicit `User=`, where `%h` is only available
after `User=` has been resolved — a circular reference. `CHANGEME` as a
plain text placeholder with a `sed` one-liner in the comment (already
implemented this way in both fixed files) is simpler and works
regardless of the unit type.
*Alternative considered:* systemd template units (`symptom-pwa@.service`
with `%i`) — rejected, since that changes the invocation (`systemctl
enable --now symptom-pwa@<username>`) and means more migration effort
for users than justified.

**4. Bilingualism in non-Python files as side-by-side comment blocks
(German line, then English line), not as two separate files.**
For documentation files with a free filename (e.g.
`docs/CLINIC_DEPLOYMENT.md` + `docs/CLINIC_DEPLOYMENT_DE.md`), the
two-file pattern is established and stays valid. For files with a fixed,
dictated name (e.g. `symptom-pwa.service`, which `systemctl` expects
exactly as named), a second file isn't possible — there, only the inline
bilingual comment block remains, as already implemented in both
`.service` files today.

## Risks / Trade-offs

- [Risk] Inline bilingual comments double the line count in deployment
  files and could become cluttered → Mitigation: the requirement is
  limited to short, block-wise comments (as in the reference example),
  not whole paragraphs.
- [Risk] Formalizing this without an accompanying compliance check means
  a violation only surfaces in manual review, not automatically →
  Mitigation: noted as an open question for a possible follow-up change
  (extending `check_source_privacy.py` to deployment artifacts).
- [Trade-off] The new `documentation-conventions` capability only
  formalizes what is already lived practice — no new risk, but also no
  immediate added value beyond traceability for new contributors (human
  or AI).

## Migration Plan

No rollout needed — pure spec documentation. After this change is
archived:
1. `privacy-rules/spec.md` contains the new requirement.
2. `documentation-conventions/spec.md` additionally contains this
   change's two requirements. **Update:** the file already
   exists under `openspec/specs/` — created when archiving
   `add-confidence-and-relevance-conventions`, which populated the same
   capability with two other requirements first (confidence labeling,
   `@relevance`). When this change is archived, the file is therefore
   not created anew, just extended with the two requirements described
   here (no name collision, technically unproblematic — checked against
   the OpenSpec merge logic in `specs-apply.js`).
No code is changed by this change itself; the affected `.service` files
were already fixed before this change.

## Open Questions

- Should `check_source_privacy.py` (or a new script) in the future also
  check deployment artifacts (`*.service`, `Caddyfile`) for hardcoded
  host/user patterns? Not part of this change, but a natural follow-up
  change.
