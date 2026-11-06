# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Tests for exact selection, sanitising only and on-demand runs in the orchestrators.

@tier        unit
@purpose.de  Prüft --only-exact, --sanitize-only, --on-demand und COMPUTE_REQUIRES der
             drei Orchestratoren.
@purpose.en  Checks --only-exact, --sanitize-only, --on-demand and COMPUTE_REQUIRES of
             the three orchestrators.
@method.de   Die echten main()-Funktionen starten echte Kindprozesse, aber nur leere
             Ersatzskripte in einem temporären Verzeichnis, die ihren Aufruf notieren.
@method.en   The real main() functions start real child processes, but only stand-in
             scripts in a temporary directory that record their call.
@reads       temporäre Dateien
@writes      temporäre Dateien
@limits.de   Keine echte Datenbank; Logging und Bereinigung sind ersetzt. Die Prüfung
             mit echten Daten steht im OpenSpec-Change.
@limits.en   No real database; logging and sanitising are replaced. Verification with
             real data is listed in the OpenSpec change.
"""

import json
import os
import pty
import re
import select
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).parent.parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

import analyse_all
import compute_all
import import_all
from modules import pipeline_runner
from utils import post_import_sanitize

RECORDER = (
    "import json, os, sys\n"
    "with open(os.environ['RECORD_FILE'], 'a', encoding='utf-8') as fh:\n"
    "    fh.write(json.dumps([os.path.basename(sys.argv[0]), sys.argv[1:]]) + '\\n')\n"
    "sys.exit(int(os.environ.get('CHILD_EXIT', '0')))\n"
)


def _populate(root: Path, names) -> None:
    for name in names:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(RECORDER, encoding="utf-8")


def _calls(record: Path) -> list:
    if not record.exists():
        return []
    return [json.loads(line) for line in record.read_text(encoding="utf-8").splitlines()]


def _called_stems(record: Path) -> list[str]:
    return [Path(name).stem for name, _ in _calls(record)]


@pytest.fixture
def record(tmp_path, monkeypatch):
    path = tmp_path / "calls.jsonl"
    monkeypatch.setenv("RECORD_FILE", str(path))
    monkeypatch.delenv("CHILD_EXIT", raising=False)
    return path


@pytest.fixture
def logged(monkeypatch):
    rows = []
    monkeypatch.setattr(pipeline_runner, "_log_compute_run", lambda *a: rows.append(("compute", *a)))
    monkeypatch.setattr(pipeline_runner, "_log_analysis_run", lambda *a: rows.append(("analysis", *a)))
    return rows


class _FakeConfig:
    def __init__(self, root: Path):
        self.root = root

    data_start = None
    infection_date = "2000-01-01"

    @property
    def analyses_dir(self):
        return self.root / "analyses"

    @property
    def data_root(self):
        return self.root / "imports"

    @property
    def apple_xml(self):
        return self.root / "imports" / "apple" / "export.xml"


def _run(module, monkeypatch, *argv):
    monkeypatch.setattr(sys, "argv", [module.__name__, *argv])
    module.main()


@pytest.fixture
def analyse(tmp_path, monkeypatch, record, logged):
    _populate(tmp_path, analyse_all.ANALYSE_SCRIPTS)
    _populate(tmp_path, analyse_all.ON_DEMAND_ANALYSE_SCRIPTS)
    monkeypatch.setattr(analyse_all, "SCRIPT_DIR", tmp_path)
    monkeypatch.setattr(analyse_all, "_Cfg", lambda: _FakeConfig(tmp_path))
    return tmp_path


@pytest.fixture
def compute(tmp_path, monkeypatch, record, logged):
    _populate(tmp_path, compute_all.COMPUTE_SCRIPTS)
    _populate(tmp_path, compute_all.ON_DEMAND_COMPUTE_SCRIPTS)
    monkeypatch.setattr(compute_all, "SCRIPT_DIR", tmp_path)
    return tmp_path


@pytest.fixture
def importer(tmp_path, monkeypatch, record):
    _populate(tmp_path, import_all.IMPORTERS)
    _populate(tmp_path, ["importers/import_ecg_logger.py", "importers/import_ecg_apple.py", "process_inbox.py"])
    (tmp_path / "imports" / "ecglogger").mkdir(parents=True)
    (tmp_path / "imports" / "ecglogger" / "x.csv").write_text("", encoding="utf-8")
    (tmp_path / "imports" / "apple" / "electrocardiograms").mkdir(parents=True)
    (tmp_path / "imports" / "_inbox").mkdir()
    (tmp_path / "imports" / "_inbox" / "waiting.txt").write_text("", encoding="utf-8")

    def _no_db():
        raise RuntimeError("no database in this test")

    monkeypatch.setattr("modules.db.open_db", _no_db)
    monkeypatch.setattr("modules.db.open_medicine_db", _no_db)
    monkeypatch.setattr(import_all, "SCRIPT_DIR", tmp_path)
    monkeypatch.setattr(import_all, "_Cfg", lambda: _FakeConfig(tmp_path))
    steps = {"sync": 0, "sanitize": 0, "health": 0}

    def _count(name, result=None):
        def inner(*a, **k):
            steps[name] += 1
            return result
        return inner

    monkeypatch.setattr(import_all, "_run_sync_registry_to_devices", _count("sync"))
    monkeypatch.setattr(import_all, "_run_post_import_sanitize", _count("sanitize", []))
    monkeypatch.setattr(import_all, "_run_outbreak_source_health", _count("health", ([], [], [])))
    return steps


# ── --only-exact ──────────────────────────────────────────────────────────────

def test_analyse_exact_stem_excludes_longer_names(analyse, monkeypatch, record):
    _run(analyse_all, monkeypatch, "--only-exact", "analyse_pem")
    assert _called_stems(record) == ["analyse_pem"]


def test_analyse_exact_and_substring_are_mutually_exclusive(analyse, monkeypatch, record):
    with pytest.raises(SystemExit) as exc:
        _run(analyse_all, monkeypatch, "--only", "pem", "--only-exact", "analyse_pem")
    assert exc.value.code != 0
    assert _calls(record) == []


def test_analyse_substring_still_matches_longer_names(analyse, monkeypatch, record):
    _run(analyse_all, monkeypatch, "--only", "analyse_pem")
    assert set(_called_stems(record)) == {"analyse_pem", "analyse_pem_cascade", "analyse_pem_threshold"}


@pytest.mark.parametrize("module,stem", [
    (analyse_all, "analyse_missing"), (compute_all, "compute_missing"), (import_all, "import_missing"),
])
def test_unknown_stem_exits_before_any_run(module, stem, analyse, compute, importer, monkeypatch, record, capsys):
    with pytest.raises(SystemExit) as exc:
        _run(module, monkeypatch, "--only-exact", f"{stem}")
    assert exc.value.code != 0
    assert stem in capsys.readouterr().err
    assert _calls(record) == []


def test_on_demand_stem_is_not_an_exact_selection(analyse, monkeypatch, record):
    with pytest.raises(SystemExit) as exc:
        _run(analyse_all, monkeypatch, "--only-exact", "analyse_synthesis")
    assert exc.value.code != 0
    assert _calls(record) == []


def test_compute_selection_keeps_list_order_and_logs(compute, monkeypatch, record, logged):
    _run(compute_all, monkeypatch, "--only-exact", "compute_canonical,compute_stress")
    assert _called_stems(record) == ["compute_stress", "compute_canonical"]
    assert [row[1] for row in logged] == ["compute_stress.py", "compute_canonical.py"]


def test_compute_selection_keeps_recompute_flag(compute, monkeypatch, record):
    _run(compute_all, monkeypatch, "--only-exact", "compute_hrv_advanced", "--recompute")
    assert _calls(record) == [["compute_hrv_advanced.py", ["--rebuild"]]]


def test_compute_without_flag_runs_the_full_list(compute, monkeypatch, record):
    _run(compute_all, monkeypatch)
    assert _called_stems(record) == [Path(s).stem for s in compute_all.COMPUTE_SCRIPTS]


@pytest.mark.parametrize("stem,other", [
    ("import_polar", "import_polar_accesslink"),
    ("import_oura", "import_oura_csv"),
    ("import_garmin", "import_garmin_gdpr"),
])
def test_import_exact_stem_keeps_sanitising(stem, other, importer, monkeypatch, record):
    _run(import_all, monkeypatch, "--only-exact", stem)
    assert _called_stems(record) == [stem]
    assert other not in _called_stems(record)
    assert importer["sanitize"] == 1
    assert importer["health"] == 0


def test_import_special_importer_gets_full_run_arguments(importer, monkeypatch, record, tmp_path):
    _run(import_all, monkeypatch, "--only-exact", "import_ecg_logger", "--person", "PER-00000000")
    assert _calls(record) == [["import_ecg_logger.py",
                               ["--dir", str(tmp_path / "imports" / "ecglogger"), "--person", "PER-00000000"]]]


def test_import_without_flag_runs_inbox_all_importers_and_health_check(importer, monkeypatch, record):
    _run(import_all, monkeypatch)
    stems = _called_stems(record)
    assert stems[0] == "process_inbox"
    assert set(Path(n).stem for n in import_all.IMPORTERS) <= set(stems)
    assert {"import_ecg_logger", "import_ecg_apple"} <= set(stems)
    assert importer["sanitize"] == 1 and importer["health"] == 1


# ── --sanitize-only and post_import_sanitize.run ──────────────────────────────

def test_sanitize_only_runs_nothing_else(importer, monkeypatch, record):
    _run(import_all, monkeypatch, "--sanitize-only")
    assert _calls(record) == []
    assert importer == {"sync": 0, "sanitize": 1, "health": 0}


def test_sanitize_only_exits_non_zero_on_failed_step(importer, monkeypatch, capsys):
    monkeypatch.setattr(import_all, "_run_post_import_sanitize", lambda: ["scrub_pii"])
    with pytest.raises(SystemExit) as exc:
        _run(import_all, monkeypatch, "--sanitize-only")
    assert exc.value.code == 1
    assert "scrub_pii" in capsys.readouterr().err


@pytest.mark.parametrize("extra", [["--only-exact", "import_polar"], ["--update"], ["--from", "2000-01-01"]])
def test_sanitize_only_rejects_importer_options(extra, importer, monkeypatch, record):
    with pytest.raises(SystemExit) as exc:
        _run(import_all, monkeypatch, "--sanitize-only", *extra)
    assert exc.value.code != 0
    assert _calls(record) == [] and importer["sanitize"] == 0


def test_failed_sanitising_step_is_reported_and_later_steps_run(monkeypatch):
    ran = []

    def _broken_open():
        ran.append("opened")
        raise RuntimeError("boom")

    monkeypatch.setattr(post_import_sanitize, "open_db", _broken_open)
    monkeypatch.setattr(post_import_sanitize, "_pseudonymize_providers", lambda: ran.append("providers"))
    failed = post_import_sanitize.run()
    assert "scrub_pii" in failed and "check_anonymization" in failed
    assert "pseudonymize_providers" not in failed
    assert "providers" in ran


def test_full_import_exit_code_ignores_failed_sanitising(importer, monkeypatch):
    monkeypatch.setattr(import_all, "_run_post_import_sanitize", lambda errors: ["scrub_pii"])
    _run(import_all, monkeypatch)


# ── --on-demand: compute ──────────────────────────────────────────────────────

def test_compute_on_demand_forwards_and_logs(compute, monkeypatch, record, logged):
    _run(compute_all, monkeypatch, "--on-demand", "compute_orthostatic_detection", "--", "--date-from", "2000-01-01")
    assert _calls(record) == [["compute_orthostatic_detection.py", ["--date-from", "2000-01-01"]]]
    assert [row[:3] for row in logged] == [("compute", "compute_orthostatic_detection.py", 0)]


def test_compute_on_demand_dry_run_is_not_logged(compute, monkeypatch, record, logged):
    _run(compute_all, monkeypatch, "--on-demand", "compute_calibrate_sources", "--", "--dry-run")
    assert _called_stems(record) == ["compute_calibrate_sources"]
    assert logged == []


def test_compute_on_demand_failure_is_logged_and_exits_non_zero(compute, monkeypatch, logged):
    monkeypatch.setenv("CHILD_EXIT", "3")
    with pytest.raises(SystemExit) as exc:
        _run(compute_all, monkeypatch, "--on-demand", "compute_histamine_triggers")
    assert exc.value.code == 1
    assert [row[:3] for row in logged] == [("compute", "compute_histamine_triggers.py", 3)]


def test_compute_on_demand_unknown_stem_is_rejected(compute, monkeypatch, record, capsys):
    with pytest.raises(SystemExit) as exc:
        _run(compute_all, monkeypatch, "--on-demand", "compute_stress")
    assert exc.value.code != 0
    assert "compute_stress" in capsys.readouterr().err
    assert _calls(record) == []


def test_compute_full_run_excludes_on_demand_scripts(compute, monkeypatch, record):
    _run(compute_all, monkeypatch)
    assert not set(_called_stems(record)) & {Path(n).stem for n in compute_all.ON_DEMAND_COMPUTE_SCRIPTS}


@pytest.mark.parametrize("module", [analyse_all, compute_all])
def test_forwarded_arguments_need_on_demand(module, analyse, compute, monkeypatch, record):
    with pytest.raises(SystemExit) as exc:
        _run(module, monkeypatch, "--", "--dry-run")
    assert exc.value.code != 0
    assert _calls(record) == []


# ── --on-demand: analysis ─────────────────────────────────────────────────────

def test_analyse_on_demand_forwards_and_logs(analyse, monkeypatch, record, logged):
    _run(analyse_all, monkeypatch, "--on-demand", "analyse_ecg_session", "--", "--session", "42")
    assert _calls(record) == [["analyse_ecg_session.py", ["--session", "42"]]]
    assert [row[:3] for row in logged] == [("analysis", "analyse_ecg_session.py", 0)]


@pytest.mark.parametrize("stem,flag", [
    ("analyse_ecg_session", "--list"), ("analyse_reha_klinik_empfehlung", "--list-backends"),
    ("analyse_synthesis", "--dry-run"), ("analyse_skin", "--help"),
])
def test_analyse_on_demand_preview_is_not_logged(stem, flag, analyse, monkeypatch, record, logged):
    _run(analyse_all, monkeypatch, "--on-demand", stem, "--", flag)
    assert _called_stems(record) == [stem]
    assert logged == []


def test_analyse_on_demand_failure_is_logged_and_exits_non_zero(analyse, monkeypatch, logged):
    monkeypatch.setenv("CHILD_EXIT", "4")
    with pytest.raises(SystemExit) as exc:
        _run(analyse_all, monkeypatch, "--on-demand", "analyse_urine")
    assert exc.value.code == 4
    assert [row[:3] for row in logged] == [("analysis", "analyse_urine.py", 4)]


def test_analyse_on_demand_unknown_stem_is_rejected(analyse, monkeypatch, record, capsys):
    with pytest.raises(SystemExit) as exc:
        _run(analyse_all, monkeypatch, "--on-demand", "analyse_pem")
    assert exc.value.code != 0
    assert "analyse_pem" in capsys.readouterr().err
    assert _calls(record) == []


def test_analyse_on_demand_rejects_batch_options(analyse, monkeypatch, record):
    with pytest.raises(SystemExit) as exc:
        _run(analyse_all, monkeypatch, "--on-demand", "analyse_urine", "--from", "2000-01-01")
    assert exc.value.code != 0
    assert _calls(record) == []


def test_analyse_full_run_excludes_on_demand_scripts(analyse, monkeypatch, record):
    _run(analyse_all, monkeypatch)
    assert not set(_called_stems(record)) & {Path(n).stem for n in analyse_all.ON_DEMAND_ANALYSE_SCRIPTS}


def test_analyse_on_demand_prompt_works_on_a_real_terminal(tmp_path):
    script = tmp_path / "analysis" / "manual" / "analyse_urine.py"
    script.parent.mkdir(parents=True)
    script.write_text("answer = input('FRAGE? ')\nprint('ANTWORT=' + answer)\n", encoding="utf-8")
    log_file = tmp_path / "logged.txt"
    wrapper = tmp_path / "wrapper.py"
    wrapper.write_text(
        "import sys\n"
        f"sys.path.insert(0, {str(SCRIPTS)!r})\n"
        "import analyse_all\n"
        "from modules import pipeline_runner\n"
        f"analyse_all.SCRIPT_DIR = __import__('pathlib').Path({str(tmp_path)!r})\n"
        f"pipeline_runner._log_analysis_run = lambda *a: open({str(log_file)!r}, 'w').write(a[0])\n"
        "sys.argv = ['analyse_all', '--on-demand', 'analyse_urine']\n"
        "analyse_all.main()\n",
        encoding="utf-8",
    )
    env = {**os.environ, "HOME": str(tmp_path)}
    master, slave = pty.openpty()
    proc = subprocess.Popen([sys.executable, str(wrapper)], stdin=slave, stdout=slave, stderr=slave, env=env)
    os.close(slave)
    seen = b""
    answered = False
    try:
        while True:
            ready, _, _ = select.select([master], [], [], 30)
            assert ready, f"no output from child: {seen!r}"
            try:
                chunk = os.read(master, 4096)
            except OSError:
                break
            if not chunk:
                break
            seen += chunk
            if not answered and b"FRAGE?" in seen:
                os.write(master, b"ja\n")
                answered = True
    finally:
        os.close(master)
        proc.wait(timeout=30)
    assert proc.returncode == 0
    assert b"ANTWORT=ja" in seen
    assert log_file.read_text(encoding="utf-8") == "analyse_urine.py"


# ── Registries ────────────────────────────────────────────────────────────────

def test_compute_requires_covers_the_list_and_points_backwards():
    order = compute_all.COMPUTE_SCRIPTS
    assert list(compute_all.COMPUTE_REQUIRES) == order
    for script, requirements in compute_all.COMPUTE_REQUIRES.items():
        for requirement in requirements:
            assert order.index(requirement) < order.index(script), (script, requirement)


def test_compute_reads_later_point_forwards():
    order = compute_all.COMPUTE_SCRIPTS
    for script, later in compute_all.COMPUTE_READS_LATER.items():
        for other in later:
            assert order.index(other) > order.index(script), (script, other)


def _read_names(script: str) -> set[str]:
    return set(re.findall(r"(?:FROM|JOIN)\s+(\w+)", (SCRIPTS / script).read_text(encoding="utf-8")))


@pytest.mark.parametrize("reader,table,producer", [
    ("compute/compute_af_evidence.py", "ppi_windows", "compute/compute_arrhythmia.py"),
    ("compute/compute_stress.py", "ppi_hrv_advanced", "compute/compute_hrv_advanced.py"),
    ("compute/compute_clinical.py", "pem_correlation", "compute/compute_postinfectious.py"),
    ("compute/compute_daily_context.py", "pem_evidence_scores", "compute/compute_pem.py"),
    ("compute/compute_acute_events.py", "personal_baseline", "compute/compute_personal_baseline.py"),
    ("compute/compute_ans_dysfunction_evidence.py", "daily_context", "compute/compute_daily_context.py"),
])
def test_compute_requires_matches_the_sql(reader, table, producer):
    assert table in _read_names(reader)
    assert producer in compute_all.COMPUTE_REQUIRES[reader]


def test_on_demand_lists_cover_existing_scripts_outside_the_full_runs():
    for name in compute_all.ON_DEMAND_COMPUTE_SCRIPTS:
        assert (SCRIPTS / name).exists() and name not in compute_all.COMPUTE_SCRIPTS
    for name in analyse_all.ON_DEMAND_ANALYSE_SCRIPTS:
        assert (SCRIPTS / name).exists() and name not in analyse_all.ANALYSE_SCRIPTS


def test_declared_preview_flags_exist_in_their_scripts():
    for name, flags in analyse_all.ON_DEMAND_ANALYSE_SCRIPTS.items():
        assert set(flags) <= analyse_all._supported_flags(SCRIPTS / name), name


def test_orchestrators_import_with_an_empty_config_directory(tmp_path):
    env = {k: v for k, v in os.environ.items() if k != "KYORO_ACTIVE_PATIENT_DIR"}
    env["HOME"] = str(tmp_path)
    result = subprocess.run(
        [sys.executable, "-c",
         "import analyse_all, compute_all, import_all; print(len(compute_all.COMPUTE_REQUIRES))"],
        cwd=SCRIPTS, env=env, capture_output=True, text=True, timeout=120,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == str(len(compute_all.COMPUTE_SCRIPTS))
