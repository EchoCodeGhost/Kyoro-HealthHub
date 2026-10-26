# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests für Praxis-/Labor-Pseudonymisierung (synthetische Namen)."""
import sqlite3

import pytest

from utils import anonymize, pseudonymize_providers as pp


@pytest.fixture
def identity(monkeypatch, tmp_path):
    monkeypatch.setattr(anonymize, "_IDENTITY_DB", tmp_path / "identity.db")
    return tmp_path / "identity.db"


def test_pseudonym_is_stable_and_mapped(identity):
    a = anonymize.pseudonymize_provider("Labor Musterlabor GmbH", "Labor")
    b = anonymize.pseudonymize_provider("  labor musterlabor gmbh ", "Labor")
    assert a == b and a.startswith("Labor-")
    assert anonymize.pseudonymize_provider(a, "Labor") == a
    con = sqlite3.connect(identity)
    assert con.execute("SELECT name_real FROM provider_pseudonym_map WHERE pseudo_id=?", (a,)).fetchone()


def test_process_rewrites_names_and_addresses(identity):
    con = sqlite3.connect(":memory:")
    con.execute("CREATE TABLE lab_manual (date TEXT, parameter TEXT, labor TEXT NOT NULL DEFAULT '', "
                "kommentar TEXT, person TEXT, PRIMARY KEY (date, parameter, labor, person))")
    con.execute("INSERT INTO lab_manual VALUES ('2026-01-01','CRP','Musterlabor','Probe aus Musterstraße 12, 12345 Musterstadt','p')")
    stats = pp.process(con)
    labor, kommentar = con.execute("SELECT labor, kommentar FROM lab_manual").fetchone()
    assert labor.startswith("Labor-") and "Musterlabor" not in labor
    assert "Musterstraße" not in kommentar and "[ADRESSE-ENTFERNT]" in kommentar
    assert stats == {"names": 1, "texts": 1}
    assert pp.process(con) == {"names": 0, "texts": 0}


def test_primary_key_collision_keeps_existing_row(identity):
    pseudo = anonymize.pseudonymize_provider("Musterlabor", "Labor")
    con = sqlite3.connect(":memory:")
    con.execute("CREATE TABLE lab_manual (date TEXT, parameter TEXT, labor TEXT NOT NULL DEFAULT '', "
                "person TEXT, PRIMARY KEY (date, parameter, labor, person))")
    con.execute("INSERT INTO lab_manual VALUES ('2026-01-01','CRP',?, 'p')", (pseudo,))
    con.execute("INSERT INTO lab_manual VALUES ('2026-01-01','CRP','Musterlabor','p')")
    pp.process(con)
    assert con.execute("SELECT COUNT(*), MIN(labor) FROM lab_manual").fetchone() == (1, pseudo)


def test_dry_run_changes_nothing(identity):
    con = sqlite3.connect(":memory:")
    con.execute("CREATE TABLE lab_manual (date TEXT, parameter TEXT, labor TEXT NOT NULL DEFAULT '', person TEXT)")
    con.execute("INSERT INTO lab_manual VALUES ('2026-01-01','CRP','Musterlabor','p')")
    assert pp.process(con, dry_run=True)["names"] == 1
    assert con.execute("SELECT labor FROM lab_manual").fetchone()[0] == "Musterlabor"
