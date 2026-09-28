## ADDED Requirements

### Requirement: Structural change to positionally-read data
A change that inserts, removes or reorders a field in a data structure read by
position — a result tuple consumed via `row[i]`, a fixed-length row unpacked into
variables, an `INSERT` column list paired with a value tuple — SHALL be treated as
a global change. Every reader of that structure SHALL be located and updated in
the same change, in the same way `db-schema-conventions` treats a table or column
rename as global rather than local.

This applies to positional access only. Structures read by key name (`dict`,
`sqlite3.Row`, named tuple field access) are unaffected, because inserting a field
there does not shift the meaning of the others.

#### Scenario: Field inserted into a result tuple
- **WHEN** a contributor adds a field in the middle of a tuple that is built in
  one place and consumed by index elsewhere (console output, plot, export,
  downstream aggregation)
- **THEN** the change locates every positional reader of that tuple and updates
  the indices, and the contributor states in the PR where those readers are —
  updating only the database column list is not sufficient

#### Scenario: Structure is read by key rather than position
- **WHEN** the affected structure is a dict, a `sqlite3.Row`, or a named tuple
  accessed by field name
- **THEN** inserting a field is not a global change and this requirement does not
  apply

### Requirement: Impossible values in a script's own output are defects
A value that cannot occur by construction — a loop variable outside its declared
range, a float where an integer is assembled, a per-day count exceeding the days
in the period — SHALL be treated as evidence of a defect and investigated before
any result derived from that run is reported or merged.

#### Scenario: Console summary prints an out-of-range value
- **WHEN** a script's output contains a value that its own control flow cannot
  produce (e.g. `lag+18d` where the lag loop is `range(1, 4)`)
- **THEN** the run is treated as failed and the cause is found, rather than the
  surrounding numbers being reported as valid

#### Scenario: Value is unusual but constructible
- **WHEN** a value is merely surprising — a high but reachable measurement, an
  unexpected but possible count
- **THEN** this requirement does not apply; it covers values ruled out by the
  code's own structure, not values ruled out by expectation
