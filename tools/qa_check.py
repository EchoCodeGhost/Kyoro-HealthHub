#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Pre-checkin quality gate — fast, offline, hermetic checks to run before every
commit (and in CI). No network, no LLM.

Checks:
  1. docs in sync           docstrings vs generated docs/ + docs/generated/data_flow.md
                             (tools/gen_docs.py --check)
  2. prompts docs in sync   prompts vs docs/prompts.md (scripts/generate_prompts_docs.py --check)
  3. SPDX headers           every scripts/*.py (except __init__.py) has an SPDX line
  4. syntax                 every scripts/*.py parses
  5. source privacy         scripts/utils/check_source_privacy.py (if present)
  6. no embedded dates      scripts/utils/check_no_dates.py (if present) — enforces
                             docs/CONTRIBUTING.md § "Versioning and changelogs"
  7. no memory links        scripts/utils/check_no_memory_links.py (if present) —
                             private memory-system `[[...]]` references never reach the repo
  8. ai labeling            scripts/utils/check_ai_labeling.py (if present) — no hand-rolled
                             LLM chat call bypasses the shared AI-generated label
  9. ruff                   lint, if ruff is installed
 10. docstrings             structured @-tags and completeness (scripts/check_docstrings.py)

The DOI/reference verification is deliberately NOT here — it is a pre-release,
online gate (see tools/verify_refs.py).

Usage:
  python3 tools/qa_check.py            # run all, non-zero exit on any failure
  python3 tools/qa_check.py --quiet    # only print failures + summary
"""

import argparse
import ast
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = REPO / "scripts"


def _py_files() -> list[Path]:
    return [f for f in SCRIPTS.rglob("*.py") if f.name != "__init__.py"]


def check_docs_sync() -> tuple[bool, list[str]]:
    r = subprocess.run([sys.executable, str(REPO / "tools" / "gen_docs.py"), "--check"],
                       capture_output=True, text=True)
    msgs = [l for l in (r.stdout + r.stderr).splitlines() if l.strip()]
    return r.returncode == 0, msgs


def check_spdx() -> tuple[bool, list[str]]:
    missing = []
    for f in _py_files():
        head = f.read_text(encoding="utf-8", errors="replace")[:400]
        if "SPDX-License-Identifier" not in head:
            missing.append(f"no SPDX: {f.relative_to(REPO).as_posix()}")
    return not missing, missing


def check_syntax() -> tuple[bool, list[str]]:
    bad = []
    for f in _py_files():
        try:
            ast.parse(f.read_text(encoding="utf-8"))
        except SyntaxError as e:
            bad.append(f"syntax: {f.relative_to(REPO).as_posix()}:{e.lineno}: {e.msg}")
    return not bad, bad


def check_privacy() -> tuple[bool, list[str]]:
    script = SCRIPTS / "utils" / "check_source_privacy.py"
    if not script.exists():
        return True, ["skipped: check_source_privacy.py not found"]
    r = subprocess.run([sys.executable, str(script)], capture_output=True, text=True)
    msgs = [l for l in (r.stdout + r.stderr).splitlines() if l.strip()]
    return r.returncode == 0, msgs[-10:]


def check_no_dates() -> tuple[bool, list[str]]:
    script = SCRIPTS / "utils" / "check_no_dates.py"
    if not script.exists():
        return True, ["skipped: check_no_dates.py not found"]
    r = subprocess.run([sys.executable, str(script)], capture_output=True, text=True)
    msgs = [line for line in (r.stdout + r.stderr).splitlines() if line.strip()]
    return r.returncode == 0, msgs[-20:]


def check_no_memory_links() -> tuple[bool, list[str]]:
    script = SCRIPTS / "utils" / "check_no_memory_links.py"
    if not script.exists():
        return True, ["skipped: check_no_memory_links.py not found"]
    r = subprocess.run([sys.executable, str(script)], capture_output=True, text=True)
    msgs = [line for line in (r.stdout + r.stderr).splitlines() if line.strip()]
    return r.returncode == 0, msgs[-20:]


def check_ai_labeling() -> tuple[bool, list[str]]:
    script = SCRIPTS / "utils" / "check_ai_labeling.py"
    if not script.exists():
        return True, ["skipped: check_ai_labeling.py not found"]
    r = subprocess.run([sys.executable, str(script), "--quiet"], capture_output=True, text=True)
    msgs = [line for line in (r.stdout + r.stderr).splitlines() if line.strip()]
    return r.returncode == 0, msgs[-20:]


def _find_ruff() -> str | None:
    # shutil.which() only sees PATH — misses a project venv's own bin/ruff
    # when the venv isn't activated (e.g. `python3 tools/qa_check.py` with a
    # bare system python). Check next to the running interpreter first, since
    # that's exactly the venv this script itself is most likely running in.
    venv_ruff = Path(sys.executable).parent / "ruff"
    if venv_ruff.exists():
        return str(venv_ruff)
    return shutil.which("ruff")


def check_ruff() -> tuple[bool, list[str]]:
    ruff = _find_ruff()
    if not ruff:
        return True, ["skipped: ruff not installed"]
    # Restricted to critical bug classes only (undefined names, redefinitions,
    # bare except, ...). Style findings (F401/F541/F841 etc.) are excluded —
    # not treated as errors in this project, so a full default-ruleset run
    # would turn this gate red on noise instead of real bugs.
    r = subprocess.run([ruff, "check", "--select", "F821,F811,F402,F601,E722",
                        str(SCRIPTS), str(REPO / "tools")],
                       capture_output=True, text=True)
    msgs = [l for l in (r.stdout + r.stderr).splitlines() if l.strip()]
    return r.returncode == 0, msgs[-15:]


def check_docstrings() -> tuple[bool, list[str]]:
    """Prüft Docstrings auf strukturierte @-Tags und Vollständigkeit."""
    script = SCRIPTS / "check_docstrings.py"
    if not script.exists():
        return True, ["skipped: check_docstrings.py not found"]
    r = subprocess.run([sys.executable, str(script), "--quiet"],
                      capture_output=True, text=True)
    msgs = [l for l in (r.stdout + r.stderr).splitlines() if l.strip()]
    return r.returncode == 0, msgs[-20:]  # Letzte 20 Fehlermeldungen


def check_prompts_docs_sync() -> tuple[bool, list[str]]:
    """Prüft, ob docs/prompts.md mit der Prompt-Registry synchron ist."""
    script = SCRIPTS / "generate_prompts_docs.py"
    if not script.exists():
        return True, ["skipped: generate_prompts_docs.py not found"]
    r = subprocess.run([sys.executable, str(script), "--check"],
                      capture_output=True, text=True, cwd=REPO)
    msgs = [l for l in (r.stdout + r.stderr).splitlines() if l.strip()]
    return r.returncode == 0, msgs


def check_syndrome_endemic_regions() -> tuple[bool, list[str]]:
    """Prüft, ob syndromes/*.json's endemic_regions mit ENDEMIC_REFERENCE/
    FSME_RISIKOKREISE_BUNDESWEIT synchron sind (s. dortiger Docstring)."""
    script = SCRIPTS / "utils" / "check_syndrome_endemic_regions.py"
    if not script.exists():
        return True, ["skipped: check_syndrome_endemic_regions.py not found"]
    r = subprocess.run([sys.executable, str(script), "--quiet"],
                        capture_output=True, text=True)
    msgs = [l for l in (r.stdout + r.stderr).splitlines() if l.strip()]
    return r.returncode == 0, msgs


CHECKS = [
    ("docs in sync", check_docs_sync),
    ("prompts docs in sync", check_prompts_docs_sync),
    ("SPDX headers", check_spdx),
    ("syntax",       check_syntax),
    ("source privacy", check_privacy),
    ("no embedded dates", check_no_dates),
    ("no memory links", check_no_memory_links),
    ("ai labeling",  check_ai_labeling),
    ("ruff",         check_ruff),
    ("docstrings",   check_docstrings),
    ("syndrome endemic regions sync", check_syndrome_endemic_regions),
]


def main() -> int:
    ap = argparse.ArgumentParser(description="Pre-checkin quality gate.")
    ap.add_argument("--quiet", action="store_true", help="only show failures")
    args = ap.parse_args()

    failed = 0
    for name, fn in CHECKS:
        ok, msgs = fn()
        skipped = msgs and all(m.startswith("skipped") for m in msgs)
        status = "SKIP" if (ok and skipped) else ("PASS" if ok else "FAIL")
        if not ok:
            failed += 1
        if not args.quiet or not ok:
            print(f"[{status}] {name}")
            if not ok or (msgs and not args.quiet):
                for m in msgs:
                    print(f"        {m}")
    print()
    if failed:
        print(f"QA FAILED: {failed} of {len(CHECKS)} check group(s) failed.")
        return 1
    print(f"QA OK: {len(CHECKS)} check group(s) passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
