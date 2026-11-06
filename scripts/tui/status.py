# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Status der Pipeline und Personenliste für die TUI, nur lesend.

@tier        infrastructure
@purpose.de  Ermittelt für das Dashboard den Stand von Import, Compute und Analyse sowie
             die Personen für die Personenauswahl, ohne etwas zu schreiben.
@purpose.en  Determines the state of import, compute and analysis for the dashboard, and
             the persons for the person selection, without writing anything.
@method.de   Liest import_log, compute_log und analysis_log über modules.db.open_readonly.
             Zeitstempel werden nach UTC umgerechnet, nie als Text verglichen; ohne Zeitzone
             gelten sie als UTC, wie datetime('now'). Als Import zählen weder post_import_*
             noch compute_*. Veraltet ist Compute, wenn ein Import mit neuen Zeilen jünger
             ist als das Skript mit dem ältesten Erfolg. On-Demand-Läufe zählen nicht.
@method.en   Reads import_log, compute_log and analysis_log through
             modules.db.open_readonly. Timestamps are converted to UTC and never compared as
             text; without a time zone they count as UTC, like datetime('now'). Neither
             post_import_* nor compute_* rows count as imports. Compute is outdated when an
             import with new rows is newer than the script with the oldest success.
             On-demand runs do not count.
@reads       import_log, compute_log, analysis_log, alle Tabellen mit person-Spalte, identity.db
@writes      Nichts
@limits.de   read_person_choices kann bei kaltem Plattencache lange dauern und gehört in einen
             Hintergrund-Worker. Nicht lesbare Daten gelten als unbekannt. Schon der Zugriff
             auf OWN_PERSON_ID lädt identity_resolver, der das Schema von identity.db sicherstellt.
@limits.en   read_person_choices can take long with a cold disk cache and belongs in a
             background worker. Unreadable data counts as unknown. Accessing OWN_PERSON_ID
             already loads identity_resolver, which ensures the schema of identity.db.

@relevance.de  Zeigt, ob Analysen auf aktuellen Daten beruhen
@relevance.en  Shows whether analyses rest on current data
@usage
    status = read_pipeline_status()
    status.compute_outdated
    choices = read_person_choices()
"""

import sqlite3
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from analyse_all import ANALYSE_SCRIPTS, REQUIRES_INFECTION_DATE
from compute_all import COMPUTE_SCRIPTS
from health_config import OWN_PERSON_ID, Config
from modules.db import DB_ERRORS, open_readonly
from modules.i18n import t
from modules.identity_resolver import reverse_resolve

_NOT_IMPORTS = ("post_import_", "compute_")
# Enthalten Personen, ohne dass es Daten zu ihnen geben muss.
_NON_DATA_TABLES = frozenset({
    "access_log", "analysis_log", "audit_log", "compute_log", "devices", "import_log",
    "persons", "source_confidence", "source_priority",
})
# Hat ein Pseudonym, steht aber für Daten ohne zugeordnete Person.
_NOT_A_PERSON = frozenset({"unknown"})
_READ_ERRORS = (*DB_ERRORS, OSError, RuntimeError)


@dataclass(frozen=True)
class ImportStatus:
    known: bool = False
    last_import: datetime | None = None
    last_import_with_rows: datetime | None = None


@dataclass(frozen=True)
class StageStatus:
    known: bool = False
    last_run: datetime | None = None
    oldest_success: datetime | None = None
    never_succeeded: tuple[str, ...] = ()
    last_run_failed: tuple[str, ...] = ()


@dataclass(frozen=True)
class PipelineStatus:
    imports: ImportStatus
    compute: StageStatus
    analysis: StageStatus

    @property
    def compute_outdated(self) -> bool | None:
        """True, False, oder None, wenn es sich nicht feststellen lässt."""
        if not self.imports.known or not self.compute.known:
            return None
        newest = self.imports.last_import_with_rows
        if newest is None:
            return False
        oldest = self.compute.oldest_success
        return oldest is None or newest > oldest


@dataclass(frozen=True)
class PersonChoice:
    pseudonym: str
    display_name: str
    is_own: bool


def parse_ts(value: object) -> datetime | None:
    """Wandelt einen Zeitstempel nach UTC um; None, wenn er nicht lesbar ist."""
    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _tables(conn) -> set[str]:
    return {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def _import_rows(conn) -> list[tuple]:
    if "import_log" not in _tables(conn):
        return []
    return conn.execute("SELECT ts_run, source, rows_inserted FROM import_log").fetchall()


def _import_status(rows: Iterable[tuple]) -> ImportStatus:
    last = last_with_rows = None
    for ts_run, source, rows_inserted in rows:
        ts = parse_ts(ts_run)
        if ts is None or str(source or "").startswith(_NOT_IMPORTS):
            continue
        last = max(last, ts) if last else ts
        if rows_inserted:
            last_with_rows = max(last_with_rows, ts) if last_with_rows else ts
    return ImportStatus(True, last, last_with_rows)


def _stage_status(conn, table: str, registry: Iterable[str]) -> StageStatus:
    """Nur Skripte aus dem Register zählen, sonst überdeckte ein On-Demand-Lauf einen alten vollen Lauf."""
    names = [Path(script).name for script in registry]
    latest: dict[str, tuple[datetime, int]] = {}
    success: dict[str, datetime] = {}
    for script, ts_run, returncode in conn.execute(f"SELECT script, ts_run, returncode FROM {table}"):
        ts = parse_ts(ts_run)
        if ts is None or script not in names:
            continue
        if script not in latest or ts >= latest[script][0]:
            latest[script] = (ts, returncode)
        if returncode == 0 and (script not in success or ts > success[script]):
            success[script] = ts
    never = tuple(name for name in names if name not in success)
    return StageStatus(
        known=True,
        last_run=max((ts for ts, _ in latest.values()), default=None),
        oldest_success=None if never else min(success.values(), default=None),
        never_succeeded=never,
        last_run_failed=tuple(name for name in names if name in latest and latest[name][1] != 0),
    )


def read_pipeline_status() -> PipelineStatus:
    """Liest den Stand aller Stufen. Was nicht lesbar ist, bleibt known=False."""
    imports, compute, analysis = ImportStatus(), StageStatus(), StageStatus()
    try:
        cfg = Config()
        conn = open_readonly(cfg.db_path)
    except _READ_ERRORS:
        return PipelineStatus(imports, compute, analysis)
    try:
        tables = _tables(conn)
        if "import_log" in tables:
            rows = _import_rows(conn)
            try:
                medicine = open_readonly(cfg.medicine_db_path)
                try:
                    rows += _import_rows(medicine)
                finally:
                    medicine.close()
            except _READ_ERRORS:
                pass  # medicine.db ist optional; der Stand aus health.db bleibt gültig.
            imports = _import_status(rows)
        if "compute_log" in tables:
            compute = _stage_status(conn, "compute_log", COMPUTE_SCRIPTS)
        if "analysis_log" in tables:
            analysis = _stage_status(conn, "analysis_log", ANALYSE_SCRIPTS)
    except _READ_ERRORS:
        pass
    finally:
        conn.close()
    return PipelineStatus(imports, compute, analysis)


def skipped_without_infection_date() -> tuple[str, ...]:
    """Analyse-Skripte, die mangels clinical.infection_date übersprungen würden."""
    try:
        if Config().infection_date:
            return ()
    except (OSError, ValueError):
        pass
    return tuple(sorted(REQUIRES_INFECTION_DATE))


def _persons_in(conn) -> set[str]:
    persons: set[str] = set()
    for table in _tables(conn) - _NON_DATA_TABLES:
        columns = {row[1] for row in conn.execute(f'PRAGMA table_info("{table}")')}
        if "person" in columns:
            persons.update(row[0] for row in conn.execute(f'SELECT DISTINCT person FROM "{table}"'))
    return {person for person in persons if isinstance(person, str) and person.startswith("PER-")}


def _display_name(pseudonym: str) -> str:
    if pseudonym == OWN_PERSON_ID:
        return t("Ich selbst", "Myself")
    try:
        return reverse_resolve(pseudonym) or pseudonym
    except (sqlite3.Error, OSError):
        return pseudonym


def read_person_choices() -> list[PersonChoice]:
    """Personen mit Daten, die eigene zuerst. Mit nur einem Eintrag bleibt das Feld ausgeblendet.

    Ist nichts lesbar, bleibt nur die eigene Person übrig; das ist auch der CLI-Standard.
    """
    persons: set[str] = set()
    try:
        cfg = Config()
        for path in (cfg.db_path, cfg.medicine_db_path):
            try:
                conn = open_readonly(path)
            except _READ_ERRORS:
                continue
            try:
                persons |= _persons_in(conn)
            except _READ_ERRORS:
                pass
            finally:
                conn.close()
    except (OSError, ValueError):
        pass
    persons.add(OWN_PERSON_ID)
    named = ((p, _display_name(p)) for p in persons)
    choices = [PersonChoice(p, name, p == OWN_PERSON_ID) for p, name in named if name.lower() not in _NOT_A_PERSON]
    return sorted(choices, key=lambda c: (not c.is_own, c.display_name.casefold()))
