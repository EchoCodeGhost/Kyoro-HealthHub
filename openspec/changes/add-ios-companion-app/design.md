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

### Spike: pipeline in embedded Python (2026-11-07, direction pending)

Static import check: 72 of 80 importers and 22 of 28 compute scripts need no
third-party package at module level. In an empty venv, 66 importers and 21
compute modules import cleanly, and `importers/import_symptomtrack_export.py`
plus `compute/compute_symptoms.py` run in-process against a fresh database
(apps/ios-python-poc). Blockers for iOS: subprocess orchestration in
import_all/compute_all/analyse_all, and sqlcipher3 (replaced on iOS by Data
Protection). Proposed split: Python on device for import and compute, Swift
Charts for plots, scipy/statsmodels analyses on the optional hub. Device
measurements are open.

### On-device intelligence

- Vision document recognition (iOS 26, every device) reads lab reports
  including table structure; VisionKit Live Text reads displays of measuring
  devices without an export.
- Foundation Models (Apple Intelligence devices only) maps OCR text and
  free text or speech to structured fields with guided generation.
- Every recognised value goes through a confirmation step. The model never
  derives medical values; computation stays in the pipeline. Devices without
  Apple Intelligence fall back to OCR plus fixed rules.
- Nothing leaves the device, so the remote-LLM consent flow does not apply.

### Relation to Kyoro SymptomTrack (KiSTe)

Kyoro SymptomTrack, short KiSTe, is the existing symptom-tracking PWA with
its own backend. Its code lives in the history of the private repository
(pwa/, tools/KST-PWA/), untracked since July pending consolidation and a
privacy review. The hub reads it through `import_symptomtrack_export.py`
(JSON) and `import_kyoro_symptoms.py` (CSV, source `kyoro_st`).

- The iPhone app writes the same JSON format. Its entries carry
  `source: kyoro_ios`; the importer stores them under that source so they
  never collide with PWA rows of the same day, and several entries per day
  resolve to the highest value.
- Symptom catalogue: 37 modules with 256 symptoms, five preselected,
  released by Michel on 2026-11-10 and kept in `config/symptom_catalog.json`
  as the single list for PWA, app and hub. The app adopts the
  module model instead of a fixed quick-pick list; setup selects modules.
  Symptom labels stay identical to the PWA, because they are the `symptom`
  value in health.db.
- Entry types: binary, scale 0 to 10, inverted scale (high is good) and
  text. Scale anchors depend on the type.
- Capture flow: category, search, value, body region on a body map,
  backdated time, photo, note, and a batch ("Stapel") that saves several
  symptoms at once.
- Migraine and AFib episodes (start, end, aura or heart rate, medication,
  intake time). The importer skips them today.
- Crisis banner with 112 and the German crisis lines while the suicidality
  module is active.
- The PWA stays the path for Android, web and the shared family server.
- `compute_histamine_triggers.py` reads only `source = 'kyoro_st'` rows
  with timestamps. iPhone entries must be included there as well.
- `mobile/KyoroVitalGuard` (Android, Polar BLE presyncope warning, untested
  on hardware) is out of scope for version 1; an iOS port via the Polar
  BLE SDK is a later candidate.

## Risks / Trade-offs

- An app makes it easier to start a remote-LLM run casually → consent per run, provider always visible, default off.
- HealthKit data volume can be large → background delivery with anchored queries, sent in daily packages.
- Bridge exposes the pipeline on the network → bound to the paired device token, TLS, no endpoint that runs arbitrary scripts, nothing outside the manifest allowlist.
