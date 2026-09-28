#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Regressionstest: Verhalten ohne KYORO_ACTIVE_PATIENT_DIR

@tier        test
@purpose.de  Stellt sicher, dass das System ohne gesetzte KYORO_ACTIVE_PATIENT_DIR
             Umweltvariable genau wie vorher funktioniert (keine Regression).
@purpose.en  Ensures the system behaves exactly as before when KYORO_ACTIVE_PATIENT_DIR
             environment variable is not set (no regression).
@method.de   Testet, dass KYORO_CONFIG_DIR auf ~/.config/kyoro/ zeigt und alle
             Pfade korrekt aufgelöst werden.
@method.en  Tests that KYORO_CONFIG_DIR points to ~/.config/kyoro/ and all paths
             resolve correctly.
@usage
    python3 tests/manual/test_regression_no_env.py   # ausführen aus dem Repo-Root
"""
import os
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).parent.parent.parent

# Stelle sicher, dass KYORO_ACTIVE_PATIENT_DIR nicht gesetzt ist
if "KYORO_ACTIVE_PATIENT_DIR" in os.environ:
    del os.environ["KYORO_ACTIVE_PATIENT_DIR"]

# Importiere health_config nach der Bereinigung der Umgebung
sys.path.insert(0, str(_REPO_ROOT))
from scripts.health_config import KYORO_CONFIG_DIR, KYORO_MASTER_DIR

def test_default_paths():
    """Teste, dass die Standardpfade ohne KYORO_ACTIVE_PATIENT_DIR korrekt sind."""
    home = Path.home()
    expected_config_dir = home / ".config" / "kyoro"
    expected_master_dir = home / ".config" / "kyoro-master"
    
    assert KYORO_CONFIG_DIR == expected_config_dir, \
        f"KYORO_CONFIG_DIR sollte {expected_config_dir} sein, ist aber {KYORO_CONFIG_DIR}"
    assert KYORO_MASTER_DIR == expected_master_dir, \
        f"KYORO_MASTER_DIR sollte {expected_master_dir} sein, ist aber {KYORO_MASTER_DIR}"
    
    print("✓ Standardpfade sind korrekt ohne KYORO_ACTIVE_PATIENT_DIR")

def test_db_paths():
    """Teste, dass die Datenbankpfade korrekt aufgelöst werden."""
    from scripts.health_config import DEFAULTS
    
    # Teste einige wichtige Pfade
    db_path = Path(DEFAULTS['paths']['db'])
    expected_db_path = Path.home() / "Kyoro-HealthHub" / "data"
    assert db_path.parent == expected_db_path, \
        f"db_path sollte unter {expected_db_path} liegen: {db_path.parent} != {expected_db_path}"
    
    print("✓ Datenbankpfade sind korrekt (Standardverhalten ohne KYORO_ACTIVE_PATIENT_DIR)")

def test_no_regression():
    """Teste, dass das Verhalten dem alten Verhalten entspricht."""
    # Simuliere das alte Verhalten (direkter Pfadaufbau)
    old_style_config_dir = Path.home() / ".config" / "kyoro"
    
    assert KYORO_CONFIG_DIR == old_style_config_dir, \
        "KYORO_CONFIG_DIR sollte dem alten Standardpfad entsprechen"
    
    print("✓ Keine Regression: Verhalten entspricht dem alten Standard")

if __name__ == "__main__":
    print("Führe Regressionstests ohne KYORO_ACTIVE_PATIENT_DIR durch...")
    test_default_paths()
    test_db_paths()
    test_no_regression()
    print("\n✓ Alle Regressionstests bestanden!")
