#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Verifikation: Zwei Test-Patient:innen, zwei Test-User, End-to-End-Zugriffstest

@tier        test
@purpose.de  Verifiziert die korrekte Funktionsweise des Berechtigungssystems mit zwei
             Test-Patient:innen und zwei Test-Usern (ein autorisiert, einer nicht).
@purpose.en  Verifies the correct functioning of the authorization system with two
             test patients and two test users (one authorized, one not).
@method.de   Erstellt zwei Test-Patient:innen, zwei Test-User, weist Berechtigungen zu,
             und testet den Zugriff auf die API-Endpunkte.
@method.en  Creates two test patients, two test users, assigns permissions, and tests
             access to the API endpoints.
@usage
    python3 tests/manual/test_verification.py   # ausführen aus dem Repo-Root
"""
import os
import sys
import subprocess
import tempfile
from pathlib import Path

_REPO_ROOT = Path(__file__).parent.parent.parent

# Isolation: HOME auf ein temporäres Verzeichnis umbiegen, BEVOR health_config/
# auth/db importiert werden — sonst schreibt dieser Test in den echten
# KYORO_MASTER_DIR des Betreibers (siehe den Vorfall im Klinik-Multi-Patienten-
# Plan: Testläufe hatten reale Test-Patienten/-User in
# ~/.config/kyoro-master/ hinterlassen). Path.home() liest unter POSIX $HOME.
_TEST_HOME = tempfile.mkdtemp(prefix="kyoro_test_home_")
os.environ["HOME"] = _TEST_HOME

# Minimale health_config.json anlegen — OWN_PERSON_ID braucht mindestens
# user.name, um ein Pseudonym ableiten zu können (identity.db existiert im
# frischen Test-HOME noch nicht).
import json as _json
_test_kyoro_dir = Path(_TEST_HOME) / ".config" / "kyoro"
_test_kyoro_dir.mkdir(parents=True, exist_ok=True)
(_test_kyoro_dir / "health_config.json").write_text(
    _json.dumps({"user": {"name": "Test Operator"}}), encoding="utf-8"
)

# health.db existiert in einem frischen Test-HOME nicht (normalerweise legt
# onboard.py es an) — Basis-Schema direkt anlegen, damit db.get_conn() nicht
# gegen ein nicht existierendes Verzeichnis läuft.
sys.path.insert(0, str(_REPO_ROOT / "scripts"))
from utils.create_schema import SCHEMA as _HEALTH_SCHEMA
import sqlite3 as _sqlite3
_test_data_dir = Path(_TEST_HOME) / "Kyoro-HealthHub" / "data"
_test_data_dir.mkdir(parents=True, exist_ok=True)
_test_conn = _sqlite3.connect(_test_data_dir / "health.db")
_test_conn.executescript(_HEALTH_SCHEMA)
_test_conn.commit()
_test_conn.close()

# Füge das scripts-Verzeichnis zum Pfad hinzu
sys.path.insert(0, str(_REPO_ROOT / "pwa" / "backend"))

import auth
import db

def test_verification():
    """Verifiziere die korrekte Funktionsweise des Berechtigungssystems."""
    # Schritt 1: Zwei Test-Patient:innen erstellen
    print("1. Zwei Test-Patient:innen erstellen...")
    result1 = subprocess.run([
        sys.executable, str(_REPO_ROOT / "scripts" / "utils" / "manage" / "shared_access" / "manage_people.py"),
        "add", "PAT-001", "--group-id", "Gruppe-A"
    ], capture_output=True, text=True, cwd=str(_REPO_ROOT), env=os.environ)
    if result1.returncode != 0:
        print(f"   ✗ Fehler beim Erstellen der ersten Patient:in: {result1.stderr}")
        sys.exit(1)
    print(f"   ✓ Erste Patient:in erstellt")
    
    result2 = subprocess.run([
        sys.executable, str(_REPO_ROOT / "scripts" / "utils" / "manage" / "shared_access" / "manage_people.py"),
        "add", "PAT-002", "--group-id", "Gruppe-A"
    ], capture_output=True, text=True, cwd=str(_REPO_ROOT), env=os.environ)
    if result2.returncode != 0:
        print(f"   ✗ Fehler beim Erstellen der zweiten Patient:in: {result2.stderr}")
        sys.exit(1)
    print(f"   ✓ Zweite Patient:in erstellt")
    
    # Schritt 2: Zwei Test-User erstellen
    print("\n2. Zwei Test-User erstellen...")
    result3 = subprocess.run([
        sys.executable, str(_REPO_ROOT / "pwa" / "backend" / "auth.py"),
        "--add-user", "test_user1", "--name", "Test User 1"
    ], capture_output=True, text=True, cwd=str(_REPO_ROOT), env=os.environ)
    if result3.returncode != 0:
        print(f"   ✗ Fehler beim Erstellen des ersten Users: {result3.stderr}")
        sys.exit(1)
    print(f"   ✓ Erster User erstellt")
    
    result4 = subprocess.run([
        sys.executable, str(_REPO_ROOT / "pwa" / "backend" / "auth.py"),
        "--add-user", "test_user2", "--name", "Test User 2"
    ], capture_output=True, text=True, cwd=str(_REPO_ROOT), env=os.environ)
    if result4.returncode != 0:
        print(f"   ✗ Fehler beim Erstellen des zweiten Users: {result4.stderr}")
        sys.exit(1)
    print(f"   ✓ Zweiter User erstellt")
    
    # Schritt 3: Berechtigungen zuweisen
    print("\n3. Berechtigungen zuweisen...")
    # Hole die patient_pseudo-Werte
    result_list = subprocess.run([
        sys.executable, str(_REPO_ROOT / "scripts" / "utils" / "manage" / "shared_access" / "manage_people.py"), "list"
    ], capture_output=True, text=True, cwd=str(_REPO_ROOT), env=os.environ)
    if result_list.returncode != 0:
        print(f"   ✗ Fehler beim Auflisten der Patient:innen: {result_list.stderr}")
        sys.exit(1)
    
    # Extrahiere die patient_pseudo-Werte
    lines = result_list.stdout.strip().split('\n')
    patient_pseudos = []
    for line in lines:
        if 'OK PT-' in line:
            parts = line.split()
            patient_pseudos.append(parts[1])
    
    if len(patient_pseudos) < 2:
        print(f"   ✗ Nicht genug Patient:innen gefunden")
        sys.exit(1)
    
    patient_pseudo1 = patient_pseudos[0]
    patient_pseudo2 = patient_pseudos[1]
    
    # Initialisiere die Tabellen manuell
    conn = db.get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS patient_assignments (
            user_id        TEXT NOT NULL,
            patient_pseudo TEXT NOT NULL,
            role           TEXT NOT NULL CHECK(role IN 
                             ('owner','staff_readonly','staff_readwrite','admin')),
            granted_by     TEXT,
            granted_at     TEXT NOT NULL,
            revoked_at     TEXT,
            PRIMARY KEY (user_id, patient_pseudo)
        );
        
        CREATE TABLE IF NOT EXISTS access_log (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id        TEXT NOT NULL,
            patient_pseudo TEXT NOT NULL,
            action         TEXT NOT NULL,
            ts             TEXT NOT NULL,
            detail         TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_access_log_patient
            ON access_log(patient_pseudo, ts);
    """)
    conn.commit()
    conn.close()
    
    # Weise test_user1 Berechtigungen für patient_pseudo1 zu
    conn = db.get_conn()
    conn.execute("""
        INSERT INTO patient_assignments 
        (user_id, patient_pseudo, role, granted_by, granted_at) 
        VALUES (?, ?, 'staff_readwrite', 'admin', datetime('now'))
    """, ("test_user1", patient_pseudo1))
    conn.commit()
    conn.close()
    print(f"   ✓ Berechtigungen für test_user1 zugewiesen")
    
    # Schritt 4: Zugriffstest
    print("\n4. Zugriffstest...")
    # Teste den Zugriff für test_user1 auf patient_pseudo1 (sollte erfolgreich sein)
    from authz import check_patient_access
    from auth import UserInfo
    
    user1 = UserInfo(user_id="test_user1", name="Test User 1", readonly=False)
    try:
        check_patient_access(user1, patient_pseudo1)
        print(f"   ✓ Zugriff für test_user1 auf {patient_pseudo1} erfolgreich")
    except Exception as e:
        print(f"   ✗ Zugriff für test_user1 auf {patient_pseudo1} fehlgeschlagen: {e}")
        sys.exit(1)
    
    # Teste den Zugriff für test_user1 auf patient_pseudo2 (sollte fehlschlagen)
    try:
        check_patient_access(user1, patient_pseudo2)
        print(f"   ✗ Zugriff für test_user1 auf {patient_pseudo2} sollte fehlschlagen")
        sys.exit(1)
    except Exception as e:
        print(f"   ✓ Zugriff für test_user1 auf {patient_pseudo2} korrekt abgelehnt")
    
    # Teste den Zugriff für test_user2 auf patient_pseudo1 (sollte fehlschlagen)
    user2 = UserInfo(user_id="test_user2", name="Test User 2", readonly=False)
    try:
        check_patient_access(user2, patient_pseudo1)
        print(f"   ✗ Zugriff für test_user2 auf {patient_pseudo1} sollte fehlschlagen")
        sys.exit(1)
    except Exception as e:
        print(f"   ✓ Zugriff für test_user2 auf {patient_pseudo1} korrekt abgelehnt")
    
    # Schritt 5: Audit-Log überprüfen
    print("\n5. Audit-Log überprüfen...")
    conn = db.get_conn()
    rows = conn.execute("SELECT * FROM access_log").fetchall()
    conn.close()
    
    if len(rows) < 3:
        print(f"   ✗ Nicht genug Einträge im Audit-Log gefunden")
        sys.exit(1)
    
    print(f"   ✓ Audit-Log enthält {len(rows)} Einträge")
    
    print("\n✓ Verifikation erfolgreich!")

if __name__ == "__main__":
    print("Führe Verifikation durch...")
    test_verification()
