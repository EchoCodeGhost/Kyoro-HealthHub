# SPDX-License-Identifier: GPL-3.0-or-later
"""
Regression tests for scripts/utils/promote_anamnese_findings.py.

Background: the first version of this script was tested against a hand-rolled
CREATE TABLE statement (with an extra `slug` column bolted on) instead of the
real project schema in utils/create_schema.py, which never got that column.
Every real `--promote` call crashed with "no such column: slug" — invisible
to the original tests because they never built the schema the same way
production does. These tests execute the actual SCHEMA string so a future
schema/code drift like that fails here instead of at runtime.

Also covers: idempotency (a second `--promote` run must not re-offer or
duplicate an already-promoted finding/target pair, task 2.3), and the
`slug` fallback in build_target_entry (finding.get("slug", "generic") never
engages because the key is always present-but-None, not absent).
"""

import json
import sqlite3
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

from utils.create_schema import SCHEMA
import health_config
import modules.identity_resolver as identity_resolver
import utils.manage.personal.manage_family_history as manage_family_history
import utils.manage.personal.manage_travel_history as manage_travel_history
import utils.manage.personal.manage_exposure_history as manage_exposure_history
import utils.manage.personal.manage_known_risk_exposures as manage_known_risk_exposures
import utils.promote_anamnese_findings as promote


PER_TEST_PSEUDO = "PER-test123"


@pytest.fixture
def promotion_env(tmp_path, monkeypatch):
    """Real project schema in a temp DB + the four JSON stores redirected to tmp_path."""
    config_dir = tmp_path / ".config" / "kyoro"
    config_dir.mkdir(parents=True)

    monkeypatch.setattr(health_config, "KYORO_CONFIG_DIR", config_dir, raising=False)
    monkeypatch.setattr(manage_family_history, "HISTORY_FILE", config_dir / "family_history.json")
    monkeypatch.setattr(manage_travel_history, "TRAVEL_FILE", config_dir / "travel_history.json")
    monkeypatch.setattr(manage_exposure_history, "EXPOSURE_FILE", config_dir / "exposure_history.json")
    monkeypatch.setattr(manage_known_risk_exposures, "RISK_FILE", config_dir / "known_risk_exposures.json")

    monkeypatch.setattr(
        identity_resolver, "resolve_display_name",
        lambda pseudo_id: "Mutter" if pseudo_id == PER_TEST_PSEUDO else "Unknown",
        raising=False,
    )
    # promote_anamnese_findings imported resolve_display_name by name — patch its own binding too.
    monkeypatch.setattr(
        promote, "resolve_display_name",
        lambda pseudo_id: "Mutter" if pseudo_id == PER_TEST_PSEUDO else "Unknown",
    )

    db_path = tmp_path / "test_health.db"
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA)

    # promote_anamnese_findings did `from modules.db import open_db` — patching
    # modules.db.open_db afterwards does NOT affect that already-bound name,
    # only patching the name inside promote's own module namespace does.
    monkeypatch.setattr(promote, "open_db", lambda: sqlite3.connect(db_path))

    yield conn
    conn.close()


def _insert_session(conn, track="family"):
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT INTO anamnese_sessions (track, started_at, last_updated_at, transcript_json, status) "
        "VALUES (?, ?, ?, ?, ?)",
        (track, now, now, json.dumps([{"role": "system", "content": "Test"}]), "completed"),
    )
    conn.commit()
    return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def _insert_finding(conn, session_id, track, **overrides):
    now = datetime.now(timezone.utc).isoformat()
    finding = {
        "date_or_period": None,
        "place_or_subject": None,
        "event_text": "Test event",
        "relevance_note": None,
        "person": PER_TEST_PSEUDO,
        "slug": None,
        **overrides,
    }
    conn.execute(
        "INSERT INTO anamnese_findings "
        "(session_id, track, date_or_period, place_or_subject, event_text, relevance_note, person, slug, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            session_id, track, finding["date_or_period"], finding["place_or_subject"],
            finding["event_text"], finding["relevance_note"], finding["person"],
            finding["slug"], now,
        ),
    )
    conn.commit()
    return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def test_get_session_findings_matches_real_schema(promotion_env):
    """The query in get_session_findings() must run against the real schema (no `slug` crash)."""
    conn = promotion_env
    session_id = _insert_session(conn, "family")
    _insert_finding(conn, session_id, "family", place_or_subject="Mutter", event_text="Brustkrebs diagnostiziert")

    findings = promote.get_session_findings(conn, session_id)

    assert len(findings) == 1
    assert findings[0]["event_text"] == "Brustkrebs diagnostiziert"
    assert findings[0]["slug"] is None


def test_promote_end_to_end_writes_to_target_stores(promotion_env, monkeypatch):
    """A family-history finding, promoted, must land in family_history.json."""
    conn = promotion_env
    session_id = _insert_session(conn, "family")
    _insert_finding(
        conn, session_id, "family",
        place_or_subject="Mutter", event_text="Brustkrebs diagnostiziert",
        date_or_period="1985", relevance_note="bestätigt",
    )

    promote.main(session_id, auto_confirm=True)

    family_file = health_config.KYORO_CONFIG_DIR / "family_history.json"
    assert family_file.exists()
    data = json.loads(family_file.read_text())
    assert len(data) == 1
    assert data[0]["relative"] == "Mutter"
    assert data[0]["condition"] == "Brustkrebs diagnostiziert"


def test_promote_is_idempotent(promotion_env):
    """Re-running --promote for the same session must not duplicate entries (task 2.3)."""
    conn = promotion_env
    session_id = _insert_session(conn, "family")
    _insert_finding(conn, session_id, "family", place_or_subject="Mutter", event_text="Brustkrebs diagnostiziert")

    promote.main(session_id, auto_confirm=True)
    promote.main(session_id, auto_confirm=True)

    family_file = health_config.KYORO_CONFIG_DIR / "family_history.json"
    data = json.loads(family_file.read_text())
    assert len(data) == 1, "second --promote run duplicated the entry"


def test_promoted_target_types_recorded(promotion_env):
    """A promoted finding/target pair must be recorded in anamnese_promotions."""
    conn = promotion_env
    session_id = _insert_session(conn, "family")
    finding_id = _insert_finding(conn, session_id, "family", place_or_subject="Mutter", event_text="Test")

    assert promote.get_promoted_target_types(conn, finding_id) == set()

    promote.main(session_id, auto_confirm=True)

    assert promote.get_promoted_target_types(conn, finding_id) == {"family"}


def test_chronic_secondary_target_offered_once_then_suppressed(promotion_env):
    """An animal-track finding offers exposure_history + known_risk_exposures once;
    a second run must not re-offer either, even with a real slug."""
    conn = promotion_env
    session_id = _insert_session(conn, "animal")
    finding_id = _insert_finding(
        conn, session_id, "animal",
        place_or_subject="Rind", event_text="Regelmäßiger Kontakt mit Rindern",
        date_or_period="2010-2020", slug="q_fieber",
    )

    targets_before = promote.get_promotion_targets(promote.get_session_findings(conn, session_id)[0])
    assert {t[2] for t in targets_before} == {"animal", "risk"}

    promote.main(session_id, auto_confirm=True)

    assert promote.get_promoted_target_types(conn, finding_id) == {"animal", "risk"}

    exposure_file = health_config.KYORO_CONFIG_DIR / "exposure_history.json"
    risk_file = health_config.KYORO_CONFIG_DIR / "known_risk_exposures.json"
    assert len(json.loads(exposure_file.read_text())["animal_contacts"]) == 1
    assert len(json.loads(risk_file.read_text())) == 1

    promote.main(session_id, auto_confirm=True)

    assert len(json.loads(exposure_file.read_text())["animal_contacts"]) == 1
    assert len(json.loads(risk_file.read_text())) == 1


def test_invalid_slug_finding_excluded_not_silently_written(promotion_env):
    """task 4.2: a finding with an invalid/stale known_risk_exposures slug must be
    excluded with a clear error, not silently dropped or written invalid — and must
    not be marked as promoted, so it can be retried once the slug is fixed."""
    conn = promotion_env
    session_id = _insert_session(conn, "leisure")
    finding_id = _insert_finding(
        conn, session_id, "leisure",
        event_text="Höhlenwandern als Hobby", slug="unbekannter_erreger",
    )

    promote.main(session_id, auto_confirm=True)

    risk_file = health_config.KYORO_CONFIG_DIR / "known_risk_exposures.json"
    assert not risk_file.exists(), "invalid-slug finding must not be written to the store"
    assert promote.get_promoted_target_types(conn, finding_id) == set(), (
        "a failed promotion must not be recorded as promoted"
    )


def test_risk_slug_fallback_actually_engages():
    """finding.get("slug", "generic") never fires because the key is always present
    (just possibly None) — build_target_entry must use `or` to fall back correctly."""
    finding = {
        "event_text": "Some hobby exposure",
        "relevance_note": None,
        "person": PER_TEST_PSEUDO,
        "date_or_period": None,
        "slug": None,
    }
    entry = promote.build_target_entry(finding, "risk")
    assert entry["slug"] == "generic"
