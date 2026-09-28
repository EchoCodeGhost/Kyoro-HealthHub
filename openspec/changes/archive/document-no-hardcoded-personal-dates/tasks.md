## 1. Spec artifacts

- [x] 1.1 Write proposal.md (why, what changes, capabilities, impact)
- [x] 1.2 Write design.md (context, decisions, risks, open questions)
- [x] 1.3 Write specs/privacy-rules/spec.md (ADDED requirement: no hardcoded personal dates/timestamps)

## 2. Cross-linking

- [x] 2.1 Verify CLAUDE.md's existing "No personal values are hardcoded in the repo... Every date, device ID, and person identifier comes from config" line still accurately points at the now-complete set of formalized requirements (timezone, device ID, person identifier, date) — no wording change needed if it already does
- [x] 2.2 Verify `openspec validate document-no-hardcoded-personal-dates` (or equivalent) passes before archiving

## 3. Archive

- [ ] 3.1 Sync the new requirement into `openspec/specs/privacy-rules/spec.md` and archive this change (openspec-archive-change skill / `opsx:archive`)
