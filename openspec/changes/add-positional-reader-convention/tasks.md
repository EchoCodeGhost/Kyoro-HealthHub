## 1. Spec extension

- [x] 1.1 Add requirement "Structural change to positionally-read data" to `cross-cutting-conventions`
- [x] 1.2 Formulate scenario "Field inserted mid-way into a result tuple"
- [x] 1.3 Formulate scenario "Impossible value in the script's own output"
- [x] 1.4 Document the boundary: applies to positional readers, not to access via key names

## 2. Code inventory (no refactoring)

- [ ] 2.1 Record spots where a tuple is built in one function and read by index in another
- [ ] 2.2 For each spot found, check whether the build site and the read site assume the same field order
- [ ] 2.3 Submit any deviations found as their own fixes, not as part of this change

## 3. Anchor in contributor documentation

- [ ] 3.1 Name the rule in `docs/CONTRIBUTING_DE.md` / `docs/CONTRIBUTING.md` among the pre-PR review steps
- [ ] 3.2 Reference the analogy to `db-schema-conventions` (renaming is global)
