## Why

Kyoro's value sits in a pipeline that needs dozens of commands, a fixed stage order and a terminal. That is a barrier on low-energy days and for anyone who did not write the pipeline. Most data also starts on the phone (symptoms, Apple Watch, test protocols), but reaches the hub only through manual exports. A native iPhone app can make the existing functions easy, guided and integrated, and can make the nested import, compute and analyse chain run without the user assembling it.

## What Changes

- New native iPhone app under `apps/ios/` (SwiftUI, iOS 26, Swift 6, XcodeGen). It is an operating and capture layer: analysis stays in the Python hub.
- Five tabs (Today, Capture, History, Doctor, More), a five-step onboarding, rule-based suggestions with a stated reason, and guided wizards for the home test protocols in `docs/test_protocols/`.
- System integration: interactive widget, App Intents for Siri and Shortcuts, later Live Activities for timed protocols and HealthKit background delivery.
- Phone data reaches the hub in the existing SymptomTrack JSON format, so no new importer is needed. `process_inbox.py` now recognises `symptomtrack_export_*.json` and files with a `symptom_entries` key.
- Planned hub bridge: a small paired HTTP service that reuses the TUI job runner and manifests to run one autopilot job (inbox import, compute, analyse) and to return plain-language status. Specified here, not built in this change's first step.
- Visual language from the Kyoro logo, plus a no-slop checklist (`apps/ios/NO_SLOP.md`) applied to every step.

## Capabilities

### New Capabilities
- `ios-companion-app`: iPhone app for capture, guidance, suggestions and system integration.
- `hub-bridge`: paired local service through which the app starts pipeline jobs and reads results.

### Modified Capabilities
- `pipeline-architecture`: inbox routing for SymptomTrack JSON exports.

## Impact

- **New code:** `apps/ios/` (app, widget extension, tests). Generated Xcode project is not checked in.
- **Changed code:** `scripts/process_inbox.py` (JSON sniffing and handler), `tests/unit/test_process_inbox_sniffing.py`.
- **Release:** excluded from releases until a privacy sweep, like `mobile/` and `pwa/`.
- **Regulatory scope:** unchanged. Private use only; no diagnosis; AI output labelled.
