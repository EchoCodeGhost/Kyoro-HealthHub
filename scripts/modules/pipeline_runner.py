# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
pipeline_runner.py — gemeinsamer Subprozess-Runner für Master-Pipeline-Skripte.

@tier        infrastructure
@purpose.de  Führt ein Pipeline-Skript (Importer/Compute/Analyse) als Subprozess aus
             und stellt sicher, dass dessen Ausgabe bei einem Absturz nicht verloren
             geht. Wird von import_all.py, compute_all.py und analyse_all.py geteilt,
             damit alle drei Master-Skripte sich bei Fehlern gleich verhalten.
@purpose.en  Runs a pipeline script (importer/compute/analysis) as a subprocess and
             ensures its output isn't lost on a crash. Shared by import_all.py,
             compute_all.py and analyse_all.py so all three master scripts behave
             identically on failure.
@method.de   subprocess.run(..., capture_output=True, env mit PYTHONUNBUFFERED=1)
             statt Weiterleitung an das ererbte stdout/stderr. capture_output
             sorgt für saubere Reihenfolge und erlaubt gezielte Ausgabe der
             letzten 20 stderr-Zeilen bei Fehlern; PYTHONUNBUFFERED verhindert,
             dass ein hart abgeschossener Kindprozess (z. B. OOM-Kill) seine
             block-gepufferte, noch ungeflushte Ausgabe verliert, bevor sie
             überhaupt geschrieben wurde. check_import_log=True (von
             import_all.py gesetzt) zählt vor/nach dem Subprozess die
             Gesamt-Zeilenzahl aller Tabellen (außer import_log) in health.db
             und medicine.db; sind nach einem erfolgreichen Lauf mehr
             Datenzeilen vorhanden, aber kein neuer import_log-Eintrag, gilt
             das als Chain-of-Custody-Verstoß. Bewusst auf Lauf-Ebene statt
             pro SQL-Transaktion geprüft: viele Importer committen mehrfach
             und loggen erst am Ende (z. B. import_polar.py: 21 Commits, 1
             log_import()-Aufruf) — eine Prüfung pro Commit würde diese
             bestehende, funktionierende Architektur brechen. log_compute=True
             (von compute_all.py gesetzt) schreibt nach jedem Subprozess-Lauf
             einen compute_log-Eintrag in health.db (Skriptname, aktueller
             Git-Commit-Hash via `git rev-parse HEAD`, Returncode, Laufzeit) —
             Pendant zu import_log für Compute-Läufe, da abgeleitete Tabellen
             bei jedem Lauf per DELETE+Neuberechnung überschrieben werden und
             sonst nicht rekonstruierbar wäre, mit welchem Code-Stand ein
             bestimmtes Ergebnis berechnet wurde. log_analysis=True (von
             analyse_all.py gesetzt) schreibt analog einen analysis_log-Eintrag
             (gleiche Felder wie compute_log, ueber denselben internen
             _log_pipeline_run()-Helper) — Analyse-Skripte schreiben nicht in
             Quelltabellen und waeren sonst ueberhaupt nicht auditierbar.
@method.en   subprocess.run(..., capture_output=True, env with PYTHONUNBUFFERED=1)
             instead of inheriting stdout/stderr. capture_output gives clean
             ordering and lets us print the last 20 stderr lines on failure;
             PYTHONUNBUFFERED prevents a hard-killed child (e.g. OOM-killed)
             from losing block-buffered, unflushed output before it was ever
             written. check_import_log=True (set by import_all.py) counts the
             total row count across all tables (except import_log) in
             health.db and medicine.db before/after the subprocess; if a
             successful run leaves more data rows but no new import_log
             entry, that's treated as a chain-of-custody violation. Checked
             deliberately at the run level, not per SQL transaction: many
             importers commit multiple times and log only once at the end
             (e.g. import_polar.py: 21 commits, 1 log_import() call) — a
             per-commit check would break this existing, working
             architecture. log_compute=True (set by compute_all.py) writes a
             compute_log entry to health.db after every subprocess run
             (script name, current git commit hash via `git rev-parse HEAD`,
             return code, duration) — the compute-side counterpart to
             import_log, since derived tables are overwritten via
             DELETE+recompute on every run and would otherwise leave no way
             to reconstruct which code version produced a given result.
             log_analysis=True (set by analyse_all.py) analogously writes an
             analysis_log entry (same fields as compute_log, via the same
             internal _log_pipeline_run() helper) — analysis scripts don't
             write to source tables and would otherwise be unauditable.
@reads       health.db, medicine.db (nur für den Zeilenzahl-Vergleich bei check_import_log)
@writes      compute_log in health.db, wenn log_compute=True; analysis_log in health.db, wenn log_analysis=True (sonst nichts direkt) — die aufgerufenen Kindskripte lesen/schreiben die DB selbst
@limits.de   Kein Live-Streaming — Ausgabe erscheint erst nach Prozessende. Für
             lange Einzelskripte (z. B. Polar-Import) ist das ein bewusster
             Trade-off gegen verschluckte Fehlermeldungen. check_import_log
             erkennt nur "Daten geschrieben, aber gar kein Log-Eintrag" auf
             Lauf-Ebene — keine feingranulare Zuordnung, welche Tabelle/Quelle
             betroffen war, und keine Erkennung von falschen/unvollständigen
             (aber vorhandenen) Log-Einträgen.

@relevance.de  Ermöglicht die Pipeline-Verarbeitung, essentiell für die Datenverarbeitungsworkflows
@relevance.en  Enables pipeline processing, essential for data processing workflows
@limits.en   No live streaming — output only appears after the process exits. For
             long-running individual scripts (e.g. Polar import) this is a
             deliberate trade-off against swallowed error messages.
             check_import_log only detects "data written but no log entry at
             all" at the run level — no fine-grained attribution of which
             table/source was affected, and no detection of wrong/incomplete
             (but present) log entries.
@usage
    from modules.pipeline_runner import run_pipeline_script
    errors: list[str] = []
    run_pipeline_script("import_all", script_path, cmd, errors)
    run_pipeline_script("import_all", script_path, cmd, errors, check_import_log=True)
    run_pipeline_script("compute_all", script_path, cmd, errors, show_command=True)
    run_pipeline_script("compute_all", script_path, cmd, errors, log_compute=True)
    run_pipeline_script("analyse_all", script_path, cmd, errors, log_analysis=True)
"""

import os
import subprocess
import sys
import time
from pathlib import Path

from modules.base import _git_commit_hash  # re-export: pipeline_runner's own former home
from modules.i18n import t

REPO_ROOT = Path(__file__).resolve().parents[2]


def _log_pipeline_run(table_name: str, script_name: str, returncode: int,
                      duration_s: float) -> None:
    """Schreibt einen Log-Eintrag in compute_log oder analysis_log — Pendant zu
    log_import() fuer Compute-/Analyse-Laeufe, die keine Quelltabellen schreiben
    und daher nicht ueber log_import() erfassbar sind.

    Erstellt die Tabelle bei Bedarf selbst (CREATE TABLE IF NOT EXISTS), analog
    zum Muster in den Compute-Skripten selbst, statt sich auf eine separate
    Migration bestehender health.db-Installationen zu verlassen. Kein person-Feld:
    ein compute_all.py/analyse_all.py-Lauf verarbeitet die gesamte DB, nicht die
    Daten einer einzelnen Person (s. design.md Non-Goals in add-provenance-logging).
    table_name kommt aus einer festen, internen Konstantenmenge (COMPUTE_LOG_TABLE/
    ANALYSIS_LOG_TABLE), nie aus Nutzereingabe — String-Interpolation hier ist
    daher unkritisch, kein SQL-Injection-Vektor.
    """
    from modules.db import open_db
    try:
        conn = open_db()
    except Exception:
        return
    try:
        conn.execute(f"""
            CREATE TABLE IF NOT EXISTS {table_name} (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                ts_run        TEXT NOT NULL,
                script        TEXT NOT NULL,
                git_commit    TEXT,
                returncode    INTEGER NOT NULL DEFAULT 0,
                duration_s    REAL
            )
        """)
        conn.execute(
            f"INSERT INTO {table_name} (ts_run, script, git_commit, returncode, duration_s)"
            " VALUES (datetime('now'), ?, ?, ?, ?)",
            (script_name, _git_commit_hash(), returncode, duration_s),
        )
        conn.commit()
    finally:
        conn.close()


def _log_compute_run(script_name: str, returncode: int, duration_s: float) -> None:
    _log_pipeline_run("compute_log", script_name, returncode, duration_s)


def _log_analysis_run(script_name: str, returncode: int, duration_s: float) -> None:
    _log_pipeline_run("analysis_log", script_name, returncode, duration_s)


def _snapshot_row_totals(open_fn) -> "tuple[int, int] | None":
    """Zählt Zeilen über alle Tabellen (außer import_log) + import_log selbst.

    Gibt None zurück, wenn die DB nicht geöffnet werden kann (z. B. fehlende
    medicine.db bei einer Installation, die nur health.db nutzt) — das ist
    kein Fehler, sondern schlicht "diese DB gibt es hier nicht/noch nicht".
    """
    try:
        conn = open_fn()
    except Exception:
        return None
    try:
        tables = [
            row[0] for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            ).fetchall()
        ]
        data_total = 0
        log_total = 0
        for table in tables:
            count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            if table == "import_log":
                log_total = count
            else:
                data_total += count
        return data_total, log_total
    finally:
        conn.close()


def _check_import_log_compliance(
    script_name: str, prefix: str, before, errors: list[str],
    open_db_fn=None, open_medicine_db_fn=None,
) -> None:
    """Vergleicht Vorher/Nachher-Snapshots und meldet Verstöße (s. @method oben).

    open_db_fn/open_medicine_db_fn MÜSSEN dieselben sein wie beim Vorher-Snapshot
    (Default: modules.db.open_db/open_medicine_db) — sonst wird eine falsche DB
    verglichen und Verstöße bleiben unentdeckt (in Tests wichtig: hier lassen
    sich gezielt Fake-Connections statt der echten health.db einsetzen).
    """
    if open_db_fn is None or open_medicine_db_fn is None:
        from modules.db import open_db, open_medicine_db
        open_db_fn = open_db_fn or open_db
        open_medicine_db_fn = open_medicine_db_fn or open_medicine_db

    after = (_snapshot_row_totals(open_db_fn), _snapshot_row_totals(open_medicine_db_fn))
    for label, snap_before, snap_after in (
        ("health.db", before[0], after[0]),
        ("medicine.db", before[1], after[1]),
    ):
        if snap_before is None or snap_after is None:
            continue
        data_before, log_before = snap_before
        data_after, log_after = snap_after
        if data_after > data_before and log_after == log_before:
            print(
                t(f"[{prefix}] CHAIN-OF-CUSTODY-WARNUNG: {script_name} hat {data_after - data_before} "
                  f"Zeile(n) in {label} geschrieben, aber keinen neuen import_log-Eintrag erzeugt.",
                  f"[{prefix}] CHAIN-OF-CUSTODY WARNING: {script_name} wrote {data_after - data_before} "
                  f"row(s) to {label} but produced no new import_log entry."),
                file=sys.stderr,
            )
            errors.append(f"{script_name} (no import_log entry despite {label} write)")


def run_pipeline_script(
    prefix: str,
    script_path: Path,
    cmd: list[str],
    errors: list[str],
    show_command: bool = False,
    check_import_log: bool = False,
    log_compute: bool = False,
    log_analysis: bool = False,
) -> None:
    """Führt ein Pipeline-Skript aus, protokolliert Erfolg/Fehler unter [prefix].

    PYTHONUNBUFFERED=1 im Kindprozess ist kein Stil-Detail: capture_output=True
    liest zuverlässig alles, was das Kind tatsächlich flusht — aber ein hart
    abgeschossener Kindprozess (z.B. OOM-Kill) verliert block-gepufferte,
    ungeflushte Ausgabe unwiederbringlich, bevor sie überhaupt in die Pipe
    geschrieben wird. Unbuffered schreibt sofort, nicht erst am Prozessende.
    """
    script_name = script_path.name
    print(t(f"\n[{prefix}] Starte {script_name} ...", f"\n[{prefix}] Starting {script_name} ..."))
    if show_command:
        print(t(f"  Befehl: {' '.join(cmd)}", f"  Command: {' '.join(cmd)}"))

    before = None
    open_db_fn = open_medicine_db_fn = None
    if check_import_log:
        from modules.db import open_db, open_medicine_db
        open_db_fn, open_medicine_db_fn = open_db, open_medicine_db
        before = (_snapshot_row_totals(open_db_fn), _snapshot_row_totals(open_medicine_db_fn))

    env = {**os.environ, "PYTHONUNBUFFERED": "1"}
    start = time.monotonic()
    result = subprocess.run(cmd, capture_output=True, text=True, env=env)
    duration_s = time.monotonic() - start
    if result.stdout:
        print(result.stdout, end="")

    if log_compute:
        _log_compute_run(script_name, result.returncode, duration_s)
    if log_analysis:
        _log_analysis_run(script_name, result.returncode, duration_s)

    if result.returncode != 0:
        print(t(f"[{prefix}] FEHLER: {script_name} beendet mit Code {result.returncode}",
                f"[{prefix}] ERROR: {script_name} exited with code {result.returncode}"),
              file=sys.stderr)
        if result.stderr:
            tail = result.stderr.splitlines()[-20:]
            for ln in tail:
                print(f"  {ln}", file=sys.stderr)
        errors.append(script_name)
    else:
        print(t(f"[{prefix}] {script_name} erfolgreich abgeschlossen.",
                f"[{prefix}] {script_name} completed successfully."))
        if check_import_log and before is not None:
            _check_import_log_compliance(script_name, prefix, before, errors, open_db_fn, open_medicine_db_fn)
