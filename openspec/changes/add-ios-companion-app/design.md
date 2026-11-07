## Context

The hub is local-first Python with a fixed stage order (`import_all.py` → `compute_all.py` → `analyse_all.py`) and an existing operating layer, the pipeline TUI (`scripts/tui/`). The TUI already solves job locking, flag allowlisting and remote-LLM consent. The phone app should reuse those decisions instead of creating a second pipeline path.

## Goals / Non-Goals

**Goals:** easy capture in two taps; guided flows for everything manual; one autopilot job for everything automatic; data stays on the phone and the user's own computer.

**Non-goals:** running analyses on the phone; a cloud backend; Android in this change; diagnosis or treatment advice.

## Decisions

- **Native SwiftUI instead of a cross-platform framework.** Widgets, Live Activities, App Intents and HealthKit background delivery are the core of "integrated" and are first-class only natively. Android can follow later against the same bridge.
- **iOS 26 minimum.** Liquid Glass from system components, Foundation Models for on-device text understanding, current Tab API; avoids compatibility code.
- **SymptomTrack JSON as the transfer format.** `import_symptomtrack_export.py` already reads it, so the hub needs only an inbox rule. Known limit: the importer keeps the first entry per symptom and day (`INSERT OR IGNORE`); a later change may keep the highest value as `import_kyoro_symptoms.py` does.
- **Bridge reuses the TUI runner and manifests.** One job at a time, argument lists only, the same allowlist. A remote LLM run requires consent per run, shown in the app.
- **Pairing by QR code shown on the hub.** The code carries the bridge address and a one-time secret; the phone stores a device token in the Keychain. Reachable in the home network or through a VPN the user already runs.
- **Suggestions are rule-based and explain themselves.** At most three cards; each states why it appears. No LLM decides what the user should do.
- **Design tokens from the logo** in one file (`KyoroTheme.swift`); colour only as accent, status never by colour alone.

## Risks / Trade-offs

- An app makes it easier to start a remote-LLM run casually → consent per run, provider always visible, default off.
- HealthKit data volume can be large → background delivery with anchored queries, sent in daily packages.
- Bridge exposes the pipeline on the network → bound to the paired device token, TLS, no endpoint that runs arbitrary scripts, nothing outside the manifest allowlist.
