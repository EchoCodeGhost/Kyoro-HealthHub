# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Tests for the TUI job runner with real child processes.

@tier        unit
@purpose.de  Prüft Streaming, Job-Sperre, Abbruch der Prozessgruppe, Dienste und den
             interaktiven Modus an einem echten Terminal.
@purpose.en  Checks streaming, the job lock, cancelling the process group, services and
             the interactive mode on a real terminal.
@method.de   Echte Unterprozesse und echte Pseudo-Terminals, keine Mocks.
@method.en   Real child processes and real pseudo-terminals, no mocks.
@reads       temporäre Dateien
@writes      temporäre Dateien
@limits.de   App.suspend wird durch einen einfachen Kontext ersetzt; der Lauf mit der
             echten App steht in Abschnitt 6 des OpenSpec-Changes.
@limits.en   App.suspend is replaced by a plain context; the run with the real app is in
             section 6 of the OpenSpec change.
"""

import asyncio
import contextlib
import os
import pty
import select
import signal
import sys
import time
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).parent.parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

from modules import i18n
from tui.runner import MAX_LINE_CHARS, JobBusy, JobRunner

TIMEOUT_S = 30


def _run(coro):
    return asyncio.run(asyncio.wait_for(coro, TIMEOUT_S))


def _script(tmp_path: Path, body: str, name: str = "child.py") -> list[str]:
    path = tmp_path / name
    path.write_text(body, encoding="utf-8")
    return [sys.executable, str(path)]


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    # Ein Zombie zählt nicht als laufend. Ohne /proc (macOS) räumt launchd verwaiste Prozesse weg.
    try:
        return Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[0] != "Z"
    except OSError:
        return not Path("/proc/self").exists()


async def _wait_for_file(path: Path) -> str:
    while not (path.exists() and path.read_text()):
        await asyncio.sleep(0.02)
    return path.read_text()


async def _wait_until_dead(pid: int) -> bool:
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        if not _alive(pid):
            return True
        await asyncio.sleep(0.02)
    return False


# ── Piped ─────────────────────────────────────────────────────────────────────

def test_output_arrives_before_exit(tmp_path):
    release = tmp_path / "release"
    argv = _script(tmp_path, f"""
import pathlib, time
print("READY")
while not pathlib.Path({str(release)!r}).exists():
    time.sleep(0.01)
print("END")
""")
    lines = []

    def on_line(line):
        lines.append(line)
        release.touch()

    result = _run(JobRunner().run_piped(argv, on_line))
    assert lines == ["READY", "END"]
    assert result.returncode == 0 and not result.cancelled


def test_all_output_is_delivered_and_stderr_is_merged(tmp_path):
    argv = _script(tmp_path, """
import sys
for i in range(50000):
    print("line", i)
print("ERR", file=sys.stderr)
print("LAST")
sys.exit(3)
""")
    lines = []
    result = _run(JobRunner().run_piped(argv, lines.append))
    assert result.returncode == 3
    assert len(lines) == 50002
    assert "ERR" in lines and lines[-1] == "LAST"


def test_result_keeps_no_output(tmp_path):
    result = _run(JobRunner().run_piped(_script(tmp_path, "print('MARKER')")))
    assert "MARKER" not in repr(result)


def test_long_line_without_newline_does_not_break_the_stream(tmp_path):
    argv = _script(tmp_path, f"import sys; sys.stdout.write('x' * {MAX_LINE_CHARS * 3 + 5})")
    lines = []
    result = _run(JobRunner().run_piped(argv, lines.append))
    assert result.returncode == 0
    assert sum(map(len, lines)) == MAX_LINE_CHARS * 3 + 5
    assert max(map(len, lines)) <= MAX_LINE_CHARS


def test_invalid_utf8_and_crlf_are_handled(tmp_path):
    argv = _script(tmp_path, r"import sys; sys.stdout.buffer.write(b'a\xff\r\nb')")
    lines = []
    _run(JobRunner().run_piped(argv, lines.append))
    assert lines == ["a�", "b"]


def test_input_fails_visibly_instead_of_hanging(tmp_path):
    lines = []
    result = _run(JobRunner().run_piped(_script(tmp_path, "input('question? ')"), lines.append))
    assert result.returncode != 0
    assert any("EOFError" in line for line in lines)


def test_shell_characters_stay_literal(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    value = "$(touch injected); `touch injected` | touch injected"
    argv = _script(tmp_path, "import sys; print(sys.argv[1])") + [value]
    lines = []
    _run(JobRunner().run_piped(argv, lines.append))
    assert lines == [value]
    assert not (tmp_path / "injected").exists()


def test_child_environment_and_session(tmp_path, monkeypatch):
    previous = i18n.get_lang()
    i18n.set_lang("en")
    try:
        argv = _script(tmp_path, """
import os
print(os.environ["PYTHONUNBUFFERED"], os.environ["MPLBACKEND"], os.environ["KYORO_LANG"], os.getsid(0) == os.getpid())
""")
        lines = []
        _run(JobRunner().run_piped(argv, lines.append))
    finally:
        i18n.set_lang(previous)
    assert lines == ["1 Agg en True"]


def test_runner_creates_no_files(tmp_path, monkeypatch):
    work = tmp_path / "work"
    work.mkdir()
    monkeypatch.chdir(work)
    _run(JobRunner().run_piped(_script(tmp_path, "print('MARKER')")))
    assert list(work.iterdir()) == []


# ── Job lock ──────────────────────────────────────────────────────────────────

def test_second_job_is_refused_until_the_first_ends(tmp_path):
    release = tmp_path / "release"
    slow = _script(tmp_path, f"""
import pathlib, time
while not pathlib.Path({str(release)!r}).exists():
    time.sleep(0.01)
""")
    quick = _script(tmp_path, "pass", "quick.py")

    async def scenario():
        runner = JobRunner()
        first = asyncio.create_task(runner.run_piped(slow))
        await asyncio.sleep(0)
        assert runner.busy and runner.elapsed_s is not None
        with pytest.raises(JobBusy):
            await runner.run_piped(quick)
        with pytest.raises(JobBusy):
            runner.run_interactive(quick, contextlib.nullcontext)
        release.touch()
        assert (await first).returncode == 0
        assert not runner.busy and runner.elapsed_s is None
        assert (await runner.run_piped(quick)).returncode == 0

    _run(scenario())


def test_lock_is_released_when_the_program_does_not_exist(tmp_path):
    async def scenario():
        runner = JobRunner()
        with pytest.raises(OSError):
            await runner.run_piped([str(tmp_path / "missing")])
        assert not runner.busy

    _run(scenario())


def test_failing_callback_ends_cleanly_and_is_reported(tmp_path):
    argv = _script(tmp_path, "for i in range(1000): print(i)")

    def broken(_line):
        raise KeyError("callback")

    async def scenario():
        runner = JobRunner()
        with pytest.raises(KeyError):
            await runner.run_piped(argv, broken)
        assert not runner.busy

    _run(scenario())


# ── Cancel ────────────────────────────────────────────────────────────────────

ORCHESTRATOR = """
import pathlib, subprocess, sys
child = subprocess.Popen([sys.executable, "-c", {child!r}])
pathlib.Path({pid_file!r}).write_text(str(child.pid))
print("started", flush=True)
child.wait()
"""
SLEEPER = "import time; time.sleep(25)"
STUBBORN = "import signal, time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(25)"


def _orchestrator(tmp_path, child=SLEEPER):
    pid_file = tmp_path / "child.pid"
    return _script(tmp_path, ORCHESTRATOR.format(child=child, pid_file=str(pid_file)), "orchestrator.py"), pid_file


def test_cancel_ends_the_orchestrator_and_its_child(tmp_path):
    argv, pid_file = _orchestrator(tmp_path)

    async def scenario():
        runner = JobRunner()
        job = asyncio.create_task(runner.run_piped(argv))
        pid = int(await _wait_for_file(pid_file))
        assert _alive(pid)
        assert await runner.cancel() is True
        result = await job
        assert result.cancelled and result.returncode != 0
        assert await _wait_until_dead(pid)
        assert not runner.busy

    _run(scenario())


def test_cancel_kills_a_child_that_ignores_sigterm(tmp_path):
    argv, pid_file = _orchestrator(tmp_path, STUBBORN)

    async def scenario():
        runner = JobRunner(grace_s=0.5)
        job = asyncio.create_task(runner.run_piped(argv))
        pid = int(await _wait_for_file(pid_file))
        await asyncio.sleep(0.3)  # Zeit, den Signal-Handler zu setzen
        await runner.cancel()
        assert (await job).cancelled
        assert await _wait_until_dead(pid)

    _run(scenario())


def test_cancel_kills_a_parent_that_ignores_sigterm(tmp_path):
    ready = tmp_path / "ready"
    argv = _script(tmp_path, f"""
import pathlib, signal, time
signal.signal(signal.SIGTERM, signal.SIG_IGN)
pathlib.Path({str(ready)!r}).write_text("1")
time.sleep(25)
""")

    async def scenario():
        runner = JobRunner(grace_s=0.3)
        job = asyncio.create_task(runner.run_piped(argv))
        await _wait_for_file(ready)
        await runner.cancel()
        result = await job
        assert result.cancelled and result.returncode == -signal.SIGKILL

    _run(scenario())


def test_cancelling_the_awaiting_task_ends_the_process_group(tmp_path):
    argv, pid_file = _orchestrator(tmp_path)

    async def scenario():
        runner = JobRunner()
        job = asyncio.create_task(runner.run_piped(argv))
        pid = int(await _wait_for_file(pid_file))
        job.cancel()
        with pytest.raises(asyncio.CancelledError):
            await job
        assert await _wait_until_dead(pid)
        assert not runner.busy

    _run(scenario())


def test_cancel_without_a_job_returns_false():
    assert _run(JobRunner().cancel()) is False


def test_job_returns_when_a_grandchild_keeps_the_pipe_open(tmp_path):
    pid_file = tmp_path / "grandchild.pid"
    argv = _script(tmp_path, f"""
import pathlib, subprocess, sys
child = subprocess.Popen([sys.executable, "-c", {SLEEPER!r}])
pathlib.Path({str(pid_file)!r}).write_text(str(child.pid))
print("done")
""")

    async def scenario():
        started = time.monotonic()
        result = await JobRunner().run_piped(argv)
        assert result.returncode == 0
        assert time.monotonic() - started < 10
        os.kill(int(pid_file.read_text()), signal.SIGKILL)

    _run(scenario())


def test_cancel_returns_when_a_detached_grandchild_keeps_the_pipe_open(tmp_path):
    pid_file = tmp_path / "detached.pid"
    argv = _script(tmp_path, f"""
import pathlib, subprocess, sys, time
child = subprocess.Popen([sys.executable, "-c", {SLEEPER!r}], start_new_session=True)
pathlib.Path({str(pid_file)!r}).write_text(str(child.pid))
time.sleep(25)
""")

    async def scenario():
        runner = JobRunner(grace_s=0.3)
        job = asyncio.create_task(runner.run_piped(argv))
        pid = int(await _wait_for_file(pid_file))
        started = time.monotonic()
        await runner.cancel()
        assert (await job).cancelled
        assert time.monotonic() - started < 10
        os.kill(pid, signal.SIGKILL)

    _run(scenario())


def test_no_lines_reach_the_callback_after_the_job_ended(tmp_path):
    argv = _script(tmp_path, """
import subprocess, sys
code = "import time; time.sleep(3); print('LATE', flush=True)"
subprocess.Popen([sys.executable, "-c", code])
print("EARLY", flush=True)
""")
    lines = []

    async def scenario():
        await JobRunner().run_piped(argv, lines.append)
        await asyncio.sleep(1.5)

    _run(scenario())
    assert lines == ["EARLY"]


# ── Services ──────────────────────────────────────────────────────────────────

def test_service_runs_outside_the_job_lock_and_stops(tmp_path):
    service = _script(tmp_path, SLEEPER, "service.py")
    job = _script(tmp_path, "print('job')", "job.py")

    async def scenario():
        runner = JobRunner()
        assert await runner.start_service("db", service) is True
        assert await runner.start_service("db", service) is False
        assert runner.service_running("db") and not runner.busy
        assert (await runner.run_piped(job)).returncode == 0
        assert await runner.stop_service("db") is True
        assert not runner.service_running("db")
        assert await runner.stop_service("db") is False

    _run(scenario())


def test_chatty_service_does_not_stall_on_a_full_pipe(tmp_path):
    done = tmp_path / "done"
    argv = _script(tmp_path, f"""
import pathlib
for i in range(20000):
    print("y" * 200, flush=True)
pathlib.Path({str(done)!r}).write_text("1")
""")

    async def scenario():
        runner = JobRunner()
        await runner.start_service("chatty", argv)
        await _wait_for_file(done)
        await runner.stop_all_services()

    _run(scenario())


def test_stop_all_services_ends_children_too(tmp_path):
    argv, pid_file = _orchestrator(tmp_path)

    async def scenario():
        runner = JobRunner()
        await runner.start_service("one", argv)
        await runner.start_service("two", _script(tmp_path, SLEEPER, "two.py"))
        pid = int(await _wait_for_file(pid_file))
        assert await runner.stop_all_services() == 2
        assert await _wait_until_dead(pid)
        assert not runner.service_running("one") and not runner.service_running("two")

    _run(scenario())


def test_service_can_restart_after_it_ended_by_itself(tmp_path):
    argv = _script(tmp_path, "pass")

    async def scenario():
        runner = JobRunner()
        await runner.start_service("short", argv)
        while runner.service_running("short"):
            await asyncio.sleep(0.01)
        assert await runner.start_service("short", argv) is True
        await runner.stop_all_services()

    _run(scenario())


# ── Interactive ───────────────────────────────────────────────────────────────

HARNESS = """
import contextlib, sys
sys.path.insert(0, {scripts!r})
from tui.runner import JobRunner

@contextlib.contextmanager
def suspend():
    print("SUSPENDED", flush=True)
    yield
    print("RESUMED", flush=True)

result = JobRunner().run_interactive([sys.executable, {child!r}], suspend)
print("PARENT-OK", result.returncode, flush=True)
"""


def _run_on_terminal(tmp_path, child_body, on_output, env=None):
    child = tmp_path / "interactive_child.py"
    child.write_text(child_body, encoding="utf-8")
    harness = tmp_path / "harness.py"
    harness.write_text(HARNESS.format(scripts=str(SCRIPTS), child=str(child)), encoding="utf-8")
    pid, fd = pty.fork()
    if pid == 0:
        os.environ.update(env or {})
        os.execv(sys.executable, [sys.executable, str(harness)])
    seen = b""
    deadline = time.monotonic() + TIMEOUT_S
    try:
        while time.monotonic() < deadline:
            ready, _, _ = select.select([fd], [], [], 1)
            if not ready:
                continue
            try:
                chunk = os.read(fd, 4096)
            except OSError:
                break
            if not chunk:
                break
            seen += chunk
            on_output(fd, seen)
    finally:
        os.close(fd)
        with contextlib.suppress(ChildProcessError):
            os.waitpid(pid, 0)
    return seen.decode("utf-8", "replace")


def test_interactive_script_gets_the_real_terminal(tmp_path):
    answered = []

    def on_output(fd, seen):
        if b"QUESTION?" in seen and not answered:
            answered.append(True)
            os.write(fd, b"yes\n")

    output = _run_on_terminal(tmp_path, """
import os, sys
answer = input("QUESTION? ")
print("ANSWER=" + answer, sys.stdin.isatty(), os.getpgrp() == os.tcgetpgrp(0))
""", on_output)
    assert "ANSWER=yes True True" in output
    assert output.index("SUSPENDED") < output.index("QUESTION?") < output.index("RESUMED")
    assert "PARENT-OK 0" in output


def test_ctrl_c_interrupts_the_script_but_not_the_tui(tmp_path):
    sent = []

    def on_output(fd, seen):
        if b"WAITING" in seen and not sent:
            sent.append(True)
            os.write(fd, b"\x03")

    output = _run_on_terminal(tmp_path, """
import time
print("WAITING", flush=True)
try:
    time.sleep(25)
except KeyboardInterrupt:
    print("CHILD-INTERRUPTED", flush=True)
    raise SystemExit(7)
""", on_output)
    assert "CHILD-INTERRUPTED" in output
    assert "PARENT-OK 7" in output


def test_interactive_restores_signal_handler_and_lock(tmp_path):
    before = signal.getsignal(signal.SIGINT)
    runner = JobRunner()
    result = runner.run_interactive(_script(tmp_path, "pass"), contextlib.nullcontext)
    assert result.returncode == 0 and not result.cancelled
    assert not runner.busy
    assert signal.getsignal(signal.SIGINT) is before
