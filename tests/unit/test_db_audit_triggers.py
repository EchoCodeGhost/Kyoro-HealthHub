# SPDX-License-Identifier: GPL-3.0-or-later
"""
Regression test for modules/db.py's _install_audit_log_triggers().

Background: the config-directory chain-of-custody work (ensure_git_repo(),
commit_config_change()) only covers KYORO_CONFIG_DIR's JSON files — the
actual clinical data lives in health.db/medicine.db, where a silent UPDATE
or DELETE (found live this session: a raw SQL fix reclassifying a
misattributed ECG session) left no trace anywhere except this chat. These
triggers close that gap at the database level, so it fires regardless of
whether the change came through a Kyoro script, the sqlite3 CLI, or
Datasette.
"""

import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

from modules.db import _install_audit_log_triggers


def _fresh_conn():
    conn = sqlite3.connect(":memory:")
    conn.execute(
        "CREATE TABLE symptoms (id INTEGER PRIMARY KEY, person TEXT, "
        "date TEXT, symptom TEXT, severity INTEGER)"
    )
    return conn


def test_insert_is_not_audited():
    conn = _fresh_conn()
    _install_audit_log_triggers(conn)

    conn.execute("INSERT INTO symptoms (person, date, symptom, severity) "
                 "VALUES ('PER-x', '2026-08-16', 'Kopfschmerz', 5)")
    conn.commit()

    assert conn.execute("SELECT count(*) FROM audit_log").fetchone()[0] == 0


def test_update_is_audited_with_old_and_new_values():
    conn = _fresh_conn()
    _install_audit_log_triggers(conn)
    conn.execute("INSERT INTO symptoms (id, person, date, symptom, severity) "
                 "VALUES (1, 'PER-x', '2026-08-16', 'Kopfschmerz', 5)")
    conn.commit()

    conn.execute("UPDATE symptoms SET severity = 8 WHERE id = 1")
    conn.commit()

    row = conn.execute(
        "SELECT operation, old_data, new_data FROM audit_log").fetchone()
    assert row[0] == "UPDATE"
    old = json.loads(row[1])
    new = json.loads(row[2])
    assert old["severity"] == 5
    assert new["severity"] == 8
    assert old["symptom"] == new["symptom"] == "Kopfschmerz"


def test_delete_is_audited_with_old_values_and_null_new():
    conn = _fresh_conn()
    _install_audit_log_triggers(conn)
    conn.execute("INSERT INTO symptoms (id, person, date, symptom, severity) "
                 "VALUES (1, 'PER-x', '2026-08-16', 'Kopfschmerz', 5)")
    conn.commit()

    conn.execute("DELETE FROM symptoms WHERE id = 1")
    conn.commit()

    row = conn.execute(
        "SELECT operation, old_data, new_data FROM audit_log").fetchone()
    assert row[0] == "DELETE"
    assert json.loads(row[1])["severity"] == 5
    assert row[2] is None


def test_fires_regardless_of_caller_not_just_kyoro_code():
    """The whole point: a change made via raw SQL (standing in for the
    sqlite3 CLI or Datasette, which also go through triggers, not app code)
    must be caught exactly like a change from a Kyoro script would be."""
    conn = _fresh_conn()
    _install_audit_log_triggers(conn)
    conn.execute("INSERT INTO symptoms (id, person, date, symptom, severity) "
                 "VALUES (1, 'PER-x', '2026-08-16', 'Kopfschmerz', 5)")
    conn.commit()

    # No Kyoro helper involved at all — raw cursor.execute, as an external
    # tool would issue it.
    conn.execute("UPDATE symptoms SET severity = 99 WHERE id = 1")
    conn.commit()

    assert conn.execute("SELECT count(*) FROM audit_log").fetchone()[0] == 1


def test_reinstall_is_idempotent_no_duplicate_triggers():
    conn = _fresh_conn()
    _install_audit_log_triggers(conn)
    _install_audit_log_triggers(conn)

    triggers = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='trigger' AND name LIKE '_audit_%'"
    ).fetchall()
    assert len(triggers) == 2  # one UPDATE + one DELETE trigger, not four


def test_self_heals_when_a_column_is_added_later():
    """Found essential live: triggers bake in a fixed column list at CREATE
    TRIGGER time. Without a re-check, a column added via a later migration
    (ALTER TABLE) would silently be missing from all future audit entries."""
    conn = _fresh_conn()
    _install_audit_log_triggers(conn)
    trigger_before = conn.execute(
        "SELECT sql FROM sqlite_master WHERE name='_audit_symptoms_update'"
    ).fetchone()[0]

    conn.execute("ALTER TABLE symptoms ADD COLUMN notes TEXT")
    conn.commit()
    _install_audit_log_triggers(conn)  # simulates the next connection open

    trigger_after = conn.execute(
        "SELECT sql FROM sqlite_master WHERE name='_audit_symptoms_update'"
    ).fetchone()[0]
    assert trigger_before != trigger_after
    assert '"notes"' in trigger_after or "'notes'" in trigger_after

    conn.execute("INSERT INTO symptoms (id, person, date, symptom, severity, notes) "
                 "VALUES (1, 'PER-x', '2026-08-16', 'Kopfschmerz', 5, 'initial')")
    conn.commit()
    conn.execute("UPDATE symptoms SET notes = 'updated' WHERE id = 1")
    conn.commit()

    new_data = json.loads(
        conn.execute("SELECT new_data FROM audit_log").fetchone()[0])
    assert new_data["notes"] == "updated"


def test_audit_log_table_itself_is_never_audited():
    """Must not create triggers on audit_log itself — would recurse."""
    conn = _fresh_conn()
    _install_audit_log_triggers(conn)

    trigger_names = {
        row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='trigger'").fetchall()
    }
    assert "_audit_audit_log_update" not in trigger_names
    assert "_audit_audit_log_delete" not in trigger_names


def test_second_table_gets_its_own_independent_triggers():
    conn = _fresh_conn()
    conn.execute("CREATE TABLE medications (id INTEGER PRIMARY KEY, name TEXT)")
    _install_audit_log_triggers(conn)

    conn.execute("INSERT INTO medications (id, name) VALUES (1, 'Cetirizin')")
    conn.commit()
    conn.execute("UPDATE medications SET name = 'Bilastin' WHERE id = 1")
    conn.commit()

    rows = conn.execute(
        "SELECT table_name, operation FROM audit_log").fetchall()
    assert rows == [("medications", "UPDATE")]
