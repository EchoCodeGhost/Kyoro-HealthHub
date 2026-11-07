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

### Requirement: Wizards resume where the user left
Every multi-step wizard SHALL persist its current step and entered values, so that closing it and opening it again continues at the same step.

#### Scenario: Wizard closed mid-way
- **WHEN** the user closes a wizard at step 2 of 4 and opens it again later
- **THEN** it opens at step 2 with the values entered before

### Requirement: Detect connected sources from Apple Health
The app SHALL list which apps write data to Apple Health, state per app which Kyoro data types arrive automatically, and offer the export path only for data types that do not.

#### Scenario: App writes only some types
- **WHEN** an app writes steps and heart rate but no HRV to Apple Health
- **THEN** it is listed as running for steps and heart rate, with one action to set up the export for HRV

#### Scenario: No Health data after access was requested
- **WHEN** a day has passed since Health access was requested and no samples were read
- **THEN** a suggestion explains how to grant read access in the Settings app

### Requirement: Honest about data quantity
A screen that needs more data than is available SHALL state what is missing and how to get it. It SHALL NOT show placeholder charts or example values.

#### Scenario: Trend needs seven days
- **WHEN** a trend needs seven days of values and three exist
- **THEN** the screen says that four more days are needed and which source provides them

### Requirement: Errors offer one fix
Every error shown to the user SHALL name the problem in one plain sentence and offer one action that resolves it; technical details SHALL be collapsed by default.

#### Scenario: Wrong export file shared
- **WHEN** the user shares a CSV where the importer needs the full ZIP export
- **THEN** the app names the expected file and opens the export guide for that app

### Requirement: Low-energy capture
The app SHALL allow logging a symptom in one interaction from the widget, Siri or the Capture tab, with severity and time filled in by default.

#### Scenario: Bad day
- **WHEN** the user taps the bad-day action in the widget
- **THEN** an entry is stored without any further question and can be edited later

### Requirement: Confirm recognised values
Values recognised from scans, camera or free text SHALL be stored only after the user confirmed them; uncertain values SHALL be listed first next to the image region they were read from.

#### Scenario: Lab report scanned
- **WHEN** a lab report is scanned and three values are uncertain
- **THEN** the review screen lists those three first with the source crop, and nothing is saved before the user confirms

### Requirement: Backup reminder
The app SHALL suggest creating an encrypted backup file once a month while no backup exists from the last 30 days.

#### Scenario: No recent backup
- **WHEN** 30 days passed since the last backup file was created
- **THEN** the Today screen shows a backup suggestion with its reason
