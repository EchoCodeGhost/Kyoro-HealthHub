## Why

Inserting a field into a positionally-read data structure silently breaks every
reader that indexes into it. This is not hypothetical: two fields were added
mid-tuple to the result rows in `compute_pem.py`, the `INSERT` column list was
updated correctly, but the console summary below it kept its old indices. It then
printed `react=17.3 lag+18d` — with `for lag in range(1, 4)`, a lag of 18 cannot
occur. The output was read, quoted in a review, and passed on before anyone
noticed. It was caught only in post-merge review by the maintainer.

`db-schema-conventions` already treats a table/column rename as a global change.
The same reasoning applies one level down, to in-memory row shapes: a tuple built
in one function and consumed by index in another is a contract, and changing it is
a global change too. Nothing currently states this as a requirement a reviewer
(human or AI) could point at.

The second half of the failure is separate and worth naming: the impossible value
was visible in the author's own run. A value that cannot occur by construction is
evidence that the code is wrong, not noise to scroll past.

## What Changes

- Add a requirement to `cross-cutting-conventions` covering structural changes to
  positionally-read data structures: after inserting, removing or reordering a
  field, every positional reader of that structure must be located and updated.
- Add a scenario covering the review side: an impossible-by-construction value in
  a script's own output is treated as a defect, not as noise.
- Deliberately does NOT add automated tooling. A linter for "tuple index used
  after tuple shape changed" would need type information the codebase does not
  carry; the requirement is written so a reviewer can point at it, consistent with
  how the timezone and device-agnosticism rules were introduced.
- Deliberately does NOT mandate replacing tuples with dataclasses or named tuples.
  That would be a large refactor of working code; the requirement constrains how
  changes are made, not how data is represented.
