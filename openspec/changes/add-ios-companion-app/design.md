## Context

The hub is local-first Python with a fixed stage order (`import_all.py` → `compute_all.py` → `analyse_all.py`) and an existing operating layer, the pipeline TUI (`scripts/tui/`). The TUI already solves job locking, flag allowlisting and remote-LLM consent. The phone app reuses those decisions and the same Python code instead of creating a second pipeline.

## Goals / Non-Goals

**Goals:** the app works on an iPhone or iPad alone, without a computer; easy capture in two taps; guided flows for everything manual; one autopilot job for everything automatic; data stays on the device and, if paired, on the user's own computer.

**Non-goals:** requiring a computer; a cloud backend; Android in this change; diagnosis or treatment advice; rating values or warning based on values.

## Decisions

- **Native SwiftUI instead of a cross-platform framework.** Widgets, Live Activities, App Intents and HealthKit background delivery are the core of "integrated" and are first-class only natively. Android can follow later against the same bridge.
- **iOS 26 minimum.** Liquid Glass from system components, Foundation Models for on-device text understanding, current Tab API; avoids compatibility code.
- **SymptomTrack JSON as the transfer format.** `import_symptomtrack_export.py` already reads it, so the hub needs only an inbox rule. Known limit: the importer keeps the first entry per symptom and day (`INSERT OR IGNORE`); a later change may keep the highest value as `import_kyoro_symptoms.py` does.
- **Bridge reuses the TUI runner and manifests.** One job at a time, argument lists only, the same allowlist. A remote LLM run requires consent per run, shown in the app.
- **Pairing by QR code shown on the hub.** The code carries the bridge address and a one-time secret; the phone stores a device token in the Keychain. Reachable in the home network or through a VPN the user already runs.
- **Suggestions are rule-based and explain themselves.** At most three cards; each states why it appears. No LLM decides what the user should do.
- **Design tokens from the logo** in one file (`KyoroTheme.swift`); colour only as accent, status never by colour alone.

### Direction: iPhone alone, hub optional (decided 2026-11-07)

Michel decided on 2026-11-07 that the app runs on its own. Import and
compute run in embedded Python on the device, plots are drawn with Swift
Charts from structured analysis output, and the hub is an optional upgrade
for the analyses that need scipy or statsmodels, for automatic Garmin
download, and as a backup target. Version 1 targets one person and one
leading device.

### Spike: pipeline in embedded Python (2026-11-07)

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
- On-device intelligence sends nothing off the device. Remote LLM providers are not part of version 1; if added later, they use the per-run consent flow.

### Relation to Kyoro SymptomTrack (KiSTe)

Kyoro SymptomTrack, short KiSTe, is the existing symptom-tracking PWA with
its own backend (shared-access server, `/api/export`). Its code is not in
this repository. The hub reads it through `import_symptomtrack_export.py`
(JSON) and `import_kyoro_symptoms.py` (CSV, source `kyoro_st`).

- The iPhone app writes the same JSON format, so no new importer is needed.
  Its entries carry `source: kyoro_ios`; the importer stores them under
  that source so they never collide with PWA rows of the same day, and
  several entries per day resolve to the highest value.
- The PWA stays the path for Android, web and the shared family server.
  The iPhone app is the native, offline path for iPhone and iPad users.
- To take over from KiSTe: body region per entry, migraine and AFib
  episodes (start, end, triggers; the importer skips these today), the
  symptom catalogue and wording.
- `compute_histamine_triggers.py` reads only `source = 'kyoro_st'` rows
  with timestamps. iPhone entries must be included there as well.

### Regulatory scope (research 2026-11-07)

The research doc "Kyoro iPhone-App: Recht und Technik geprüft" found that
value-bound warnings, a standing-test rating and arrhythmia tiers are very
likely medical device software under MDCG 2019-11 (class IIa to IIb), while
capture, display and an uninterpreted doctor export are not. Version 1
therefore documents and does not rate: the lab's own markings, a fixed
emergency sentence, and a standing test that shows values and the difference.
Classifications from hub or on-device analyses are filtered out of the app
and its exports. User-logged episodes (migraine, AFib as a diary entry) stay,
because the user records them.

App Review Guideline 5.1.3(ii) says apps "may not store personal health
information in iCloud". The backup is therefore encrypted and written to a
place the user picks, or to the paired hub; Kyoro does not write to iCloud
by itself. Apple is asked before the first submission whether an end-to-end
encrypted iCloud backup is acceptable.

### Doctor export as an interface (research 2026-11-07)

A direct API to practice software or the ePA is not part of version 1.
Writing into the ePA is open to the insured person through the insurer's
ePA app, to providers, insurers, the e-prescription server and, by opt-in,
to DiGA (§ 6a DiGAV); a DiGA must be a CE-marked medical device, which
conflicts with the documentation-only scope. Practice software has no
general import interface for patient data; the KBV archive and change
interface (FHIR, § 371 SGB V) moves data between practice systems. Version 1
therefore exports a PDF and a FHIR R4 bundle through the share sheet and
explains the upload into the ePA app. A Kyoro server or API would make the
project a controller for health data under GDPR Art. 9, and claiming
interoperability with an EHR system would require the EHDS wellness label
(Regulation (EU) 2025/327, Art. 47).

## Risks / Trade-offs

- An app makes it easier to start a remote-LLM run casually → consent per run, provider always visible, default off.
- HealthKit data volume can be large → background delivery with anchored queries, sent in daily packages.
- Bridge exposes the pipeline on the network → bound to the paired device token, TLS, no endpoint that runs arbitrary scripts, nothing outside the manifest allowlist.
