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

### Requirement: Encrypted backup the user places
The app SHALL create an encrypted backup of its own database and SHALL NOT write health data to iCloud by itself (App Review Guideline 5.1.3(ii)). The user chooses the location once through the Files picker (on the device, a USB drive, the paired hub, or a cloud folder of their choice). The app SHALL remind the user when the last backup is older than seven days, SHALL show the time of the last backup, and SHALL offer to restore a backup on first launch with an empty database.

#### Scenario: First backup
- **WHEN** the user has logged entries on three days and no backup location is set
- **THEN** the Today screen shows one suggestion to choose a backup location, with the reason that deleting the app deletes its data

#### Scenario: Paired hub
- **WHEN** a hub is paired and reachable
- **THEN** the app writes the encrypted backup to the hub after each autopilot run without asking again

#### Scenario: New iPhone
- **WHEN** the app starts with an empty database
- **THEN** it offers "Sicherung wiederherstellen" with the Files picker and "Neu beginnen", and shows backup date, source device and day count before restoring

#### Scenario: Backup overdue
- **WHEN** the last backup is older than seven days
- **THEN** the Today screen shows a suggestion with the date of the last backup and one action that writes a new one

#### Scenario: Backup key
- **WHEN** the first backup is written
- **THEN** the key is stored in the Keychain and the app shows a recovery code once and offers to save it in the Passwords app

### Requirement: Intended purpose is documentation
Kyoro SHALL be a diary for collecting, organising and sharing the user's own health data with their doctor. It SHALL NOT rate values, detect conditions or warn based on values (EU MDR, MDCG 2019-11 rule 11). App texts, App Store text and help SHALL NOT use the words erkennen, warnen, screenen, Diagnose or name a test as a test for a condition.

#### Scenario: New screen copy
- **WHEN** a screen, suggestion or export text is added
- **THEN** it describes what was recorded or how values changed, and passes the wording check in `apps/ios/NO_SLOP.md`

#### Scenario: Hub analysis with a rating
- **WHEN** a hub or on-device analysis produces a classification such as an arrhythmia tier, an AFib or ectopy flag, or an orthostatic rating
- **THEN** the app does not show or export that classification

### Requirement: Values the lab marked and a fixed emergency hint
The app SHALL show the markings that a lab report itself carries (H, L, reference range) next to scanned values, labelled as the lab's marking. It SHALL NOT keep its own threshold table. Every result screen and the More tab SHALL carry the same fixed sentence that does not depend on any value: "Kyoro ist kein Notdienst. Bei Brustschmerz, Atemnot, Lähmung oder Bewusstlosigkeit: 112."

#### Scenario: Scanned value outside the lab's reference range
- **WHEN** a confirmed lab value lies outside the reference range printed on the report
- **THEN** the app shows the lab's marking and range as printed, and adds nothing of its own

#### Scenario: Report without reference range
- **WHEN** the report gives no reference range for a value
- **THEN** the app shows the value without any marking

### Requirement: Standing test records, it does not rate
The guided standing test SHALL record heart rate and, if entered, blood pressure at each measuring point, symptoms and an abort, and SHALL show the values and the difference to the lying value. It SHALL NOT label the result as notable, normal or abnormal.

#### Scenario: Large heart rate increase
- **WHEN** heart rate rises by 34 per minute after standing up
- **THEN** the result screen shows lying and standing values and "Anstieg: 34 pro Minute", and offers to add the protocol to the doctor report, without a rating

#### Scenario: Test aborted
- **WHEN** the user taps "Abbrechen und hinsetzen"
- **THEN** the abort and its time are stored as a result and appear in the doctor report

### Requirement: Accessible under cognitive fatigue
Every screen SHALL support Dynamic Type up to the largest accessibility size without truncation, VoiceOver labels for all controls, chart summaries for VoiceOver, touch targets of at least 44 points, no time limits, Reduce Motion, and meaning that never relies on colour alone. Every text field SHALL accept dictation.

#### Scenario: Largest text size
- **WHEN** the user selects the largest accessibility text size
- **THEN** every screen reflows without cut-off text and all actions stay reachable

### Requirement: Explain where data lives during setup
Setup SHALL show, before the Apple Health request, where data is stored (on the device, in the encrypted backup at the place the user chooses, nowhere else) and which actions send data off the device, and SHALL state that Kyoro is neither a medical device nor an emergency service.

#### Scenario: Setup
- **WHEN** the user reaches the Apple Health step in setup
- **THEN** the data location page has been shown before it
