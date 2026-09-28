## 1. Spec artifacts

- [x] 1.1 Write proposal.md (why, what changes, capabilities, impact)
- [x] 1.2 Write design.md (context, decisions, risks, open questions)
- [x] 1.3 Write specs/cross-cutting-conventions/spec.md (3 requirements: timezone, device-agnosticism, i18n)

## 2. Cross-linking

- [x] 2.1 Add a one-line reference to the new `cross-cutting-conventions` capability under CLAUDE.md's existing "Privacy rules" section (pointing at the spec, not duplicating its content)
- [x] 2.2 Verify `openspec validate document-cross-cutting-conventions` (or equivalent) passes before archiving

## 3. Archive

- [x] 3.1 Sync the new capability into `openspec/specs/cross-cutting-conventions/spec.md` and archive this change (openspec-archive-change skill / `opsx:archive`)
