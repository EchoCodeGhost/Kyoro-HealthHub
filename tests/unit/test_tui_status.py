# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Tests for the read-only database access and the TUI status queries.

@tier        unit
@purpose.de  Prüft, dass der Lesezugriff nichts verändert und der Status bei fehlenden,
             gesperrten oder nicht entschlüsselbaren Datenbanken unbekannt bleibt.
@purpose.en  Checks that read-only access changes nothing and that the status stays unknown
             for missing, locked or undecryptable databases.
@method.de   Echte temporäre SQLite- und SQLCipher-Dateien mit erfundenen Werten.
@method.en   Real temporary SQLite and SQLCipher files with made-up values.
@reads       temporäre Dateien
@writes      temporäre Dateien
@limits.de   Die Prüfung gegen die echten Datenbanken steht im OpenSpec-Change.
@limits.en   The check against the real databases is listed in the OpenSpec change.
"""

import hashlib
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import ClassVar

import pytest

SCRIPTS = Path(__file__).parent.parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

from compute_all import COMPUTE_SCRIPTS
from health_config import OWN_PERSON_ID
from modules import db
from modules.db import DB_ERRORS, open_readonly
from tui import status

OTHER = "PER-00000001"
SECOND = "PER-00000002"
COMPUTE_NAMES = [Path(s).name for s in COMPUTE_SCRIPTS]


def _utc(text):
    return datetime.fromisoformat(text).replace(tzinfo=timezone.utc)


def _make_db(path: Path, statements=()):
    conn = sqlite3.connect(path)
    for statement in statements:
        conn.execute(*statement) if isinstance(statement, tuple) else conn.execute(statement)
    conn.commit()
    conn.close()
    return path


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


IMPORT_LOG = "CREATE TABLE import_log (ts_run TEXT, source TEXT, rows_inserted INT, person TEXT)"
COMPUTE_LOG = "CREATE TABLE compute_log (ts_run TEXT, script TEXT, returncode INT)"
ANALYSIS_LOG = "CREATE TABLE analysis_log (ts_run TEXT, script TEXT, returncode INT)"


@pytest.fixture(autouse=True)
def _no_key(monkeypatch):
    monkeypatch.setattr(db, "_load_db_key", lambda cfg: None)
    monkeypatch.setattr("health_config.load", lambda *a, **k: {})


@pytest.fixture
def paths(tmp_path, monkeypatch):
    class _Cfg:
        db_path = tmp_path / "health.db"
        medicine_db_path = tmp_path / "medicine.db"
        infection_date = None
        names: ClassVar[dict] = {}

    monkeypatch.setattr(status, "Config", _Cfg)
    monkeypatch.setattr(status, "reverse_resolve", lambda pseudonym: _Cfg.names.get(pseudonym))
    return _Cfg


# ── open_readonly ─────────────────────────────────────────────────────────────

def test_readonly_changes_nothing_and_installs_no_triggers(tmp_path):
    path = _make_db(tmp_path / "x.db", ["CREATE TABLE t (a INT)", "INSERT INTO t VALUES (1)"])
    before = _digest(path)
    conn = open_readonly(path)
    assert conn.execute("SELECT a FROM t").fetchall() == [(1,)]
    assert conn.execute("SELECT count(*) FROM sqlite_master WHERE type='trigger'").fetchone() == (0,)
    conn.close()
    assert _digest(path) == before


@pytest.mark.parametrize("statement", ["INSERT INTO t VALUES (2)", "CREATE TABLE n (a INT)", "DROP TABLE t"])
def test_readonly_refuses_writes(tmp_path, statement):
    conn = open_readonly(_make_db(tmp_path / "x.db", ["CREATE TABLE t (a INT)"]))
    with pytest.raises(DB_ERRORS):
        conn.execute(statement)
    conn.close()


def test_readonly_does_not_create_a_missing_file(tmp_path):
    with pytest.raises(DB_ERRORS):
        open_readonly(tmp_path / "missing.db")
    assert not (tmp_path / "missing.db").exists()


def test_readonly_handles_special_characters_in_the_path(tmp_path):
    folder = tmp_path / "a b#c?d%e"
    folder.mkdir()
    conn = open_readonly(_make_db(folder / "x.db", ["CREATE TABLE t (a INT)"]))
    assert conn.execute("SELECT count(*) FROM t").fetchone() == (0,)
    conn.close()


def test_readonly_reads_a_database_in_wal_mode(tmp_path):
    path = tmp_path / "wal.db"
    writer = sqlite3.connect(path)
    writer.execute("PRAGMA journal_mode=WAL")
    writer.execute("CREATE TABLE t (a INT)")
    writer.execute("INSERT INTO t VALUES (1)")
    writer.commit()
    conn = open_readonly(path)
    assert conn.execute("SELECT a FROM t").fetchall() == [(1,)]
    conn.close()
    writer.close()


def test_readonly_encrypted_right_and_wrong_key(tmp_path, monkeypatch):
    sqlcipher3 = pytest.importorskip("sqlcipher3")
    path = tmp_path / "enc.db"
    conn = sqlcipher3.connect(str(path))
    conn.execute("PRAGMA key='richtig'")
    conn.execute("CREATE TABLE t (a INT)")
    conn.commit()
    conn.close()
    monkeypatch.setattr(db, "_load_db_key", lambda cfg: "richtig")
    reader = open_readonly(path)
    assert reader.execute("SELECT count(*) FROM t").fetchone() == (0,)
    reader.close()
    monkeypatch.setattr(db, "_load_db_key", lambda cfg: "falsch")
    with pytest.raises(DB_ERRORS):
        open_readonly(path)


def test_readonly_reports_a_garbage_file(tmp_path):
    path = tmp_path / "x.db"
    path.write_bytes(b"not a database, " * 100)
    with pytest.raises(DB_ERRORS):
        open_readonly(path)


# ── Timestamps ────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("text,expected", [
    ("2000-01-02 03:04:05", "2000-01-02 03:04:05"),
    ("2000-01-02T03:04:05.000000", "2000-01-02 03:04:05"),
    ("2000-01-02T05:04:05.000000+02:00", "2000-01-02 03:04:05"),
    ("2000-01-02T03:04:05Z", "2000-01-02 03:04:05"),
])
def test_all_stored_timestamp_formats_become_utc(text, expected):
    assert status.parse_ts(text) == _utc(expected)


@pytest.mark.parametrize("value", ["", "kein Datum", None])
def test_unreadable_timestamp_is_none(value):
    assert status.parse_ts(value) is None


def test_offset_timestamp_compares_as_time_not_as_text(paths):
    # Als Text wäre der erste jünger, tatsächlich ist er eine Stunde älter.
    _make_db(paths.db_path, [
        IMPORT_LOG,
        ("INSERT INTO import_log VALUES (?,?,?,?)", ("2000-01-02T12:30:00+02:00", "a", 1, None)),
        ("INSERT INTO import_log VALUES (?,?,?,?)", ("2000-01-02 11:30:00", "b", 1, None)),
    ])
    assert status.read_pipeline_status().imports.last_import == _utc("2000-01-02 11:30:00")


# ── Pipeline status ───────────────────────────────────────────────────────────

def _insert_compute(rows):
    return [("INSERT INTO compute_log VALUES (?,?,?)", row) for row in rows]


def _all_compute(ts, returncode=0):
    return _insert_compute([(ts, name, returncode) for name in COMPUTE_NAMES])


def _imports(*rows):
    return [("INSERT INTO import_log VALUES (?,?,?,?)", (*row, None)) for row in rows]


def test_missing_databases_leave_everything_unknown(paths):
    result = status.read_pipeline_status()
    assert not result.imports.known and not result.compute.known and not result.analysis.known
    assert result.compute_outdated is None
    assert not paths.db_path.exists()


def test_undecryptable_database_is_unknown(paths):
    paths.db_path.write_bytes(b"not a database, " * 100)
    assert status.read_pipeline_status().compute_outdated is None


def test_locked_database_is_unknown(paths, monkeypatch):
    def _locked(path):
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(status, "open_readonly", _locked)
    assert not status.read_pipeline_status().imports.known


def test_missing_log_table_is_unknown_and_the_rest_stays_known(paths):
    _make_db(paths.db_path, [IMPORT_LOG])
    result = status.read_pipeline_status()
    assert result.imports.known and not result.compute.known and not result.analysis.known
    assert result.compute_outdated is None


@pytest.mark.parametrize("source", ["post_import_pii_scrub", "compute_sleep_spo2"])
def test_sanitising_and_compute_rows_are_not_imports(paths, source):
    _make_db(paths.db_path, [IMPORT_LOG, COMPUTE_LOG, *_all_compute("2000-01-02 00:00:00"),
                             *_imports(("2000-01-01 00:00:00", "polar", 5), ("2000-06-01 00:00:00", source, 9))])
    result = status.read_pipeline_status()
    assert result.imports.last_import == _utc("2000-01-01 00:00:00")
    assert result.compute_outdated is False


def test_import_with_new_rows_makes_compute_outdated(paths):
    _make_db(paths.db_path, [IMPORT_LOG, COMPUTE_LOG, *_all_compute("2000-01-02 00:00:00"),
                             *_imports(("2000-01-03 00:00:00", "polar", 5))])
    assert status.read_pipeline_status().compute_outdated is True


def test_import_without_new_rows_does_not_make_compute_outdated(paths):
    _make_db(paths.db_path, [IMPORT_LOG, COMPUTE_LOG, *_all_compute("2000-01-02 00:00:00"),
                             *_imports(("2000-01-03 00:00:00", "polar", 0))])
    result = status.read_pipeline_status()
    assert result.imports.last_import == _utc("2000-01-03 00:00:00")
    assert result.compute_outdated is False


def test_import_into_medicine_db_counts(paths):
    _make_db(paths.db_path, [IMPORT_LOG, COMPUTE_LOG, *_all_compute("2000-01-02 00:00:00")])
    _make_db(paths.medicine_db_path, [IMPORT_LOG, *_imports(("2000-01-03 00:00:00", "lab", 2))])
    assert status.read_pipeline_status().compute_outdated is True


def test_on_demand_run_does_not_make_compute_look_current(paths):
    _make_db(paths.db_path, [
        IMPORT_LOG, COMPUTE_LOG, *_all_compute("2000-01-01 00:00:00"),
        *_imports(("2000-01-02 00:00:00", "polar", 5)),
        *_insert_compute([("2000-01-03 00:00:00", "compute_calibrate_sources.py", 0)]),
    ])
    result = status.read_pipeline_status()
    assert result.compute.last_run == _utc("2000-01-01 00:00:00")
    assert result.compute_outdated is True


def test_single_script_run_does_not_make_compute_look_current(paths):
    _make_db(paths.db_path, [
        IMPORT_LOG, COMPUTE_LOG, *_all_compute("2000-01-01 00:00:00"),
        *_imports(("2000-01-02 00:00:00", "polar", 5)),
        *_insert_compute([("2000-01-03 00:00:00", COMPUTE_NAMES[0], 0)]),
    ])
    result = status.read_pipeline_status()
    assert result.compute.last_run == _utc("2000-01-03 00:00:00")
    assert result.compute.oldest_success == _utc("2000-01-01 00:00:00")
    assert result.compute_outdated is True


def test_failed_and_never_run_scripts_are_named(paths):
    done = COMPUTE_NAMES[:-1]
    _make_db(paths.db_path, [
        IMPORT_LOG, COMPUTE_LOG,
        *_insert_compute([("2000-01-01 00:00:00", name, 0) for name in done]),
        *_insert_compute([("2000-01-02 00:00:00", done[0], 1)]),
        *_imports(("1999-01-01 00:00:00", "polar", 5)),
    ])
    result = status.read_pipeline_status()
    assert result.compute.never_succeeded == (COMPUTE_NAMES[-1],)
    assert result.compute.last_run_failed == (done[0],)
    assert result.compute.oldest_success is None
    assert result.compute_outdated is True


def test_no_imports_means_not_outdated(paths):
    _make_db(paths.db_path, [IMPORT_LOG, COMPUTE_LOG])
    assert status.read_pipeline_status().compute_outdated is False


def test_reading_status_changes_no_file(paths):
    _make_db(paths.db_path, [IMPORT_LOG, COMPUTE_LOG, ANALYSIS_LOG])
    before = _digest(paths.db_path)
    status.read_pipeline_status()
    assert _digest(paths.db_path) == before
    assert sorted(p.name for p in paths.db_path.parent.iterdir()) == ["health.db"]


def test_scripts_skipped_without_infection_date(paths):
    assert "analyse_mecfs" in status.skipped_without_infection_date()
    paths.infection_date = "2000-01-01"
    assert status.skipped_without_infection_date() == ()


# ── Persons ───────────────────────────────────────────────────────────────────

def _person_table(name, *persons):
    return [f"CREATE TABLE {name} (person TEXT)",
            *[(f"INSERT INTO {name} VALUES (?)", (p,)) for p in persons]]


def test_only_own_person_gives_one_choice(paths):
    _make_db(paths.db_path, _person_table("measurements", OWN_PERSON_ID))
    choices = status.read_person_choices()
    assert [c.pseudonym for c in choices] == [OWN_PERSON_ID]
    assert choices[0].is_own


def test_nothing_readable_leaves_the_own_person(paths):
    assert [c.pseudonym for c in status.read_person_choices()] == [OWN_PERSON_ID]


def test_several_persons_own_first_then_by_name(paths):
    _make_db(paths.db_path, _person_table("measurements", OWN_PERSON_ID, OTHER))
    _make_db(paths.medicine_db_path, _person_table("lab_manual", SECOND))
    paths.names = {OTHER: "Zeta", SECOND: "alpha", OWN_PERSON_ID: "interner Wert"}
    choices = status.read_person_choices()
    assert [(c.pseudonym, c.is_own) for c in choices] == [(OWN_PERSON_ID, True), (SECOND, False), (OTHER, False)]
    assert [c.display_name for c in choices[1:]] == ["alpha", "Zeta"]
    assert "interner Wert" not in choices[0].display_name


def test_pseudonym_of_unassigned_data_is_not_a_person(paths):
    _make_db(paths.db_path, _person_table("measurements", OTHER))
    paths.names = {OTHER: "unknown"}
    assert [c.pseudonym for c in status.read_person_choices()] == [OWN_PERSON_ID]


def test_person_without_a_name_shows_the_pseudonym(paths):
    _make_db(paths.db_path, _person_table("measurements", OTHER))
    assert OTHER in [c.display_name for c in status.read_person_choices()]


@pytest.mark.parametrize("value", ["unknown", None, "self", ""])
def test_values_that_are_no_pseudonym_are_ignored(paths, value):
    _make_db(paths.db_path, _person_table("measurements", value))
    assert [c.pseudonym for c in status.read_person_choices()] == [OWN_PERSON_ID]


@pytest.mark.parametrize("table", ["devices", "source_priority", "import_log", "persons", "audit_log"])
def test_tables_without_health_data_add_no_person(paths, table):
    _make_db(paths.db_path, _person_table(table, OTHER))
    assert [c.pseudonym for c in status.read_person_choices()] == [OWN_PERSON_ID]


def test_reading_persons_changes_no_file(paths):
    _make_db(paths.db_path, _person_table("measurements", OTHER))
    paths.names = {OTHER: "Zeta"}
    before = {p.name: _digest(p) for p in paths.db_path.parent.iterdir()}
    status.read_person_choices()
    assert {p.name: _digest(p) for p in paths.db_path.parent.iterdir()} == before


def test_failing_name_lookup_shows_the_pseudonym(paths, monkeypatch):
    def _broken(pseudonym):
        raise sqlite3.OperationalError("unable to open database file")

    monkeypatch.setattr(status, "reverse_resolve", _broken)
    _make_db(paths.db_path, _person_table("measurements", OTHER))
    assert OTHER in [c.display_name for c in status.read_person_choices()]
