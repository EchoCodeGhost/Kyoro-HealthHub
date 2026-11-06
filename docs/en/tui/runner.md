# Job-Runner der Pipeline-TUI: startet Skripte als Unterprozesse.

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/tui/runner.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Runs at most one pipeline job at a time, streams its output and ends the whole process group on cancel. Services run outside the job lock, and interactive scripts run on the real terminal.

## Relevance

Ensures the TUI never writes to the same databases in parallel

## Method

Three modes. piped: own session, stdin=DEVNULL, stdout and stderr merged, PYTHONUNBUFFERED=1 and MPLBACKEND=Agg. interactive: runs inside the given suspend context in the same session, so the script keeps the terminal. service: own session, output is read continuously so the pipe can never fill up. Cancel sends SIGTERM to the process group, then SIGKILL after the grace period. Always an argument list, never a shell.

## Data flow

- **Reads:** `Keine`, `Tabellen`
- **Writes:** `Keine Tabellen, keine Dateien`

## Limitations

Keeps no output: lines only go to the callback. Background processes left by a job that ended normally keep running. POSIX only.

## Usage

```bash
runner = JobRunner()
result = await runner.run_piped([sys.executable, "script.py"], log.write_line)
await runner.cancel()
result = runner.run_interactive([sys.executable, "script.py"], app.suspend)
await runner.start_service("datasette", [sys.executable, "serve.py"])
```
