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
    du -sh build/kyoro_poc/ios/xcode/build/Debug-iphonesimulator/*.app

Results appear on screen and in the log with the prefix `KYORO_POC`.
For a real device, open the generated Xcode project
(`briefcase open iOS`), set a signing team and run it from Xcode.

## What to record

| Measure | Simulator | Device |
|---|---|---|
| App size (.app) | | |
| Cold start to UI ready | | |
| Datenbank anlegen | | |
| Import Symptome | | |
| Berechnen Symptome | | |
| Errors | | |
