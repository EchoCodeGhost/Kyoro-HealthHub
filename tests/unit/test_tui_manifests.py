# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Tests for the TUI manifest types, the flag allowlist and the exclusions.

@tier        unit
@purpose.de  Prüft, dass nur deklarierte Flags übergeben werden, gesperrte Flags nicht
             deklarierbar sind und EXCLUDED echte Skripte trifft.
@purpose.en  Checks that only declared flags are passed, blocked flags cannot be declared
             and EXCLUDED matches real scripts.
@method.de   Prüft EXCLUDED gegen die echten Dateien unter scripts/.
@method.en   Checks EXCLUDED against the real files under scripts/.
@reads       Dateinamen unter scripts/
@writes      Nichts
@limits.de   Die Abdeckung aller Skripte folgt mit den Manifest-Einträgen.
@limits.en   Coverage of all scripts follows with the manifest entries.
"""

import subprocess
import sys
from fnmatch import fnmatchcase
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).parent.parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

from tui.manifests import (
    BLOCKED_FLAGS,
    EXCLUDED,
    BoolField,
    ChoiceField,
    IntField,
    PathField,
    ScriptEntry,
    TextField,
    is_excluded,
)


def _entry(*fields, **kwargs):
    return ScriptEntry("analysis/manual/example.py", ("Beispiel", "Example"), "test", fields=fields, **kwargs)


def test_build_args_for_each_field_type():
    entry = _entry(PathField(None, required=True), IntField("--session"), BoolField("--plot"),
                   BoolField("--list"), ChoiceField("--mode", choices=("a", "b")), TextField("--note"))
    args = entry.build_args({None: "x.csv", "--session": "42", "--plot": True, "--list": False,
                             "--mode": "b", "--note": ""})
    assert args == ["x.csv", "--session", "42", "--plot", "--mode", "b"]


def test_undeclared_flag_is_refused():
    with pytest.raises(ValueError, match="--no-scrub"):
        _entry(BoolField("--plot")).build_args({"--no-scrub": True})


def test_missing_required_field_is_refused():
    with pytest.raises(ValueError, match="--session"):
        _entry(IntField("--session", required=True)).build_args({})


def test_invalid_values_are_refused():
    with pytest.raises(ValueError):
        _entry(IntField("--session")).build_args({"--session": "abc"})
    with pytest.raises(ValueError):
        _entry(ChoiceField("--mode", choices=("a",))).build_args({"--mode": "b"})


def test_value_starting_with_a_dash_stays_one_argument():
    assert _entry(TextField("--note")).build_args({"--note": "--fix"}) == ["--note", "--fix"]


@pytest.mark.parametrize("flag", sorted(BLOCKED_FLAGS))
def test_blocked_flag_cannot_be_declared(flag):
    with pytest.raises(ValueError, match="blocked"):
        _entry(BoolField(flag))


def test_required_blocked_flags_are_listed():
    assert {"--no-scrub", "--host", "--writable", "--api-key", "--show-mappings",
            "--fix", "--no-backup", "--accept-terms", "--yes", "--no-confirm"} <= BLOCKED_FLAGS


def test_no_write_flag_must_be_declared():
    with pytest.raises(ValueError, match="no_write_flags"):
        _entry(BoolField("--plot"), no_write_flags=frozenset({"--dry-run"}))


def _all_files() -> list[str]:
    return [p.relative_to(SCRIPTS).as_posix() for p in SCRIPTS.rglob("*")
            if p.is_file() and "__pycache__" not in p.parts]


def _script_files() -> list[str]:
    return [path for path in _all_files() if path.endswith(".py")]


@pytest.mark.parametrize("pattern", sorted(EXCLUDED))
def test_every_exclusion_matches_a_real_file_and_has_a_reason(pattern):
    assert EXCLUDED[pattern].strip()
    assert any(fnmatchcase(path, pattern) for path in _all_files()), pattern


@pytest.mark.parametrize("stem_pattern", [
    "decrypt_db", "scrub_*", "migrate_*", "pseudonymize_*", "reduce_gps_precision",
    "create_*schema", "apply_icd_corrections", "promote_anamnese_findings",
])
def test_every_required_tool_is_excluded_wherever_it_lives(stem_pattern):
    matches = [p for p in _script_files() if fnmatchcase(Path(p).stem, stem_pattern)]
    assert matches, stem_pattern
    for path in matches:
        assert is_excluded(path), path


@pytest.mark.parametrize("directory", ["calibration", "medical", "cluster", "migrations"])
def test_every_script_in_excluded_directories_is_covered(directory):
    for path in _script_files():
        if path.startswith(f"{directory}/"):
            assert is_excluded(path), path


def test_regular_scripts_are_not_excluded():
    for path in ("utils/check_all.py", "utils/datasette_serve.py", "analyse_all.py", "importers/import_polar.py"):
        assert is_excluded(path) is None, path


def test_runner_and_manifests_import_without_textual():
    code = (
        "import sys; sys.modules['textual'] = None\n"
        "import tui.runner, tui.manifests\n"
    )
    result = subprocess.run([sys.executable, "-c", code], cwd=SCRIPTS, capture_output=True, text=True, timeout=60, check=False)
    assert result.returncode == 0, result.stderr
