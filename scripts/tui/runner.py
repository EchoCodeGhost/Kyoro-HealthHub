# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Job-Runner der Pipeline-TUI: startet Skripte als Unterprozesse.

@tier        infrastructure
@purpose.de  Führt höchstens einen Pipeline-Job gleichzeitig aus, streamt seine Ausgabe
             und beendet beim Abbrechen die ganze Prozessgruppe. Daneben laufen Dienste
             außerhalb der Job-Sperre und interaktive Skripte am echten Terminal.
@purpose.en  Runs at most one pipeline job at a time, streams its output and ends the
             whole process group on cancel. Services run outside the job lock, and
             interactive scripts run on the real terminal.
@method.de   Drei Modi. piped: eigene Session, stdin=DEVNULL, stdout und stderr
             zusammengeführt, PYTHONUNBUFFERED=1 und MPLBACKEND=Agg. interactive: läuft
             innerhalb des übergebenen suspend-Kontexts in derselben Session, damit das
             Skript das Terminal behält. service: eigene Session, Ausgabe wird dauerhaft
             gelesen, damit die Pipe nie volllaufen kann. Abbrechen sendet SIGTERM an die
             Prozessgruppe und nach der Wartezeit SIGKILL. Immer eine Argumentliste, nie
             eine Shell.
@method.en   Three modes. piped: own session, stdin=DEVNULL, stdout and stderr merged,
             PYTHONUNBUFFERED=1 and MPLBACKEND=Agg. interactive: runs inside the given
             suspend context in the same session, so the script keeps the terminal.
             service: own session, output is read continuously so the pipe can never
             fill up. Cancel sends SIGTERM to the process group, then SIGKILL after the
             grace period. Always an argument list, never a shell.
@reads       Keine Tabellen
@writes      Keine Tabellen, keine Dateien
@limits.de   Behält keine Ausgabe: Zeilen gehen nur an den Callback. Hintergrundprozesse,
             die ein normal beendeter Job hinterlässt, laufen weiter. Nur POSIX.
@limits.en   Keeps no output: lines only go to the callback. Background processes left by
             a job that ended normally keep running. POSIX only.

@relevance.de  Grundlage dafür, dass die TUI nie parallel in dieselben Datenbanken schreibt
@relevance.en  Ensures the TUI never writes to the same databases in parallel
@usage
    runner = JobRunner()
    result = await runner.run_piped([sys.executable, "script.py"], log.write_line)
    await runner.cancel()
    result = runner.run_interactive([sys.executable, "script.py"], app.suspend)
    await runner.start_service("datasette", [sys.executable, "serve.py"])
"""

import asyncio
import codecs
import os
import signal
import subprocess
import threading
import time
from collections.abc import Callable, Sequence
from contextlib import AbstractContextManager
from dataclasses import dataclass

from modules.i18n import get_lang

GRACE_PERIOD_S = 5.0
# Ein Enkelprozess kann die Pipe nach dem Ende des Jobs offen halten.
DRAIN_TIMEOUT_S = 2.0
MAX_LINE_CHARS = 65536
_READ_SIZE = 65536
_POLL_S = 0.05

LineCallback = Callable[[str], None]


class JobBusy(Exception):
    """Es läuft bereits ein Job."""


@dataclass(frozen=True)
class JobResult:
    returncode: int
    cancelled: bool
    duration_s: float


def _child_env(**extra: str) -> dict[str, str]:
    return {**os.environ, "KYORO_LANG": get_lang(), **extra}


def _signal_group(pgid: int, signum: int) -> None:
    try:
        os.killpg(pgid, signum)
    except (ProcessLookupError, PermissionError):
        # macOS meldet PermissionError, wenn nur noch Zombies in der Gruppe sind.
        pass


def _group_exists(pgid: int) -> bool:
    try:
        os.killpg(pgid, 0)
    except (ProcessLookupError, PermissionError):
        return False
    return True


async def _exited(proc: asyncio.subprocess.Process) -> int:
    """Wartet auf das Prozessende. proc.wait() wartet zusätzlich auf das Schließen der
    Pipes und hinge an jedem Enkelprozess, der sie offen hält."""
    while proc.returncode is None:
        await asyncio.sleep(_POLL_S)
    return proc.returncode


async def _end_group(proc: asyncio.subprocess.Process, grace_s: float) -> None:
    """SIGTERM an die Gruppe, nach grace_s SIGKILL an alles, was noch läuft."""
    # Mit start_new_session ist die Prozessgruppen-ID die PID des Prozesses.
    pgid = proc.pid
    _signal_group(pgid, signal.SIGTERM)
    deadline = time.monotonic() + grace_s
    try:
        await asyncio.wait_for(_exited(proc), grace_s)
    except asyncio.TimeoutError:
        pass
    while _group_exists(pgid) and time.monotonic() < deadline:
        await asyncio.sleep(_POLL_S)
    _signal_group(pgid, signal.SIGKILL)
    await _exited(proc)


class _Sink:
    """Empfänger der Zeilen. Ohne on_line wird die Ausgabe nur noch abgeholt und verworfen."""

    def __init__(self, on_line: LineCallback | None):
        self.on_line = on_line
        self.failure: Exception | None = None

    def emit(self, line: str) -> None:
        if self.on_line is None or self.failure is not None:
            return
        try:
            self.on_line(line)
        except Exception as exc:  # noqa: BLE001
            # Weiterlesen, sonst bliebe das Kind an der vollen Pipe hängen.
            self.failure = exc


async def _pump(stream: asyncio.StreamReader, sink: _Sink) -> None:
    """Liest bis zum Ende der Pipe und meldet ganze Zeilen."""
    decoder = codecs.getincrementaldecoder("utf-8")("replace")
    pending = ""
    while chunk := await stream.read(_READ_SIZE):
        pending += decoder.decode(chunk)
        *lines, pending = pending.split("\n")
        for line in lines:
            sink.emit(line.removesuffix("\r"))
        while len(pending) >= MAX_LINE_CHARS:
            sink.emit(pending[:MAX_LINE_CHARS])
            pending = pending[MAX_LINE_CHARS:]
    pending += decoder.decode(b"", final=True)
    if pending:
        sink.emit(pending.removesuffix("\r"))


@dataclass
class _Service:
    proc: asyncio.subprocess.Process
    pump: asyncio.Task


class JobRunner:
    def __init__(self, grace_s: float = GRACE_PERIOD_S):
        self._grace_s = grace_s
        self._busy = False
        self._proc: asyncio.subprocess.Process | None = None
        self._cancel_requested = False
        self._started_at: float | None = None
        self._services: dict[str, _Service] = {}
        # Pipes, die Enkelprozesse über das Jobende hinaus offen halten
        self._draining: set[asyncio.Task] = set()

    @property
    def busy(self) -> bool:
        return self._busy

    @property
    def elapsed_s(self) -> float | None:
        """Laufzeit des aktuellen Jobs, None ohne Job."""
        return None if self._started_at is None else time.monotonic() - self._started_at

    def _claim(self) -> None:
        if self._busy:
            raise JobBusy()
        self._busy = True
        self._cancel_requested = False
        self._started_at = time.monotonic()

    def _release(self) -> None:
        self._busy = False
        self._proc = None
        self._started_at = None

    async def run_piped(self, argv: Sequence[str], on_line: LineCallback | None = None) -> JobResult:
        """Führt einen Job mit geschlossenem stdin aus und streamt seine Ausgabe an on_line.

        Wird die aufrufende Aufgabe abgebrochen, endet auch die Prozessgruppe.
        """
        self._claim()
        started = time.monotonic()
        try:
            proc = await asyncio.create_subprocess_exec(
                *argv,
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                env=_child_env(PYTHONUNBUFFERED="1", MPLBACKEND="Agg"),
                start_new_session=True,
            )
            self._proc = proc
            sink = _Sink(on_line)
            pump = asyncio.create_task(_pump(proc.stdout, sink))
            try:
                returncode = await _exited(proc)
                await asyncio.wait({pump}, timeout=DRAIN_TIMEOUT_S)
            except asyncio.CancelledError:
                sink.on_line = None
                self._keep_draining(pump)
                await asyncio.shield(_end_group(proc, self._grace_s))
                raise
            sink.on_line = None
            self._keep_draining(pump)
            if sink.failure is not None:
                raise sink.failure
            return JobResult(returncode, self._cancel_requested, time.monotonic() - started)
        finally:
            self._release()

    def _keep_draining(self, pump: asyncio.Task) -> None:
        if not pump.done():
            self._draining.add(pump)
            pump.add_done_callback(self._draining.discard)

    async def cancel(self) -> bool:
        """Beendet den laufenden Job samt Prozessgruppe. False, wenn keiner läuft."""
        proc = self._proc
        if proc is None or proc.returncode is not None:
            return False
        self._cancel_requested = True
        await _end_group(proc, self._grace_s)
        return True

    def run_interactive(self, argv: Sequence[str], suspend: Callable[[], AbstractContextManager]) -> JobResult:
        """Führt ein Skript am echten Terminal aus; suspend ist z. B. App.suspend.

        Bleibt in derselben Session, sonst verlöre das Skript sein Terminal. Strg+C erreicht
        auch diesen Prozess. Ein Handler statt SIG_IGN, weil Unterprozesse SIG_IGN erben und
        sich dann nicht mehr unterbrechen ließen.
        """
        self._claim()
        started = time.monotonic()
        previous = None
        in_main_thread = threading.current_thread() is threading.main_thread()
        try:
            if in_main_thread:
                previous = signal.signal(signal.SIGINT, lambda *_: None)
            with suspend():
                result = subprocess.run(list(argv), env=_child_env(), check=False)
            return JobResult(result.returncode, False, time.monotonic() - started)
        finally:
            if in_main_thread:
                signal.signal(signal.SIGINT, previous)
            self._release()

    def service_running(self, name: str) -> bool:
        service = self._services.get(name)
        return service is not None and service.proc.returncode is None

    async def start_service(self, name: str, argv: Sequence[str], on_line: LineCallback | None = None) -> bool:
        """Startet einen Dienst außerhalb der Job-Sperre. False, wenn er schon läuft."""
        if self.service_running(name):
            return False
        proc = await asyncio.create_subprocess_exec(
            *argv,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            env=_child_env(PYTHONUNBUFFERED="1"),
            start_new_session=True,
        )
        self._services[name] = _Service(proc, asyncio.create_task(_pump(proc.stdout, _Sink(on_line))))
        return True

    async def stop_service(self, name: str) -> bool:
        """Beendet einen Dienst samt Prozessgruppe. False, wenn er nicht lief."""
        service = self._services.pop(name, None)
        if service is None:
            return False
        was_running = service.proc.returncode is None
        await _end_group(service.proc, self._grace_s)
        service.pump.cancel()
        await asyncio.gather(service.pump, return_exceptions=True)
        return was_running

    async def stop_all_services(self) -> int:
        """Beendet alle Dienste und gibt die Zahl der laufenden zurück, die beendet wurden."""
        stopped = [await self.stop_service(name) for name in list(self._services)]
        return sum(stopped)
