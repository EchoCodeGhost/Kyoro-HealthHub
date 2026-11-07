## ADDED Requirements

### Requirement: Analysis stays in the hub
The app SHALL capture data, guide the user and show results. It SHALL NOT compute clinical metrics or run analyses itself.

#### Scenario: Derived metric needed
- **WHEN** a screen needs a derived metric such as an HRV trend or a PEM pattern
- **THEN** the app shows the value computed by the hub, or says that it is not available yet

### Requirement: Suggestions explain themselves
The Today screen SHALL show at most three suggestions. Every suggestion SHALL state why it appears and offer exactly one action.

#### Scenario: Many rules apply
- **WHEN** more than three suggestion rules apply
- **THEN** only the three with the highest priority are shown

#### Scenario: Suggestion shown
- **WHEN** a suggestion is displayed
- **THEN** its reason is visible without further interaction

### Requirement: Permissions are explained before they are requested
The app SHALL explain each Apple Health data group with its purpose before the system dialog appears. Declining SHALL NOT block any other function.

#### Scenario: User declines Apple Health
- **WHEN** the user skips the Apple Health step
- **THEN** onboarding completes and the Today screen offers the permission later as a suggestion

### Requirement: Phone data uses a format the hub already imports
Exports from the app SHALL use the SymptomTrack JSON format read by `import_symptomtrack_export.py`, with symptom keys from `config/symptom_map.json`.

#### Scenario: Export dropped into the inbox
- **WHEN** a file named `symptomtrack_export_<date>.json` is placed in `imports/_inbox/`
- **THEN** `process_inbox.py` routes it to `import_symptomtrack_export.py`

### Requirement: No feature pretends to work
A function that depends on a missing part (such as the hub bridge) SHALL say so and offer the manual alternative, instead of showing a control that does nothing.

#### Scenario: Doctor export without a paired hub
- **WHEN** the user picks a specialty in the Doctor tab and no hub is paired
- **THEN** the app shows the matching `export_health.py` command to run on the computer
