#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
TOTP-Setup End-to-End Test

@tier        test
@purpose.de  Testet das TOTP-Setup von der Generierung des QR-Codes bis zum Login.
@purpose.en  Tests the TOTP setup from QR code generation to login.
@method.de   Erstellt einen neuen Benutzer, generiert einen TOTP-Secret, zeigt den QR-Code an,
             und testet den Login mit einem gültigen TOTP-Code.
@method.en  Creates a new user, generates a TOTP secret, displays the QR code, and tests
             login with a valid TOTP code.
@usage
    python3 tests/manual/test_totp_setup.py   # ausführen aus dem Repo-Root
"""
import os
import sys
import tempfile
import time
from pathlib import Path

_REPO_ROOT = Path(__file__).parent.parent.parent

# Isolation: HOME auf ein temporäres Verzeichnis umbiegen, BEVOR auth
# importiert wird — sonst schreibt dieser Test in den echten KYORO_MASTER_DIR
# des Betreibers (siehe den Vorfall im Klinik-Multi-Patienten-Plan).
# Path.home() liest unter POSIX $HOME.
_TEST_HOME = tempfile.mkdtemp(prefix="kyoro_test_home_")
os.environ["HOME"] = _TEST_HOME

# Füge das scripts-Verzeichnis zum Pfad hinzu
sys.path.insert(0, str(_REPO_ROOT / "pwa" / "backend"))

import auth

def test_totp_setup():
    """Teste das TOTP-Setup von der Generierung des QR-Codes bis zum Login."""
    # Benutzername für den Test
    test_user = "test_user"
    
    # Schritt 1: JWT-Secret generieren
    print("1. JWT-Secret generieren...")
    import subprocess
    result = subprocess.run([
        sys.executable, str(_REPO_ROOT / "pwa" / "backend" / "auth.py"), "--setup"
    ], capture_output=True, text=True, input="test_user\nTest User\n\n", encoding='utf-8',
       cwd=str(_REPO_ROOT), env=os.environ)
    if result.returncode != 0:
        print(f"   ✗ Fehler beim Generieren des JWT-Secrets: {result.stderr}")
        sys.exit(1)
    print(f"   ✓ JWT-Secret generiert")
    
    # Schritt 2: TOTP-Secret abrufen
    print("\n2. TOTP-Secret abrufen...")
    users = auth._users()
    secret = users.get(test_user, {}).get("totp_secret", "")
    if not secret:
        print(f"   ✗ Kein TOTP-Secret für Benutzer '{test_user}' gefunden")
        sys.exit(1)
    print(f"   ✓ TOTP-Secret abgerufen ({len(secret)} Zeichen)")
    
    # Schritt 3: QR-Code generieren
    print("\n3. QR-Code generieren...")
    import pyotp
    uri = pyotp.TOTP(secret).provisioning_uri(name="Test User", issuer_name="SymptomTracker")
    print(f"   ✓ QR-Code generiert")
    print(f"   Authenticator-URL: {uri}")
    
    # Schritt 4: TOTP-Code generieren (simuliert)
    print("\n4. TOTP-Code generieren (simuliert)...")
    totp = pyotp.TOTP(secret)
    totp_code = totp.now()
    print(f"   ✓ TOTP-Code generiert: {totp_code}")
    
    # Schritt 5: TOTP-Code überprüfen
    print("\n5. TOTP-Code überprüfen...")
    is_valid = auth.verify_totp(test_user, totp_code)
    if is_valid:
        print(f"   ✓ TOTP-Code ist gültig")
    else:
        print(f"   ✗ TOTP-Code ist ungültig")
        sys.exit(1)
    
    # Schritt 6: JWT-Token generieren
    print("\n6. JWT-Token generieren...")
    token = auth.issue_session_token(test_user)
    print(f"   ✓ JWT-Token generiert")
    
    # Schritt 7: Token überprüfen
    print("\n7. JWT-Token überprüfen...")
    user_info = auth.verify_token(token)
    if user_info and user_info.user_id == test_user:
        print(f"   ✓ JWT-Token ist gültig für Benutzer '{test_user}'")
    else:
        print(f"   ✗ JWT-Token ist ungültig")
        sys.exit(1)
    
    print("\n✓ TOTP-Setup End-to-End Test erfolgreich!")

if __name__ == "__main__":
    print("Führe TOTP-Setup End-to-End Test durch...")
    test_totp_setup()
