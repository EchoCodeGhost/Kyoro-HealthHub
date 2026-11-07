# Kyoro PoC: pipeline in embedded Python on iOS

Answers one question: does unchanged Kyoro pipeline code run in-process in
CPython on an iPhone, and at what cost (time, app size)?

The app copies `scripts/` as-is, creates a fresh `health.db` in the app
container, imports a 30-day symptom export with
`importers/import_symptomtrack_export.py` and runs
`compute/compute_symptoms.py`. No subprocess, no third-party packages,
no SQLCipher (iOS Data Protection covers encryption at rest).

## Desktop baseline (any OS, plain Python 3.13, empty venv)

    python3 -m venv --without-pip /tmp/kyoro-clean
    cd src && /tmp/kyoro-clean/bin/python -m kyoro_poc.smoke ../../../scripts

## iOS (Mac with Xcode 26)

    python3 -m venv .venv && . .venv/bin/activate
    pip install briefcase
    ./prepare.sh
    briefcase create iOS
    briefcase build iOS
    briefcase run iOS            # pick a simulator; tap "Test starten"

Where nothing can tap the button (Xcode 27 `simctl` cannot), start the app
with `KYORO_POC_AUTORUN=1` in its environment, for example
`SIMCTL_CHILD_KYORO_POC_AUTORUN=1 xcrun simctl launch --console booted org.kyoro.kyoro-poc`.
    du -sh build/kyoro_poc/ios/xcode/build/Debug-iphonesimulator/*.app

Results appear on screen and in the log with the prefix `KYORO_POC`.
For a real device, open the generated Xcode project
(`briefcase open iOS`), set a signing team and run it from Xcode.

## Results

First run 2026-11-07 on a Mac: Xcode 27.2, iPhone 17 simulator with iOS 27.0,
Python 3.13, Briefcase 0.4.7, toga-iOS 0.5.7. Medians of 5 runs.

| Measure | Simulator | Device |
|---|---|---|
| App size (.app) | 97 MB: python/ 50, Frameworks/ 27, app/ 11, app_packages/ 7.4 (fontTools 5.3) | open |
| Cold start to UI ready | 1014 ms (800 to 1286); 4175 ms on the first start after simulator boot | open |
| Datenbank anlegen | 71 ms | open |
| Import Symptome | 49 ms (30 rows) | open |
| Berechnen Symptome | 21 ms | open |
| Total incl. module load | 160 ms | open |

Desktop baseline in an empty venv: 143 to 347 ms total. After the first
(cold cache) run the simulator is on par with the desktop.

Fixed after the first run: `config/` was missing from the bundle
(compute_symptoms.py reads scripts/../config/symptom_map.json), timings of
finished steps were lost on a failure, and identity.db plus the registries
ignored `KYORO_ACTIVE_PATIENT_DIR` and landed in the real home directory.

Most of the size is Toga, its frameworks and an unpruned standard library.
The real app is SwiftUI and embeds only the Python framework, so Frameworks/
and app_packages/ drop out and the standard library can be trimmed.
