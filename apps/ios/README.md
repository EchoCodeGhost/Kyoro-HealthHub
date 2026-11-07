# Kyoro for iPhone (development branch)

> **Deutsche Version:** [README_DE.md](README_DE.md)

Native iPhone app that makes Kyoro easy, guided and integrated: quick capture,
Apple Health, widgets and Siri, with the Kyoro pipeline running in embedded
Python on the iPhone or iPad itself. A computer running the hub is optional. Plan and research:
`openspec/changes/add-ios-companion-app/`.

> Not part of a release. Like `mobile/` and `pwa/`, this app needs a full privacy
> sweep before it ships. Not a medical device; see [NOTICE](../../NOTICE).

## What works in this skeleton

- Five tabs: Today, Capture, History, Doctor, More
- Four-step onboarding (goals, Apple Health permissions with reasons, daily reminder)
- Rule-based suggestions on Today, at most three, each with its reason
- Symptom capture in two taps; interactive widget and Siri shortcut "Symptom erfassen"
- Guided standing test (Schellong / NASA Lean Test) with checklist and timers
- Export of entries as `symptomtrack_export_<date>.json`, which `scripts/process_inbox.py`
  recognises and imports
- Doctor tab: pick a specialty (on-device export follows with embedded Python)

Not yet: pipeline in embedded Python (proof of concept in `apps/ios-python-poc`), optional hub bridge, autopilot, HealthKit data reading beyond the
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
