# Kyoro for iPhone (development branch)

> **Deutsche Version:** [README_DE.md](README_DE.md)

Native iPhone app that makes Kyoro easy, guided and integrated: quick capture,
Apple Health, widgets and Siri on the phone, while the analysis keeps running in
the Python hub on your own computer. Plan and research:
`openspec/changes/add-ios-companion-app/`.

> Not part of a release. Like `mobile/` and `pwa/`, this app needs a full privacy
> sweep before it ships. Not a medical device; see [NOTICE](../../NOTICE).

## What works in this skeleton

- Five tabs: Today, Capture, History, Doctor, More
- Five-step onboarding (goals, Apple Health permissions with reasons, daily reminder)
- Rule-based suggestions on Today, at most three, each with its reason
- Symptom capture in two taps from the shared catalogue (config/symptom_catalog.json); modules chosen in setup and under "Mehr"; yes/no, 0-10 and text entries with backdating; interactive widget with the four most used symptoms and Siri shortcut "Symptom erfassen"; crisis numbers shown while the Suizidalität module is active
- Guided standing test (Schellong / NASA Lean Test) with checklist and timers
- Export of entries as `symptomtrack_export_<date>.json`, which `scripts/process_inbox.py`
  recognises and imports
- Doctor tab: pick a specialty, get the matching `export_health.py` command

Not yet: hub bridge and pairing, autopilot, HealthKit data reading beyond the
permission request, storing protocol measurements, resuming paused flows.

## Build

Requires Xcode 26 and [XcodeGen](https://github.com/yonaskolb/XcodeGen).

```bash
cd apps/ios
xcodegen generate
open Kyoro.xcodeproj
```

Set your own development team in Xcode. HealthKit and App Groups need a paid
developer account on a real device; the simulator works without.

## Rules for every change

- Colours, spacing and radii only from `Kyoro/DesignSystem/KyoroTheme.swift`
  (palette taken from the Kyoro logo).
- Run the [no-slop check](NO_SLOP.md) at the end of every step.
