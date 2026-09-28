# SPDX-License-Identifier: GPL-3.0-or-later
"""
Regression-Test: alle Path-Properties von health_config.Config müssen
.expanduser() aufrufen.

Hintergrund: 7 Properties (beurer_dir, omron_dir, garmin_dir, kubios_dir,
camerahRV_dir, migraine_dir, symptom_diary_dir) fehlte das — ein Config-Wert
mit literalem "~" (wie ihn die mitgelieferte Beispiel-Config verwendet) blieb
unaufgelöst. Die Importer suchten dann nach Dateien in einem Verzeichnis
namens "~", fanden nichts und meldeten "keine Dateien gefunden", obwohl die
echten Dateien am aufgelösten Pfad lagen. Kein Absturz, keine Fehlermeldung —
nur stille Datenverluste.

Läuft in einem Subprozess mit KYORO_ACTIVE_PATIENT_DIR auf ein Temp-
Verzeichnis: health_config.py liest CONFIG_PATH/DEFAULTS bei Modul-Import
einmalig ein, ein Reload im selben Prozess wäre nicht realistisch.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
EXAMPLE_CONFIG = PROJECT_ROOT / "templates" / "health_config.example.json"

_CHECK_SCRIPT = """
import sys
sys.path.insert(0, {scripts_dir!r})
from pathlib import Path
from health_config import Config

cfg = Config()
bad = []
for name, attr in vars(type(cfg)).items():
    if not isinstance(attr, property):
        continue
    try:
        value = getattr(cfg, name)
    except Exception:
        continue
    if isinstance(value, Path) and "~" in str(value):
        bad.append(f"{{name}}: {{value}}")

if bad:
    print("\\n".join(bad))
    sys.exit(1)
sys.exit(0)
"""


def test_no_config_property_leaks_literal_tilde(tmp_path):
    assert EXAMPLE_CONFIG.exists(), "templates/health_config.example.json missing"

    config_dir = tmp_path / ".config" / "kyoro"
    config_dir.mkdir(parents=True)
    (config_dir / "health_config.json").write_text(EXAMPLE_CONFIG.read_text())

    script = _CHECK_SCRIPT.format(scripts_dir=str(SCRIPTS_DIR))
    result = subprocess.run(
        [sys.executable, "-c", script],
        env={**os.environ, "KYORO_ACTIVE_PATIENT_DIR": str(tmp_path)},
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, (
        "Config properties returned an unresolved '~' path "
        "(missing .expanduser() in health_config.py):\n"
        f"{result.stdout}{result.stderr}"
    )


def test_example_config_actually_uses_tilde_paths():
    """Guards the test fixture itself: if the shipped example stops using
    '~' paths, test_no_config_property_leaks_literal_tilde above would pass
    vacuously without exercising the expanduser() call at all."""
    cfg = json.loads(EXAMPLE_CONFIG.read_text())
    paths = cfg.get("paths", {})
    tilde_paths = [k for k, v in paths.items() if isinstance(v, str) and v.startswith("~")]
    assert len(tilde_paths) >= 5, (
        "Expected the shipped example config to use '~'-prefixed paths "
        "(that's what makes this fixture useful) — found: "
        f"{tilde_paths}"
    )
