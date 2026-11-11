## 1. Skeleton (this branch)

- [x] 1.1 XcodeGen project with app, widget extension and test target
- [x] 1.2 Design tokens from the Kyoro logo and the no-slop checklist
- [x] 1.3 Tabs, onboarding wizard, shared wizard scaffold
- [x] 1.4 Rule-based suggestion engine with tests
- [x] 1.5 Symptom capture, interactive widget, Siri / Shortcuts intent
- [x] 1.6 Guided standing test from `docs/test_protocols/ORTHOSTATIC_TEST_PROTOCOL_DE.md`
- [x] 1.7 Export in SymptomTrack JSON format; `process_inbox.py` recognises it (tests)
- [ ] 1.8 First build and run on Xcode 26, simulator and a device

## 2. Capture and HealthKit

- [ ] 2.1 Read HealthKit groups with anchored queries and background delivery
- [ ] 2.2 Package format for HealthKit data that an existing importer reads (check `import_apple.py`)
- [ ] 2.3 Store protocol measurements and export them for the matching importer
- [ ] 2.4 Resume paused wizards with their input
- [ ] 2.5 Free-text capture with the on-device model, always confirmed by the user

## 3. Hub bridge

- [ ] 3.1 Bridge service using `scripts/tui/runner.py` and `scripts/tui/manifests.py`
- [ ] 3.2 QR pairing, device token in Keychain, revoke from the hub
- [ ] 3.3 Inbox upload and autopilot job with plain-language status
- [ ] 3.4 Results: findings and plots for the History tab
- [ ] 3.5 Doctor tab runs `export_health.py` through the bridge and shares the result

## 4. Integration

- [ ] 4.1 Live Activity for timed protocols
- [ ] 4.2 Notification when the autopilot finished
- [ ] 4.3 App icon from the octopus head, layered for Icon Composer
- [ ] 4.4 Lab report scan with Vision document recognition and a confirm step
- [ ] 4.5 Live Text reading for measuring devices without an export
- [ ] 4.6 Foundation Models mapping of OCR and free text, with rule-based fallback

## 4b. Embedded pipeline spike

- [x] 4b.1 Static import check and in-process smoke test on desktop
- [x] 4b.2 Simulator run of apps/ios-python-poc (size, start, timings)
- [ ] 4b.3 Device run with signing, and size of a SwiftUI shell that embeds only the Python framework
- [ ] 4b.4 Decide direction based on the measurements

## 4c. Help at critical steps (see "Kyoro-App: Wo Nutzer Hilfe brauchen")

- [ ] 4c.1 Persist wizard state (step and values) and resume
- [ ] 4c.2 Health source detection screen and "no Health data" suggestion
- [ ] 4c.3 Data-quantity states instead of empty charts
- [ ] 4c.4 Error pattern: one sentence, one fix, collapsed details
- [ ] 4c.5 Low-energy capture: bad-day action, "wie gestern", backfill yesterday
- [ ] 4c.6 Severity anchors on the scale
- [ ] 4c.7 Doctor wizard: specialty question, default period, preview before sharing
- [ ] 4c.8 Automatic encrypted backup to iCloud Drive, restore detection on first launch
- [ ] 4c.10 Threshold table for notable and urgent values, reviewed by a physician
- [ ] 4c.11 Regulatory assessment of the safety net (EU MDR rule 11) before release
- [ ] 4c.12 Accessibility pass at the largest text size, VoiceOver and Switch Control; test with affected users
- [ ] 4c.13 Data location page in setup
- [ ] 4c.9 "Ask someone for help" report without health data

## 4d. Alignment with Kyoro SymptomTrack (KiSTe)

- [x] 4d.1 Importer keeps iPhone entries under source kyoro_ios, highest value per day
- [x] 4d.2 Read the KiSTe code (private repo history) and record what the app adopts
- [x] 4d.3a Symptom catalogue released by Michel, now config/symptom_catalog.json (37 modules, 256 symptoms, test)
- [x] 4d.3b App loads the catalogue from the bundle; module choice in setup replaces the 8 fixed quick picks
- [ ] 4d.3c PWA backend reads config/symptom_catalog.json instead of its own copy
- [x] 4d.4 Entry types binary, scale, inverted scale, text with type-specific anchors
- [ ] 4d.5 Body map, photo and batch save in Capture (backdated time done)
- [ ] 4d.6 Migraine and AFib episodes in the app, and an importer path for them
- [x] 4d.7 Crisis notice (112 and crisis lines) shown unconditionally while a module with requires_crisis_notice is active
- [ ] 4d.8 Include kyoro_ios rows in compute_histamine_triggers.py
- [ ] 4d.9 Importer: for scale_inverted symptoms (energy, mood) "highest value per day" keeps the best value; decide whether the lowest should win there, and how repeated text entries resolve
- [ ] 4d.10 Build the app on the Mac (the Swift of 4d.3b/4d.4/4d.7 has not been compiled yet)
- [ ] 4d.11 Check the catalogue against the S1 guideline Long/Post-COVID (AWMF 020-027, check the current version first): add "Konzentration und Gedächtnis" to the basics and swallowing/voice problems; pacing help text in own words with the guideline as dated source. No criteria, scores or referral rules from it (MDR)

## 5. Release gate

- [ ] 5.1 Privacy sweep of the app and the bridge
- [ ] 5.2 Accessibility pass (Dynamic Type, VoiceOver, Reduce Motion)
