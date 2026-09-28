#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Manuelle Verifikation: Forschungs-Kohorten-Export

@tier        test
@purpose.de  Testet den Forschungs-Kohorten-Export mit 3 Dummy-Patient:innen.
             Verifiziert Einwilligungsprüfung, Datumsverschiebung, k-Anonymität.
@purpose.en  Tests research cohort export with 3 dummy patients. Verifies consent
             checking, date shifting, k-anonymity.
@method.de   Erstellt 3 Test-Patient:innen, erteilt selektiv Einwilligungen,
             führt Export durch und prüft Ergebnisse.
@method.en  Creates 3 test patients, grants selective consents, runs export,
             and verifies results.
@usage
    python3 tests/manual/test_research_cohort.py   # ausführen aus dem Repo-Root
"""
import os
import sys
import sqlite3
import subprocess
import tempfile
import json
from pathlib import Path

_REPO_ROOT = Path(__file__).parent.parent.parent

# Isolation: HOME auf ein temporäres Verzeichnis umbiegen
_TEST_HOME = tempfile.mkdtemp(prefix="kyoro_research_test_")
os.environ["HOME"] = _TEST_HOME

# Minimale health_config.json anlegen
import json as _json
test_kyoro_dir = Path(_TEST_HOME) / ".config" / "kyoro"
test_kyoro_dir.mkdir(parents=True, exist_ok=True)
(test_kyoro_dir / "health_config.json").write_text(
    _json.dumps({"user": {"name": "Test Operator"}}), encoding="utf-8"
)

sys.path.insert(0, str(_REPO_ROOT / "scripts"))

# Master-DB Schema erstellen
from utils.create_master_schema import create_or_upgrade
create_or_upgrade()

# Test-Personen erstellen
from utils.manage.shared_access.manage_people import cmd_add as add_patient
from utils.manage.shared_access.manage_access_grants import cmd_grant as grant_consent, cmd_revoke as revoke_consent

class Args:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

def _provision_instance(pseudo: str) -> None:
    """Legt health_config.json an und initialisiert health.db fuer eine
    Dummy-Instanz.

    NICHT ueber scripts/utils/init_db.py -- das Skript hat einen eigenen,
    von diesem Change unabhaengigen Bug gefunden: `db_path = ROOT / "data"
    / "health.db"` (init_db.py Zeile ~78) ist hart auf den Repo-Root
    verdrahtet und ignoriert Config().db_path / KYORO_ACTIVE_PATIENT_DIR
    komplett. Ausgefuehrt "wie dokumentiert" (siehe manage_patients.py's
    eigener Hinweistext "python3 onboard.py in <instance_dir> ausfuehren
    mit KYORO_ACTIVE_PATIENT_DIR=<instance_dir>") wuerde das still gegen
    die ECHTE Repo-`data/health.db` laufen (dort meist schon vorhanden ->
    "nothing to do", exit 0 -- taeuscht Erfolg vor, ohne die Instanz
    tatsaechlich zu initialisieren). Nicht Teil dieses Changes zu fixen,
    hier nur umgangen: Schema direkt gegen den korrekten Instanz-Pfad
    anlegen, unabhaengig von init_db.py.
    """
    instance_dir = Path(_TEST_HOME) / ".config" / "kyoro-master" / "patients" / pseudo
    config_dir = instance_dir / ".config" / "kyoro"
    config_dir.mkdir(parents=True, exist_ok=True)
    (instance_dir / "data").mkdir(parents=True, exist_ok=True)
    db_path = instance_dir / "data" / "health.db"
    (config_dir / "health_config.json").write_text(_json.dumps({
        "user": {"name": f"Test {pseudo}", "timezone": "Europe/Berlin"},
        "paths": {"db": str(db_path)},
    }), encoding="utf-8")

    sys.path.insert(0, str(_REPO_ROOT / "scripts"))
    from utils.create_schema import SCHEMA
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()


print("=== Test Setup: 3 Dummy-Patient:innen erstellen ===")

# Patient 1
args1 = Args(person_number="TEST001", group_id="test-group")
add_patient(args1)
pseudo1 = "PT-" + __import__('hashlib').sha256(("TEST001test-group").encode()).hexdigest()[:8].upper()
_provision_instance(pseudo1)
print(f"Patient 1: {pseudo1}")

# Patient 2
args2 = Args(person_number="TEST002", group_id="test-group")
add_patient(args2)
pseudo2 = "PT-" + __import__('hashlib').sha256(("TEST002test-group").encode()).hexdigest()[:8].upper()
_provision_instance(pseudo2)
print(f"Patient 2: {pseudo2}")

# Patient 3
args3 = Args(person_number="TEST003", group_id="test-group")
add_patient(args3)
pseudo3 = "PT-" + __import__('hashlib').sha256(("TEST003test-group").encode()).hexdigest()[:8].upper()
_provision_instance(pseudo3)
print(f"Patient 3: {pseudo3}")

print("\n=== Test 1: Export ohne Einwilligungen (sollte fehlschlagen) ===")

# Einwilligungen für nur 2 von 3 Patienten erteilen
consent_args1 = Args(person=pseudo1, scope="test-study", notes="")
grant_consent(consent_args1)

consent_args2 = Args(person=pseudo2, scope="test-study", notes="")
grant_consent(consent_args2)

# Patient 3 bekommt KEINE Einwilligung

# Export versuchen
result = subprocess.run([
    sys.executable, "scripts/exporters/export_research_cohort.py",
    "--scope", "test-study",
    "--profile", "research",
    "--quasi-identifiers", "gender",
    "--k", "5"
], capture_output=True, text=True)

if result.returncode != 0 and "ABBRUCH" in result.stdout:
    print("✅ Test 1 bestanden: Export abgelehnt wegen fehlender Einwilligung")
else:
    print("❌ Test 1 fehlgeschlagen: Export hätte fehlschlagen sollen")
    print("STDOUT:", result.stdout)
    print("STDERR:", result.stderr)

print("\n=== Test 2: Export mit allen Einwilligungen ===")

# Einwilligung für Patient 3 erteilen
consent_args3 = Args(person=pseudo3, scope="test-study", notes="")
grant_consent(consent_args3)

# Export erneut versuchen
result = subprocess.run([
    sys.executable, "scripts/exporters/export_research_cohort.py",
    "--scope", "test-study",
    "--profile", "research",
    "--quasi-identifiers", "gender",
    "--k", "5"
], capture_output=True, text=True)

if result.returncode == 0 and "✅ Fertig" in result.stdout:
    print("✅ Test 2 bestanden: Export erfolgreich mit allen Einwilligungen")
else:
    print("❌ Test 2 fehlgeschlagen: Export hätte erfolgreich sein sollen")
    print("STDOUT:", result.stdout)
    print("STDERR:", result.stderr)

print("\n=== Test 3: Widerruf testen ===")

# Einwilligung von Patient 1 widerrufen
revoke_args1 = Args(person=pseudo1, scope="test-study")
revoke_consent(revoke_args1)

# Export erneut versuchen (sollte wieder fehlschlagen)
result = subprocess.run([
    sys.executable, "scripts/exporters/export_research_cohort.py",
    "--scope", "test-study",
    "--profile", "research",
    "--quasi-identifiers", "gender",
    "--k", "5"
], capture_output=True, text=True)

if result.returncode != 0 and "ABBRUCH" in result.stdout:
    print("✅ Test 3 bestanden: Export abgelehnt nach Widerruf")
else:
    print("❌ Test 3 fehlgeschlagen: Export hätte nach Widerruf fehlschlagen sollen")

print("\n=== Test 4: Echte Daten — Datumsverschiebung + k-Anonymität ===")

import csv as _csv

_SEEDED_DATE = "2024-03-15"


def _seed_measurements(pseudo: str, metric: str, count: int) -> None:
    instance_dir = Path(_TEST_HOME) / ".config" / "kyoro-master" / "patients" / pseudo
    db_path = instance_dir / "data" / "health.db"
    sys.path.insert(0, str(_REPO_ROOT / "scripts"))
    from modules.db import open_db
    # open_db() (not a raw sqlite3.connect()) so the pseudonymization
    # safeguard's SQL functions are registered on this connection — the
    # AFTER INSERT trigger on measurements.person calls them, and a raw
    # connection would fail with "no such function: pseudonymize_person".
    con = open_db(path=db_path)
    for i in range(count):
        con.execute(
            "INSERT OR IGNORE INTO measurements (ts, date, metric, value, person) "
            "VALUES (?, ?, ?, ?, ?)",
            (f"{_SEEDED_DATE}T0{i}:00:00Z", _SEEDED_DATE, metric, 70.0 + i, "self"),
        )
    con.commit()
    con.close()


# Neuer Consent-Scope fuer diesen Test (Scope aus Test 1-3 ist fuer Patient 1 widerrufen)
for p in (pseudo1, pseudo2, pseudo3):
    grant_consent(Args(person=p, scope="data-study", notes=""))

# heart_rate: 3+3 = 6 Zeilen (>= k=5, sollte behalten werden)
_seed_measurements(pseudo1, "heart_rate", 3)
_seed_measurements(pseudo2, "heart_rate", 3)
# steps: 2 Zeilen (< k=5, sollte unterdrueckt werden)
_seed_measurements(pseudo3, "steps", 2)

result = subprocess.run([
    sys.executable, "scripts/exporters/export_research_cohort.py",
    "--scope", "data-study",
    "--profile", "research",
    "--quasi-identifiers", "metric",
    "--k", "5",
], capture_output=True, text=True)

if result.returncode != 0 or "✅ Fertig" not in result.stdout:
    print("❌ Test 4 fehlgeschlagen: Export mit echten Daten schlug fehl")
    print("STDOUT:", result.stdout)
    print("STDERR:", result.stderr)
else:
    # Export-Verzeichnis aus stdout extrahieren
    export_dir_line = [l for l in result.stdout.splitlines() if l.startswith("Export-Verzeichnis:")][0]
    export_dir = Path(export_dir_line.split(": ", 1)[1].strip())
    deliverable = export_dir / "deliverable" / "measurements.csv"
    suppressed = export_dir / "suppressed" / "measurements.csv"

    ok = True
    if not deliverable.exists():
        print("❌ Test 4a fehlgeschlagen: deliverable/measurements.csv fehlt")
        ok = False
    else:
        with open(deliverable) as f:
            rows = list(_csv.DictReader(f))
        if len(rows) != 6 or any(r["metric"] != "heart_rate" for r in rows):
            print(f"❌ Test 4a fehlgeschlagen: erwartet 6 heart_rate-Zeilen, bekam {len(rows)}: {rows}")
            ok = False
        elif any(r["date"] == _SEEDED_DATE for r in rows):
            print(f"❌ Test 4b fehlgeschlagen: Datum wurde NICHT verschoben ({_SEEDED_DATE} noch vorhanden)")
            ok = False
        else:
            print(f"✅ Test 4a+4b bestanden: 6 heart_rate-Zeilen behalten, Datum verschoben "
                  f"(Original {_SEEDED_DATE} → {sorted({r['date'] for r in rows})})")

    if not suppressed.exists():
        print("❌ Test 4c fehlgeschlagen: suppressed/measurements.csv fehlt (steps-Gruppe haette unterdrueckt werden muessen)")
        ok = False
    else:
        with open(suppressed) as f:
            srows = list(_csv.DictReader(f))
        if len(srows) != 2 or any(r["metric"] != "steps" for r in srows):
            print(f"❌ Test 4c fehlgeschlagen: erwartet 2 unterdrueckte steps-Zeilen, bekam {len(srows)}: {srows}")
            ok = False
        else:
            print("✅ Test 4c bestanden: 2 steps-Zeilen korrekt unterdrueckt (Gruppengroesse 2 < k=5)")

    if ok:
        print("✅ Test 4 insgesamt bestanden")

print("\n=== Aufräumen ===")

# Test-Verzeichnis entfernen
import shutil
shutil.rmtree(_TEST_HOME, ignore_errors=True)

print("✅ Alle Tests abgeschlossen!")
