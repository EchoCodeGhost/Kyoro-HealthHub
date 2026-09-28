## ADDED Requirements

### Requirement: Track-to-store mapping
The system SHALL map each anamnesis-interview track to the existing local JSON store(s) its findings can be promoted into: exposure/travel history → `travel_history.json`; animal contact → `exposure_history.json` (`animal_contacts[]`); occupational history & exposures → `exposure_history.json` (`occupational_exposures[]`); family history → `family_history.json`; leisure & hobbies → `known_risk_exposures.json`. Occupational, animal-contact, and exposure/travel findings SHALL additionally be eligible for promotion to `known_risk_exposures.json` when they represent a chronic or ongoing exposure rather than a one-off event.

#### Scenario: Finding from a mapped track is reviewed for promotion
- **WHEN** a finding from the animal-contact track is reviewed
- **THEN** the system offers `exposure_history.json` (`animal_contacts[]`) as a promotion target, and additionally offers `known_risk_exposures.json` if the finding represents a chronic/ongoing exposure

#### Scenario: Family-history finding is reviewed for promotion
- **WHEN** a finding from the family-history track is reviewed
- **THEN** the system offers only `family_history.json` as a promotion target, never `known_risk_exposures.json`

### Requirement: Non-interactive append functions reuse existing script logic
The system SHALL add one non-interactive append function to each of `manage_family_history.py`, `manage_travel_history.py`, `manage_exposure_history.py`, and `manage_known_risk_exposures.py`. Each such function SHALL reuse that script's own existing `load()`/`save()` I/O and field validation logic (choice lists, required fields, slug constraints) rather than reimplementing equivalent logic elsewhere. The existing interactive `cmd_add`-style functions in these scripts SHALL remain unchanged and fully functional for direct manual use.

#### Scenario: A finding is promoted to family_history.json
- **WHEN** a family-history finding is promoted
- **THEN** the system calls the new non-interactive append function in `manage_family_history.py`, which validates the entry against the same relative/side/status choice lists the interactive command uses and writes via the script's existing `save()` function

#### Scenario: Interactive command still works after this change
- **WHEN** a user runs `manage_family_history.py add` directly from the terminal, unrelated to any interview
- **THEN** the existing interactive prompts behave exactly as before this change

### Requirement: Human-confirmed, per-finding promotion
The system SHALL require an explicit confirmation for each individual finding and each individual target store before writing a promoted entry. The system SHALL NOT promote any finding automatically or in bulk without per-finding confirmation, and SHALL always display the exact entry (all fields, as they will be written) before asking for confirmation.

#### Scenario: User reviews a proposed promotion
- **WHEN** the promotion mode proposes writing a finding to a target store
- **THEN** the system displays the complete entry that would be written and waits for explicit user confirmation before writing anything

#### Scenario: User declines a proposed promotion
- **WHEN** the user declines a proposed promotion for a given finding/target pair
- **THEN** the system does not write to that target for that finding, and continues to the next proposed promotion without treating the decline as an error

#### Scenario: A finding is eligible for two targets
- **WHEN** a finding is eligible for both a primary target (e.g. `exposure_history.json`) and `known_risk_exposures.json` as a secondary target
- **THEN** the system asks for confirmation on each target independently, and the user may accept one, both, or neither

### Requirement: known_risk_exposures.json promotion requires a valid current slug
The system SHALL only offer `known_risk_exposures.json` as a promotion target for a finding that already has a candidate `syndrome_slug` attached from the interview's own extraction. Before writing, the system SHALL validate that candidate slug against the currently known syndrome-slug set used by `analyse_outbreak_exposure.py`, not merely trust the slug as extracted at interview time. A finding whose slug no longer validates SHALL be excluded from this promotion target with a clear message, not written with an invalid or unmatched slug.

#### Scenario: Finding has a valid, current slug
- **WHEN** a finding's candidate slug matches a currently known syndrome slug
- **THEN** the system offers promotion to `known_risk_exposures.json` with that slug pre-filled

#### Scenario: Finding has no candidate slug
- **WHEN** a finding has no candidate `syndrome_slug` attached
- **THEN** the system does not offer `known_risk_exposures.json` as a promotion target for that finding

#### Scenario: Finding's slug no longer validates
- **WHEN** a finding's candidate slug does not match any currently known syndrome slug (e.g. the known-slug set changed since the interview ran)
- **THEN** the system excludes that target for that finding and displays a message explaining why, rather than writing an entry with an invalid slug

### Requirement: Idempotent promotion
The system SHALL mark a finding as promoted to a given target once the user confirms that promotion, and SHALL NOT re-offer or re-write that same finding/target pair on a subsequent promotion run for the same session.

#### Scenario: Re-running promotion on an already-processed session
- **WHEN** the promotion mode is run a second time on a session whose findings were already reviewed
- **THEN** findings/targets already promoted are not re-offered, and no duplicate entries are written to any target store

#### Scenario: New findings added after a prior promotion run
- **WHEN** a session gains new findings (e.g. the interview is resumed) after an earlier promotion run
- **THEN** only the new, not-yet-promoted findings are offered on the next promotion run

### Requirement: Unpromoted findings remain reachable
The system SHALL NOT require every finding to be promoted, and a finding that is not promoted to any target store SHALL remain fully present and reachable via the anamnesis interview's existing plain-Markdown review export.

#### Scenario: A finding has no applicable promotion target
- **WHEN** a finding does not map to any of the four target stores under the current mapping (e.g. a hobby finding with no plausible pathogen-relevant slug)
- **THEN** the finding is not offered for promotion, and continues to appear in the plain-Markdown review export unaffected
