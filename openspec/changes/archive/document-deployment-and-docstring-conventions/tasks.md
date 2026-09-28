## 1. Verification: already-fixed files

- [x] 1.1 Confirm that `pwa/symptom-pwa.service` and
      `tools/KST-PWA/symptom-pwa.service` use the `CHANGEME` placeholder
      in `User=`, `WorkingDirectory=`, `ExecStart=`,
      `Environment=HOME=` and no longer contain a real username/path.
      Verified: all four directives in both files use `CHANGEME`.
- [x] 1.2 Confirm that both files contain a German and an English line
      in every content comment block.
      Verified: header comments consistently have a DE line
      followed by an EN line, including the documented `sed`
      replacement command.

## 2. Repo-wide scan for further violations

- [x] 2.1 Search the rest of the repo for other deployment artifacts
      (`*.service`, `Caddyfile`, `.env.example` or similar) with
      hardcoded real usernames/home paths (e.g.
      `grep -rn "/home/[a-z]" --include="*.service" --include="Caddyfile"`).
      Verified: no further hits outside the already-fixed
      `CHANGEME` spots.
- [x] 2.2 Switch any hits found over to `CHANGEME`, if present.
      No further hits found (see 2.1) — nothing to do.

## 3. Spot-check docstring-schema conformance

- [x] 3.1 `python3 scripts/check_docstrings.py` runs green (confirms
      that the new spec only describes already-enforced practice,
      introducing no new requirement that would break existing
      scripts). Verified: all valid, 0 errors.
- [x] 3.2 `python3 tools/gen_docs.py --check` runs green (confirms that
      all generated docs match the current docstrings). Verified:
      OK (all scripts, both languages).

## 4. Spec archiving

- [x] 4.1 Change review: `proposal.md`, `design.md`, both spec deltas,
      and this `tasks.md` are mutually consistent (no contradictions
      between requirement text and scenario examples). Done:
      consistent in substance. One point in `design.md`'s Migration
      Plan had become technically outdated by the intervening archiving
      of `add-confidence-and-relevance-conventions` (the target file
      now already exists before this archiving) — corrected, not a
      blocker (the merge logic in `specs-apply.js` handles both orders,
      no requirement name collision between the two changes).
- [ ] 4.2 Archive the change (`openspec-archive-change` /
      `/opsx:archive`), so that `privacy-rules/spec.md` gets the new
      requirement and `openspec/specs/documentation-conventions/spec.md`
      is created as a new file — **Update:** the file already exists
      (see the design.md update), it will only be extended on
      archiving, not created anew.
