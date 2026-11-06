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
@limits.de   Prüft bisher nur die On-Demand-Einträge; die übrigen folgen.
@limits.en   Only checks the on-demand entries so far; the others follow.
"""

import ast
import re
import subprocess
import sys
from dataclasses import fields as dataclass_fields
from fnmatch import fnmatchcase
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).parent.parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

import analyse_all
import compute_all
from tui.manifests import (
    BLOCKED_FLAGS,
    EXCLUDED,
    ON_DEMAND_ENTRIES,
    BoolField,
    ChoiceField,
    FloatField,
    IntField,
    ListField,
    PathField,
    ScriptEntry,
    ScriptMode,
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


# ── On-demand entries against the scripts' source ─────────────────────────────

# Bewusst nicht angeboten; die Sprache kommt über KYORO_LANG, --person hängt am Personenfeld.
NOT_OFFERED = {"--lang", "--person"} | BLOCKED_FLAGS
_LLM_IN_CODE = re.compile(r"\bcall_llm\b|_call_llm\b|modules\.llm\b|llm_provider|openrouter", re.IGNORECASE)


def _tree(entry) -> ast.Module:
    return ast.parse((SCRIPTS / entry.script).read_text(encoding="utf-8"))


def _code_without_docstrings(entry) -> str:
    tree = _tree(entry)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef)) \
                and ast.get_docstring(node) is not None:
            node.body = node.body[1:] or [ast.Pass()]
    return ast.unparse(tree)


def _argparse_definitions(entry) -> dict[str, dict]:
    definitions = {}
    for node in ast.walk(_tree(entry)):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "add_argument":
            flag = node.args[0].value
            definitions[flag] = {k.arg: ast.unparse(k.value) for k in node.keywords if k.arg}
    return definitions


entries = pytest.mark.parametrize("entry", ON_DEMAND_ENTRIES, ids=lambda e: Path(e.script).stem)


def test_on_demand_entries_match_the_orchestrator_lists():
    declared = {e.script for e in ON_DEMAND_ENTRIES}
    assert declared == set(compute_all.ON_DEMAND_COMPUTE_SCRIPTS) | set(analyse_all.ON_DEMAND_ANALYSE_SCRIPTS)
    assert len(declared) == len(ON_DEMAND_ENTRIES)


@entries
def test_declared_flags_exist_in_the_script(entry):
    supported = analyse_all._supported_flags(SCRIPTS / entry.script)
    for f in entry.fields:
        assert f.flag in supported, f"{entry.script}: {f.flag}"


@entries
def test_every_flag_of_the_script_is_declared_or_deliberately_not_offered(entry):
    supported = analyse_all._supported_flags(SCRIPTS / entry.script)
    declared = {f.flag for f in entry.fields}
    assert supported - declared <= NOT_OFFERED, entry.script


@entries
def test_field_types_match_the_argparse_definition(entry):
    definitions = _argparse_definitions(entry)
    for f in entry.fields:
        definition = definitions[f.flag]
        action = definition.get("action", "")
        assert isinstance(f, BoolField) == ("store_true" in action), f"{entry.script}: {f.flag}"
        assert isinstance(f, ListField) == ("append" in action), f"{entry.script}: {f.flag}"
        assert isinstance(f, IntField) == (definition.get("type") == "int"), f"{entry.script}: {f.flag}"
        assert isinstance(f, FloatField) == (definition.get("type") == "float"), f"{entry.script}: {f.flag}"
        assert f.required == (definition.get("required") == "True"), f"{entry.script}: {f.flag}"
        if isinstance(f, ChoiceField):
            assert sorted(f.choices) == sorted(ast.literal_eval(definition["choices"])), f"{entry.script}: {f.flag}"
        elif "choices" in definition:
            pytest.fail(f"{entry.script}: {f.flag} has choices")


@entries
def test_script_calling_input_is_interactive(entry):
    calls_input = any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "input"
                      for n in ast.walk(_tree(entry)))
    assert calls_input == (entry.mode is ScriptMode.INTERACTIVE), entry.script


@entries
def test_uses_llm_matches_the_code(entry):
    assert bool(_LLM_IN_CODE.search(_code_without_docstrings(entry))) == entry.uses_llm, entry.script


@entries
def test_labels_are_bilingual_and_every_field_has_one(entry):
    assert all(part.strip() for part in entry.label) and len(entry.label) == 2
    for f in entry.fields:
        assert f.label and all(part.strip() for part in f.label), f"{entry.script}: {f.flag}"


def test_entries_have_no_way_to_skip_the_start_dialog():
    assert "confirm" not in {f.name for f in dataclass_fields(ScriptEntry)}


def test_analyse_preview_flags_are_declared_in_the_entries():
    by_script = {e.script: e for e in ON_DEMAND_ENTRIES}
    for script, flags in analyse_all.ON_DEMAND_ANALYSE_SCRIPTS.items():
        assert set(flags) <= {f.flag for f in by_script[script].fields}, script
        assert set(flags) <= by_script[script].no_write_flags, script


def test_dry_run_flag_never_counts_as_writing():
    for entry in ON_DEMAND_ENTRIES:
        if "--dry-run" in {f.flag for f in entry.fields}:
            assert "--dry-run" in entry.no_write_flags, entry.script


def test_list_field_and_float_field_arguments():
    entry = _entry(ListField("--supplement", required=True), FloatField("--hours"))
    assert entry.build_args({"--supplement": ["A", "B"], "--hours": "1.5"}) == \
        ["--supplement", "A", "--supplement", "B", "--hours", "1.5"]
    with pytest.raises(ValueError, match="--supplement"):
        entry.build_args({"--supplement": []})


@pytest.mark.parametrize("stem,flag", [("analyse_synthesis", "--no-scrub"), ("analyse_synthesis", "--yes")])
def test_protective_flags_of_the_synthesis_are_not_offered(stem, flag):
    entry = next(e for e in ON_DEMAND_ENTRIES if Path(e.script).stem == stem)
    assert flag not in {f.flag for f in entry.fields}
    with pytest.raises(ValueError):
        entry.build_args({flag: True})
